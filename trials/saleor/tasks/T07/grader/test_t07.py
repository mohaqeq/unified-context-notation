import datetime
from decimal import Decimal

import graphene
import pytest
from django.utils import timezone

from saleor.graphql.tests.utils import (
    assert_no_permission,
    get_graphql_content,
    get_graphql_content_from_response,
)
from saleor.payment import TransactionEventType
from saleor.payment.models import TransactionEvent

REFUNDS_QUERY = """
query Order($id: ID!) {
  order(id: $id) {
    transactionSummaries {
      chargedAmount { amount }
      refunds {
        amount { amount currency }
        createdAt
      }
    }
  }
}
"""

TRANSACTIONS_QUERY = """
query Order($id: ID!) {
  order(id: $id) {
    transactions {
      id
      pspReference
      events { pspReference createdBy { __typename } }
    }
  }
}
"""

TYPE_QUERY = """
query Type($name: String!) {
  __type(name: $name) {
    fields {
      name
      type {
        kind
        name
        ofType { kind name ofType { kind name ofType { kind name } } }
      }
    }
  }
}
"""

# Fields that identify the PSP record, the people involved or internal details.
INTERNAL_FIELDS = {
    "id",
    "token",
    "externalUrl",
    "events",
    "createdBy",
    "name",
    "message",
    "pspReference",
    "actions",
    "modifiedAt",
    "order",
    "checkout",
    "app",
    "appIdentifier",
    "idempotencyKey",
    "metadata",
    "privateMetadata",
    "user",
    "transaction",
}


def _event(transaction, event_type, amount, created_at, psp_reference):
    return TransactionEvent.objects.create(
        transaction=transaction,
        type=event_type,
        amount_value=Decimal(amount),
        currency=transaction.currency,
        created_at=created_at,
        psp_reference=psp_reference,
        message="internal note",
    )


def _query(client, order, query):
    variables = {"id": graphene.Node.to_global_id("Order", order.pk)}
    return client.post_graphql(query, variables)


@pytest.mark.parametrize("client_fixture", ["api_client", "user_api_client"])
def test_behavior_lists_successful_refunds_oldest_first(
    client_fixture, request, order, transaction_item_generator
):
    # given
    client = request.getfixturevalue(client_fixture)
    now = timezone.now()
    first_at = now - datetime.timedelta(days=3)
    second_at = now - datetime.timedelta(days=1)
    refunded = transaction_item_generator(
        order_id=order.pk,
        charged_value=Decimal("20.00"),
        psp_reference="psp-refunded",
    )
    # created out of order on purpose, plus events that are not successful refunds
    _event(refunded, TransactionEventType.REFUND_SUCCESS, "3.00", second_at, "r2")
    _event(refunded, TransactionEventType.CHARGE_SUCCESS, "20.00", now, "c1")
    _event(refunded, TransactionEventType.REFUND_REQUEST, "2.00", now, "rq1")
    _event(refunded, TransactionEventType.REFUND_FAILURE, "4.00", now, "rf1")
    _event(refunded, TransactionEventType.REFUND_SUCCESS, "5.00", first_at, "r1")
    untouched = transaction_item_generator(
        order_id=order.pk,
        charged_value=Decimal("7.00"),
        psp_reference="psp-untouched",
    )
    _event(untouched, TransactionEventType.CHARGE_SUCCESS, "7.00", now, "c2")

    # when
    response = _query(client, order, REFUNDS_QUERY)

    # then
    summaries = get_graphql_content(response)["data"]["order"]["transactionSummaries"]
    assert len(summaries) == 2
    by_charged = {s["chargedAmount"]["amount"]: s["refunds"] for s in summaries}
    assert by_charged[7.0] == []
    refunds = by_charged[20.0]
    assert [r["amount"] for r in refunds] == [
        {"amount": 5.0, "currency": order.currency},
        {"amount": 3.0, "currency": order.currency},
    ]
    assert [datetime.datetime.fromisoformat(r["createdAt"]) for r in refunds] == [
        first_at,
        second_at,
    ]


@pytest.mark.parametrize("client_fixture", ["api_client", "user_api_client"])
def test_rule_order_transactions_stay_restricted(
    client_fixture, request, order, transaction_item_generator
):
    # given
    client = request.getfixturevalue(client_fixture)
    transaction = transaction_item_generator(
        order_id=order.pk,
        charged_value=Decimal("20.00"),
        refunded_value=Decimal("5.00"),
        psp_reference="psp-secret-reference",
    )
    _event(
        transaction,
        TransactionEventType.REFUND_SUCCESS,
        "5.00",
        timezone.now(),
        "psp-secret-event",
    )

    # when
    response = _query(client, order, TRANSACTIONS_QUERY)

    # then
    assert_no_permission(response)
    content = get_graphql_content_from_response(response)
    assert content["data"]["order"] is None
    assert "psp-secret" not in response.content.decode()


def _unwrap_type_name(graphql_type):
    while graphql_type["name"] is None:
        graphql_type = graphql_type["ofType"]
    return graphql_type["name"]


def _fields(client, type_name):
    response = client.post_graphql(TYPE_QUERY, {"name": type_name})
    content = get_graphql_content(response)
    return {f["name"]: f for f in content["data"]["__type"]["fields"]}


def test_rule_refund_entries_do_not_expose_internal_transaction_data(
    api_client, user_api_client
):
    # given
    summary_fields = _fields(api_client, "TransactionSummary")
    assert "refunds" in summary_fields
    entry_type_name = _unwrap_type_name(summary_fields["refunds"]["type"])

    # when
    entry_fields = _fields(api_client, entry_type_name)

    # then neither the summary nor the refund entries leak internal data
    assert set(summary_fields) & INTERNAL_FIELDS == set()
    assert {"amount", "createdAt"} <= set(entry_fields)
    assert set(entry_fields) & INTERNAL_FIELDS == set()
