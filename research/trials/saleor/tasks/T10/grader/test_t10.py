from decimal import Decimal

import graphene
import pytest

from saleor.graphql.tests.utils import get_graphql_content
from saleor.payment import PaymentMethodType

QUERY = """
query Order($id: ID!) {
  order(id: $id) {
    hasGiftCardPayment
  }
}
"""


def _has_gift_card_payment(client, order):
    variables = {"id": graphene.Node.to_global_id("Order", order.pk)}
    response = client.post_graphql(QUERY, variables)
    return get_graphql_content(response)["data"]["order"]["hasGiftCardPayment"]


@pytest.mark.parametrize("client_fixture", ["api_client", "user_api_client"])
def test_behavior_true_when_a_transaction_was_paid_with_a_gift_card(
    client_fixture, request, order, transaction_item_generator
):
    # given
    client = request.getfixturevalue(client_fixture)
    transaction_item_generator(
        order_id=order.pk,
        charged_value=Decimal("10.00"),
        payment_method_type=PaymentMethodType.CARD,
        payment_method_name="Credit card",
        psp_reference="card-1",
    )
    assert _has_gift_card_payment(client, order) is False
    transaction_item_generator(
        order_id=order.pk,
        charged_value=Decimal("5.00"),
        payment_method_type=PaymentMethodType.GIFT_CARD,
        payment_method_name="Gift card",
        psp_reference="gift-1",
    )

    # when
    result = _has_gift_card_payment(client, order)

    # then
    assert result is True


def test_behavior_false_without_transactions(api_client, order):
    # when
    result = _has_gift_card_payment(api_client, order)

    # then
    assert result is False
