import datetime

import pytest

from saleor.core.prices import Money
from saleor.giftcard.models import GiftCard
from saleor.graphql.tests.utils import get_graphql_content

QUERY = """
query GiftCards($filter: GiftCardFilterInput) {
  giftCards(first: 20, filter: $filter) {
    edges { node { code } }
  }
}
"""


def _today():
    return datetime.datetime.now(tz=datetime.UTC).date()


def _card(code, days_from_today, is_active=True):
    return GiftCard.objects.create(
        code=code,
        is_active=is_active,
        initial_balance=Money(10, "USD"),
        current_balance=Money(10, "USD"),
        expiry_date=None
        if days_from_today is None
        else _today() + datetime.timedelta(days=days_from_today),
    )


def _codes(client, permission, filter_input):
    client.user.user_permissions.add(permission)
    response = client.post_graphql(QUERY, {"filter": filter_input})
    content = get_graphql_content(response)
    return {edge["node"]["code"] for edge in content["data"]["giftCards"]["edges"]}


@pytest.fixture
def cards(db):
    return {
        "soon": _card("expires_soon", 5),
        "later": _card("expires_later", 60),
        "boundary": _card("on_boundary", 30),
        "past": _card("expired_past", -3),
        "never": _card("never_expires", None),
        "soon_inactive": _card("soon_inactive", 7, is_active=False),
    }


def test_behavior_returns_cards_expiring_strictly_before_date(
    staff_api_client, permission_manage_gift_card, cards
):
    # given
    boundary = (_today() + datetime.timedelta(days=30)).isoformat()

    # when
    codes = _codes(
        staff_api_client, permission_manage_gift_card, {"expiresBefore": boundary}
    )

    # then
    assert codes == {"expires_soon", "expired_past", "soon_inactive"}


def test_behavior_combines_with_other_filters(
    staff_api_client, permission_manage_gift_card, cards
):
    # given
    limit = (_today() + datetime.timedelta(days=45)).isoformat()

    # when
    codes = _codes(
        staff_api_client,
        permission_manage_gift_card,
        {"expiresBefore": limit, "isActive": True},
    )

    # then
    assert codes == {"expires_soon", "expired_past", "on_boundary"}


@pytest.mark.parametrize(
    ("_case", "filter_input"),
    [("omitted", {}), ("null", {"expiresBefore": None})],
)
def test_behavior_without_a_date_the_result_is_unchanged(
    _case, filter_input, staff_api_client, permission_manage_gift_card, cards
):
    # when
    codes = _codes(staff_api_client, permission_manage_gift_card, filter_input)

    # then
    assert codes == {card.code for card in cards.values()}
    # and the filter does apply when a date is given, never excluding by absence
    far = (_today() + datetime.timedelta(days=3650)).isoformat()
    with_date = _codes(
        staff_api_client, permission_manage_gift_card, {"expiresBefore": far}
    )
    assert with_date == {card.code for card in cards.values()} - {"never_expires"}
