import graphene
import pytest

from saleor.app.models import App
from saleor.webhook.models import Webhook

from saleor.graphql.tests.utils import get_graphql_content, get_graphql_content_from_response

QUERY_BY_IDENTIFIER = """
    query webhook($identifier: String) {
      webhook(identifier: $identifier) {
        id
        identifier
      }
    }
"""

QUERY_BY_ID = """
    query webhook($id: ID!) {
      webhook(id: $id) {
        id
      }
    }
"""

QUERY_BY_BOTH = """
    query webhook($id: ID, $identifier: String) {
      webhook(id: $id, identifier: $identifier) {
        id
      }
    }
"""

IDENTIFIER = "order-created-handler"


@pytest.fixture
def other_app_webhook(db):
    other_app = App.objects.create(name="Other app", is_active=True)
    return Webhook.objects.create(
        app=other_app,
        name="other",
        target_url="https://www.example.com/other",
        identifier=IDENTIFIER,
    )


@pytest.fixture
def own_webhook(webhook):
    webhook.identifier = IDENTIFIER
    webhook.save(update_fields=["identifier"])
    return webhook


def test_behavior_app_looks_up_own_webhook(app_api_client, own_webhook):
    response = app_api_client.post_graphql(
        QUERY_BY_IDENTIFIER, {"identifier": IDENTIFIER}
    )
    content = get_graphql_content(response)
    assert content["data"]["webhook"] == {
        "id": graphene.Node.to_global_id("Webhook", own_webhook.pk),
        "identifier": IDENTIFIER,
    }


def test_behavior_app_unknown_identifier_returns_null(app_api_client, own_webhook):
    response = app_api_client.post_graphql(
        QUERY_BY_IDENTIFIER, {"identifier": "does-not-exist"}
    )
    content = get_graphql_content(response)
    assert content["data"]["webhook"] is None


def test_behavior_id_and_identifier_together_is_error(app_api_client, own_webhook):
    response = app_api_client.post_graphql(
        QUERY_BY_BOTH,
        {
            "id": graphene.Node.to_global_id("Webhook", own_webhook.pk),
            "identifier": IDENTIFIER,
        },
    )
    content = get_graphql_content_from_response(response)
    assert len(content["errors"]) == 1
    assert content["data"]["webhook"] is None


def test_behavior_neither_id_nor_identifier_is_error(app_api_client, own_webhook):
    response = app_api_client.post_graphql(QUERY_BY_BOTH, {})
    content = get_graphql_content_from_response(response)
    assert len(content["errors"]) == 1
    assert content["data"]["webhook"] is None


def test_unchanged_lookup_by_id_still_works(app_api_client, own_webhook):
    response = app_api_client.post_graphql(
        QUERY_BY_ID,
        {"id": graphene.Node.to_global_id("Webhook", own_webhook.pk)},
    )
    content = get_graphql_content(response)
    assert content["data"]["webhook"]["id"] == graphene.Node.to_global_id(
        "Webhook", own_webhook.pk
    )


def test_behavior_app_never_sees_other_apps_webhook_with_same_identifier(
    app_api_client, own_webhook, other_app_webhook
):
    # the other app's webhook was created last and shares the identifier
    response = app_api_client.post_graphql(
        QUERY_BY_IDENTIFIER, {"identifier": IDENTIFIER}
    )
    content = get_graphql_content(response)
    assert content["data"]["webhook"]["id"] == graphene.Node.to_global_id(
        "Webhook", own_webhook.pk
    )


def test_rule_staff_cannot_use_identifier(
    staff_api_client, permission_manage_apps, own_webhook, other_app_webhook
):
    staff_api_client.user.user_permissions.add(permission_manage_apps)
    response = staff_api_client.post_graphql(
        QUERY_BY_IDENTIFIER, {"identifier": IDENTIFIER}
    )
    content = get_graphql_content_from_response(response)
    assert content["data"]["webhook"] is None
    assert len(content["errors"]) == 1


def test_unchanged_staff_still_uses_id(
    staff_api_client, permission_manage_apps, own_webhook
):
    staff_api_client.user.user_permissions.add(permission_manage_apps)
    webhook_id = graphene.Node.to_global_id("Webhook", own_webhook.pk)
    response = staff_api_client.post_graphql(QUERY_BY_ID, {"id": webhook_id})
    content = get_graphql_content(response)
    assert content["data"]["webhook"]["id"] == webhook_id
