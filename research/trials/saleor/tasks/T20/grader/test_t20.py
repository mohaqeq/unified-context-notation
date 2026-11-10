from datetime import timedelta

import graphene
from django.utils import timezone

from saleor.core import EventDeliveryStatus
from saleor.core.models import EventDelivery
from saleor.graphql.tests.utils import get_graphql_content
from saleor.webhook.event_types import WebhookEventAsyncType

QUERY = """
    query($id: ID!, $filter: EventDeliveryFilterInput!) {
      webhook(id: $id) {
        eventDeliveries(first: 20, filter: $filter) {
          edges { node { id status } }
        }
      }
    }
"""


def make_deliveries(webhook, event_payload):
    now = timezone.now()
    ages = {
        "old": timedelta(days=10),
        "middle": timedelta(days=5),
        "new": timedelta(days=1),
    }
    deliveries = {}
    for name, age in ages.items():
        status = (
            EventDeliveryStatus.PENDING if name == "new" else EventDeliveryStatus.FAILED
        )
        delivery = EventDelivery.objects.create(
            event_type=WebhookEventAsyncType.ANY,
            payload=event_payload,
            webhook=webhook,
            status=status,
        )
        EventDelivery.objects.filter(pk=delivery.pk).update(created_at=now - age)
        deliveries[name] = delivery
    return now, deliveries


def listed(client, webhook, filter_input):
    variables = {
        "id": graphene.Node.to_global_id("Webhook", webhook.pk),
        "filter": filter_input,
    }
    content = get_graphql_content(client.post_graphql(QUERY, variables))
    edges = content["data"]["webhook"]["eventDeliveries"]["edges"]
    return {edge["node"]["id"] for edge in edges}


def ids(*deliveries):
    return {graphene.Node.to_global_id("EventDelivery", d.pk) for d in deliveries}


def days_ago(now, days):
    return (now - timedelta(days=days)).isoformat()


def test_behavior_lower_bound(
    staff_api_client, permission_manage_apps, webhook, event_payload
):
    staff_api_client.user.user_permissions.add(permission_manage_apps)
    now, d = make_deliveries(webhook, event_payload)

    result = listed(
        staff_api_client, webhook, {"createdAt": {"gte": days_ago(now, 6)}}
    )

    assert result == ids(d["middle"], d["new"])


def test_behavior_upper_bound(
    staff_api_client, permission_manage_apps, webhook, event_payload
):
    staff_api_client.user.user_permissions.add(permission_manage_apps)
    now, d = make_deliveries(webhook, event_payload)

    result = listed(
        staff_api_client, webhook, {"createdAt": {"lte": days_ago(now, 6)}}
    )

    assert result == ids(d["old"])


def test_behavior_both_bounds(
    staff_api_client, permission_manage_apps, webhook, event_payload
):
    staff_api_client.user.user_permissions.add(permission_manage_apps)
    now, d = make_deliveries(webhook, event_payload)

    result = listed(
        staff_api_client,
        webhook,
        {"createdAt": {"gte": days_ago(now, 6), "lte": days_ago(now, 2)}},
    )

    assert result == ids(d["middle"])


def test_behavior_combines_with_status(
    staff_api_client, permission_manage_apps, webhook, event_payload
):
    staff_api_client.user.user_permissions.add(permission_manage_apps)
    now, d = make_deliveries(webhook, event_payload)

    result = listed(
        staff_api_client,
        webhook,
        {
            "createdAt": {"gte": days_ago(now, 6)},
            "status": EventDeliveryStatus.FAILED.upper(),
        },
    )

    assert result == ids(d["middle"])


def test_behavior_empty_range_does_not_restrict(
    staff_api_client, permission_manage_apps, webhook, event_payload
):
    staff_api_client.user.user_permissions.add(permission_manage_apps)
    _now, d = make_deliveries(webhook, event_payload)

    result = listed(staff_api_client, webhook, {"createdAt": {}})

    assert result == ids(d["old"], d["middle"], d["new"])
