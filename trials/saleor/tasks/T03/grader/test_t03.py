import re
from decimal import Decimal

import graphene
from django.db import connection
from django.test.utils import CaptureQueriesContext

from saleor.core.prices import Money
from saleor.giftcard import GiftCardEvents
from saleor.giftcard.error_codes import GiftCardErrorCode
from saleor.giftcard.models import GiftCard
from saleor.graphql.tests.utils import assert_no_permission, get_graphql_content

MUTATION = """
    mutation GiftCardBulkBalanceAdjust($ids: [ID!]!, $amount: Decimal!) {
        giftCardBulkBalanceAdjust(ids: $ids, amount: $amount) {
            giftCards {
                id
                currentBalance { amount }
                initialBalance { amount }
            }
            errors { field code message }
        }
    }
"""


def _card(code, current, initial):
    return GiftCard.objects.create(
        code=code,
        initial_balance=Money(Decimal(initial), "USD"),
        current_balance=Money(Decimal(current), "USD"),
    )


def _ids(*cards):
    return [graphene.Node.to_global_id("GiftCard", card.pk) for card in cards]


def _adjust(client, cards, amount, permissions=()):
    variables = {"ids": _ids(*cards), "amount": str(amount)}
    return client.post_graphql(MUTATION, variables, permissions=list(permissions))


def _balances(card):
    card.refresh_from_db()
    return card.current_balance_amount, card.initial_balance_amount


def test_behavior_applies_the_same_delta_to_every_card(
    staff_api_client, permission_manage_gift_card
):
    # given
    first = _card("bulk_card_1", "50.00", "100.00")
    second = _card("bulk_card_2", "7.50", "20.00")

    # when
    response = _adjust(
        staff_api_client, [first, second], "5.00", [permission_manage_gift_card]
    )

    # then
    data = get_graphql_content(response)["data"]["giftCardBulkBalanceAdjust"]
    assert data["errors"] == []
    returned = {c["id"]: c for c in data["giftCards"]}
    assert set(returned) == set(_ids(first, second))
    first_id, second_id = _ids(first, second)
    assert returned[first_id]["currentBalance"]["amount"] == 55.0
    assert returned[second_id]["currentBalance"]["amount"] == 12.5
    assert _balances(first) == (Decimal("55.00"), Decimal("100.00"))
    assert _balances(second) == (Decimal("12.50"), Decimal("20.00"))
    for card in (first, second):
        assert card.events.filter(type=GiftCardEvents.BALANCE_ADJUSTED).count() == 1


def test_behavior_deduction_clamps_each_card_to_zero(
    staff_api_client, permission_manage_gift_card
):
    # given
    small = _card("bulk_small", "3.00", "10.00")
    large = _card("bulk_large", "30.00", "30.00")

    # when
    response = _adjust(
        staff_api_client, [small, large], "-10.00", [permission_manage_gift_card]
    )

    # then
    data = get_graphql_content(response)["data"]["giftCardBulkBalanceAdjust"]
    assert data["errors"] == []
    assert _balances(small) == (Decimal("0.00"), Decimal("10.00"))
    assert _balances(large) == (Decimal("20.00"), Decimal("30.00"))


def test_behavior_top_up_above_initial_raises_initial(
    staff_api_client, permission_manage_gift_card
):
    # given
    near_full = _card("bulk_near_full", "95.00", "100.00")
    half = _card("bulk_half", "50.00", "100.00")

    # when
    response = _adjust(
        staff_api_client, [near_full, half], "10.00", [permission_manage_gift_card]
    )

    # then
    data = get_graphql_content(response)["data"]["giftCardBulkBalanceAdjust"]
    assert data["errors"] == []
    assert _balances(near_full) == (Decimal("105.00"), Decimal("105.00"))
    assert _balances(half) == (Decimal("60.00"), Decimal("100.00"))


def test_behavior_zero_amount_is_rejected(
    staff_api_client, permission_manage_gift_card
):
    # given
    first = _card("bulk_zero_1", "50.00", "100.00")
    second = _card("bulk_zero_2", "10.00", "10.00")

    # when
    response = _adjust(
        staff_api_client, [first, second], "0", [permission_manage_gift_card]
    )

    # then
    data = get_graphql_content(response)["data"]["giftCardBulkBalanceAdjust"]
    assert len(data["errors"]) == 1
    assert data["errors"][0]["field"] == "amount"
    assert data["errors"][0]["code"] == GiftCardErrorCode.INVALID.name
    assert _balances(first) == (Decimal("50.00"), Decimal("100.00"))
    assert _balances(second) == (Decimal("10.00"), Decimal("10.00"))
    assert first.events.filter(type=GiftCardEvents.BALANCE_ADJUSTED).exists() is False


def test_behavior_requires_manage_gift_card(staff_api_client):
    # given
    card = _card("bulk_perm", "50.00", "100.00")

    # when
    response = _adjust(staff_api_client, [card], "5.00")

    # then
    assert_no_permission(response)
    assert _balances(card) == (Decimal("50.00"), Decimal("100.00"))


def _is_update(sql):
    return sql.lstrip().upper().startswith("UPDATE")


def _is_self_referencing_update(sql):
    match = re.search(
        r'"current_balance_amount"\s*=\s*(.*?)(?:,\s*"[a-z_]+"\s*=|\s+WHERE)',
        sql,
        re.S,
    )
    return bool(match) and "current_balance_amount" in match.group(1)


def test_rule_balance_is_changed_atomically_not_read_modify_write(
    staff_api_client, permission_manage_gift_card
):
    # given
    first = _card("bulk_atomic_1", "50.00", "100.00")
    second = _card("bulk_atomic_2", "20.00", "100.00")
    staff_api_client.user.user_permissions.add(permission_manage_gift_card)
    variables = {"ids": _ids(first, second), "amount": "5.00"}

    # when
    with CaptureQueriesContext(connection) as captured:
        response = staff_api_client.post_graphql(MUTATION, variables)

    # then the request worked
    data = get_graphql_content(response)["data"]["giftCardBulkBalanceAdjust"]
    assert data["errors"] == []
    assert _balances(first)[0] == Decimal("55.00")
    assert _balances(second)[0] == Decimal("25.00")

    # and every write to the balance is either an UPDATE computed in the database
    # from the stored value, or happens after the rows were locked FOR UPDATE
    statements = [
        q["sql"] for q in captured.captured_queries if "giftcard_giftcard" in q["sql"]
    ]
    balance_updates = [
        sql for sql in statements if _is_update(sql) and '"current_balance_amount"' in sql
    ]
    assert balance_updates, "no UPDATE of the balance was issued"
    first_update_index = statements.index(balance_updates[0])
    locked_before_update = any(
        sql.lstrip().upper().startswith("SELECT") and "FOR UPDATE" in sql.upper()
        for sql in statements[:first_update_index]
    )
    assert locked_before_update or all(
        _is_self_referencing_update(sql) for sql in balance_updates
    )
