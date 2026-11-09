import datetime

import pytest

from saleor.graphql.tests.utils import get_graphql_content

QUERY = """
query GiftCardBalance($code: String!) {
  giftCardBalance(code: $code) {
    amount
    currency
  }
}
"""

UNKNOWN_CODE = "no-such-code-at-all"


def _balance(client, code):
    response = client.post_graphql(QUERY, {"code": code})
    return response, get_graphql_content(response)["data"]["giftCardBalance"]


@pytest.mark.parametrize("client_fixture", ["api_client", "user_api_client"])
def test_behavior_returns_balance_of_usable_card(client_fixture, request, gift_card):
    # given
    client = request.getfixturevalue(client_fixture)

    # when
    _, balance = _balance(client, gift_card.code)

    # then
    assert balance == {
        "amount": float(gift_card.current_balance_amount),
        "currency": gift_card.currency,
    }


def test_behavior_staff_can_read_balance(staff_api_client, gift_card):
    # when
    _, balance = _balance(staff_api_client, gift_card.code)

    # then
    assert balance == {
        "amount": float(gift_card.current_balance_amount),
        "currency": gift_card.currency,
    }


def test_behavior_unknown_code_returns_null(api_client):
    # when
    response, balance = _balance(api_client, UNKNOWN_CODE)

    # then
    assert balance is None
    assert "errors" not in response.json()


def test_behavior_reflects_current_balance(api_client, gift_card):
    # given
    gift_card.current_balance_amount = 3
    gift_card.save(update_fields=["current_balance_amount"])

    # when
    _, balance = _balance(api_client, gift_card.code)

    # then
    assert balance == {"amount": 3.0, "currency": gift_card.currency}


@pytest.mark.parametrize(
    ("_case", "fields"),
    [
        ("inactive", {"is_active": False}),
        (
            "expired",
            {
                "expiry_date": datetime.datetime.now(tz=datetime.UTC).date()
                - datetime.timedelta(days=1)
            },
        ),
    ],
)
def test_behavior_unusable_card_returns_null(_case, fields, api_client, gift_card):
    # given
    for name, value in fields.items():
        setattr(gift_card, name, value)
    gift_card.save(update_fields=list(fields))

    # when
    response, balance = _balance(api_client, gift_card.code)

    # then
    assert balance is None
    assert "errors" not in response.json()


@pytest.mark.parametrize("client_fixture", ["api_client", "user_api_client"])
def test_rule_card_restricted_to_another_customer_looks_like_unknown_code(
    client_fixture, request, gift_card, staff_user
):
    # given
    client = request.getfixturevalue(client_fixture)
    gift_card.assigned_to = staff_user
    gift_card.assigned_to_email = staff_user.email
    gift_card.save(update_fields=["assigned_to", "assigned_to_email"])
    baseline, _ = _balance(client, UNKNOWN_CODE)

    # when
    response, balance = _balance(client, gift_card.code)

    # then
    assert balance is None
    assert response.json() == baseline.json()


@pytest.mark.parametrize("client_fixture", ["api_client", "user_api_client"])
def test_rule_card_restricted_to_deleted_customer_looks_like_unknown_code(
    client_fixture, request, gift_card
):
    # given
    client = request.getfixturevalue(client_fixture)
    gift_card.assigned_to = None
    gift_card.assigned_to_email = "deleted-customer@example.com"
    gift_card.save(update_fields=["assigned_to", "assigned_to_email"])
    baseline, _ = _balance(client, UNKNOWN_CODE)

    # when
    response, balance = _balance(client, gift_card.code)

    # then
    assert balance is None
    assert response.json() == baseline.json()
