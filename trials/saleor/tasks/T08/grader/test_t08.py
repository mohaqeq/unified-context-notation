import datetime

import graphene
import pytest

from saleor.graphql.tests.utils import get_graphql_content

QUERY = """
query GiftCard($id: ID!) {
  giftCard(id: $id) {
    isExpired
    expiryDate
  }
}
"""


def _today():
    return datetime.datetime.now(tz=datetime.UTC).date()


def _is_expired(client, gift_card, permission):
    client.user.user_permissions.add(permission)
    variables = {"id": graphene.Node.to_global_id("GiftCard", gift_card.pk)}
    response = client.post_graphql(QUERY, variables)
    return get_graphql_content(response)["data"]["giftCard"]["isExpired"]


@pytest.mark.parametrize(
    ("_case", "days_from_today", "expected"),
    [
        ("expired_yesterday", -1, True),
        ("expired_long_ago", -400, True),
        ("expires_today", 0, False),
        ("expires_tomorrow", 1, False),
        ("expires_next_year", 365, False),
        ("no_expiry_date", None, False),
    ],
)
def test_behavior_is_expired(
    _case,
    days_from_today,
    expected,
    staff_api_client,
    permission_manage_gift_card,
    gift_card,
):
    # given
    gift_card.expiry_date = (
        None
        if days_from_today is None
        else _today() + datetime.timedelta(days=days_from_today)
    )
    gift_card.save(update_fields=["expiry_date"])

    # when
    is_expired = _is_expired(staff_api_client, gift_card, permission_manage_gift_card)

    # then
    assert is_expired is expected


def test_behavior_is_expired_ignores_active_flag_and_balance(
    staff_api_client, permission_manage_gift_card, gift_card
):
    # given
    gift_card.expiry_date = _today() - datetime.timedelta(days=2)
    gift_card.is_active = False
    gift_card.current_balance_amount = 0
    gift_card.save(update_fields=["expiry_date", "is_active", "current_balance_amount"])

    # when
    is_expired = _is_expired(staff_api_client, gift_card, permission_manage_gift_card)

    # then
    assert is_expired is True
