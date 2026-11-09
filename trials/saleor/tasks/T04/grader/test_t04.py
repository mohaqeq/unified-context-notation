import sys
import weakref
from decimal import Decimal

import graphene
import pytest
from django.db.models import signals

from saleor.graphql.tests.utils import get_graphql_content

MUTATION = """
    mutation GiftCardBalanceAdjust($id: ID!, $amount: Decimal!) {
        giftCardBalanceAdjust(id: $id, amount: $amount) {
            giftCard { id isActive currentBalance { amount } }
            errors { field code message }
        }
    }
"""

# Receivers that the code base already had before this change.
EXISTING_SALEOR_RECEIVERS = {
    ("post_delete", "saleor.account.signals", "delete_avatar"),
    ("post_delete", "saleor.product.signals", "delete_background_image"),
    ("post_delete", "saleor.product.signals", "delete_product_media_image"),
    ("post_delete", "saleor.app.signals", "delete_brand_images"),
    ("post_delete", "saleor.thumbnail.signals", "delete_thumbnail_image"),
}

MODEL_SIGNALS = ("pre_init", "post_init", "pre_save", "post_save", "pre_delete")
MODEL_SIGNALS += ("post_delete", "m2m_changed")


def _charge(gift_card, amount, order):
    from saleor.giftcard import gateway

    gateway.charge_gift_card(gift_card, Decimal(amount), order)
    gift_card.refresh_from_db()


def _adjust(client, gift_card, amount, permission):
    variables = {
        "id": graphene.Node.to_global_id("GiftCard", gift_card.pk),
        "amount": str(amount),
    }
    client.user.user_permissions.add(permission)
    response = client.post_graphql(MUTATION, variables)
    data = get_graphql_content(response)["data"]["giftCardBalanceAdjust"]
    gift_card.refresh_from_db()
    return data


def test_behavior_charging_deactivates_card_only_once_balance_is_zero(
    gift_card, order
):
    # given
    assert gift_card.is_active is True
    assert gift_card.current_balance_amount == Decimal(10)

    # when part of the balance is spent
    _charge(gift_card, "4.00", order)

    # then
    assert gift_card.current_balance_amount == Decimal(6)
    assert gift_card.is_active is True

    # when the rest is spent
    _charge(gift_card, "6.00", order)

    # then
    assert gift_card.current_balance_amount == Decimal(0)
    assert gift_card.is_active is False


@pytest.mark.parametrize(
    ("_case", "first_amount", "second_amount"),
    [
        ("deduction_then_exact_zero", "-3.00", "-7.00"),
        ("top_up_then_exact_zero", "5.00", "-15.00"),
        ("deduction_then_larger_than_balance", "-3.00", "-500.00"),
    ],
)
def test_behavior_adjustment_deactivates_card_only_once_balance_is_zero(
    _case,
    first_amount,
    second_amount,
    staff_api_client,
    gift_card,
    permission_manage_gift_card,
):
    # given
    assert gift_card.is_active is True

    # when the adjustment leaves a positive balance
    data = _adjust(
        staff_api_client, gift_card, first_amount, permission_manage_gift_card
    )

    # then
    assert data["errors"] == []
    assert data["giftCard"]["isActive"] is True
    assert gift_card.is_active is True
    assert gift_card.current_balance_amount > 0

    # when the adjustment takes the balance to zero
    data = _adjust(
        staff_api_client, gift_card, second_amount, permission_manage_gift_card
    )

    # then
    assert data["errors"] == []
    assert data["giftCard"]["currentBalance"]["amount"] == 0.0
    assert data["giftCard"]["isActive"] is False
    assert gift_card.current_balance_amount == Decimal(0)
    assert gift_card.is_active is False


def _saleor_receivers():
    found = set()
    for name in MODEL_SIGNALS:
        signal = getattr(signals, name)
        for entry in list(signal.receivers):
            receiver = entry[1]
            if isinstance(receiver, weakref.ref):
                receiver = receiver()
            module = getattr(receiver, "__module__", None) or ""
            if receiver is None or not module.startswith("saleor."):
                continue
            if module.startswith("saleor.hidden_tests"):
                continue
            found.add((name, module, getattr(receiver, "__name__", repr(receiver))))
    return found


def test_rule_no_new_django_signal_receivers():
    # given: make sure every app module is loaded, as in a running server
    assert "saleor.giftcard.models" in sys.modules

    # when
    receivers = _saleor_receivers()

    # then
    assert receivers - EXISTING_SALEOR_RECEIVERS == set()
