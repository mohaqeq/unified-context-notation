from unittest.mock import patch

import graphene
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from saleor.core import EventDeliveryStatus
from saleor.core.models import EventDelivery
from saleor.graphql.tests.utils import (
    assert_no_permission,
    get_graphql_content,
    get_graphql_content_from_response,
)
from saleor.webhook.event_types import WebhookEventAsyncType

MUTATION = """
    mutation($ids: [ID!]!) {
      eventDeliveryBulkRetry(ids: $ids) {
        count
        errors { field code message }
      }
    }
"""

SEND_TASK = "saleor.webhook.transport.asynchronous.transport.send_webhook_request_async"


@pytest.fixture(autouse=True)
def _webhook_plugin(settings):
    settings.PLUGINS = ["saleor.plugins.webhook.plugin.WebhookPlugin"]


@pytest.fixture
def failed_deliveries(webhook, event_payload):
    return [
        EventDelivery.objects.create(
            event_type=WebhookEventAsyncType.ANY,
            payload=event_payload,
            webhook=webhook,
            status=EventDeliveryStatus.FAILED,
        )
        for _ in range(6)
    ]


def to_ids(deliveries):
    return [graphene.Node.to_global_id("EventDelivery", d.pk) for d in deliveries]


def statuses():
    return set(EventDelivery.objects.values_list("status", flat=True))


def test_behavior_retries_all_given_deliveries(
    app_api_client, permission_manage_apps, failed_deliveries
):
    app_api_client.app.permissions.add(permission_manage_apps)
    with patch(SEND_TASK + ".apply_async") as mocked_send:
        content = get_graphql_content(
            app_api_client.post_graphql(
                MUTATION, {"ids": to_ids(failed_deliveries)}
            )
        )

    data = content["data"]["eventDeliveryBulkRetry"]
    assert data["errors"] == []
    assert data["count"] == len(failed_deliveries)
    assert statuses() == {EventDeliveryStatus.PENDING}
    scheduled = sorted(
        call.kwargs["kwargs"]["event_delivery_id"]
        for call in mocked_send.call_args_list
    )
    assert scheduled == sorted(d.pk for d in failed_deliveries)


def test_behavior_only_given_deliveries_are_retried(
    app_api_client, permission_manage_apps, failed_deliveries
):
    app_api_client.app.permissions.add(permission_manage_apps)
    chosen, untouched = failed_deliveries[:2], failed_deliveries[2:]
    with patch(SEND_TASK + ".apply_async") as mocked_send:
        content = get_graphql_content(
            app_api_client.post_graphql(MUTATION, {"ids": to_ids(chosen)})
        )

    assert content["data"]["eventDeliveryBulkRetry"]["count"] == 2
    assert mocked_send.call_count == 2
    for delivery in chosen:
        delivery.refresh_from_db()
        assert delivery.status == EventDeliveryStatus.PENDING
    for delivery in untouched:
        delivery.refresh_from_db()
        assert delivery.status == EventDeliveryStatus.FAILED


def test_behavior_unresolvable_id_changes_nothing(
    app_api_client, permission_manage_apps, failed_deliveries
):
    app_api_client.app.permissions.add(permission_manage_apps)
    ids = [*to_ids(failed_deliveries), graphene.Node.to_global_id("EventDelivery", -1)]
    with patch(SEND_TASK + ".apply_async") as mocked_send:
        content = get_graphql_content(
            app_api_client.post_graphql(MUTATION, {"ids": ids})
        )

    errors = content["data"]["eventDeliveryBulkRetry"]["errors"]
    assert len(errors) == 1
    assert errors[0]["field"] == "ids"
    assert statuses() == {EventDeliveryStatus.FAILED}
    assert mocked_send.call_count == 0


def test_behavior_requires_manage_apps(staff_api_client, failed_deliveries):
    with patch(SEND_TASK + ".apply_async") as mocked_send:
        response = staff_api_client.post_graphql(
            MUTATION, {"ids": to_ids(failed_deliveries)}
        )

    assert_no_permission(response)
    assert statuses() == {EventDeliveryStatus.FAILED}
    assert mocked_send.call_count == 0


def test_rule_status_is_changed_with_a_constant_number_of_writes(
    app_api_client, permission_manage_apps, failed_deliveries
):
    app_api_client.app.permissions.add(permission_manage_apps)
    with patch(SEND_TASK + ".apply_async"):
        with CaptureQueriesContext(connection) as ctx:
            content = get_graphql_content(
                app_api_client.post_graphql(
                    MUTATION, {"ids": to_ids(failed_deliveries)}
                )
            )

    assert content["data"]["eventDeliveryBulkRetry"]["count"] == len(failed_deliveries)
    updates = [
        q["sql"]
        for q in ctx.captured_queries
        if q["sql"].startswith('UPDATE "core_eventdelivery"')
    ]
    assert len(updates) == 1, updates
