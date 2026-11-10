import datetime

import graphene
import pytest
from django.utils import timezone

from saleor.account.models import User
from saleor.graphql.tests.utils import get_graphql_content
from saleor.order.models import Order

ADD_PROMO_CODE = """
    mutation($id: ID, $promoCode: String!) {
        checkoutAddPromoCode(id: $id, promoCode: $promoCode) {
            errors { field code message }
        }
    }
"""


def delete_dormant_customers(cutoff):
    from saleor.account import tasks

    return tasks.delete_dormant_customers(cutoff)


def _now():
    return timezone.now()


def _make_user(email, *, last_login=None, joined_days_ago=0, is_staff=False):
    user = User.objects.create(
        email=email,
        is_active=True,
        is_staff=is_staff,
        last_login=last_login,
    )
    User.objects.filter(pk=user.pk).update(
        date_joined=_now() - datetime.timedelta(days=joined_days_ago)
    )
    user.refresh_from_db()
    return user


def _cutoff():
    return _now() - datetime.timedelta(days=365)


def _exists(user):
    return User.objects.filter(pk=user.pk).exists()


def test_behavior_deletes_customers_whose_last_login_is_before_cutoff(db):
    # given
    stale = _make_user(
        "stale@example.com",
        last_login=_now() - datetime.timedelta(days=500),
        joined_days_ago=900,
    )
    recent = _make_user(
        "recent@example.com",
        last_login=_now() - datetime.timedelta(days=5),
        joined_days_ago=900,
    )

    # when
    deleted = delete_dormant_customers(_cutoff())

    # then
    assert deleted == 1
    assert _exists(stale) is False
    assert _exists(recent) is True


def test_behavior_never_logged_in_customers_are_judged_by_join_date(db):
    # given
    old_never_logged_in = _make_user("old-nl@example.com", joined_days_ago=800)
    new_never_logged_in = _make_user("new-nl@example.com", joined_days_ago=10)

    # when
    deleted = delete_dormant_customers(_cutoff())

    # then
    assert deleted == 1
    assert _exists(old_never_logged_in) is False
    assert _exists(new_never_logged_in) is True


def test_behavior_staff_and_customers_with_orders_are_kept(db, order):
    # given
    old_staff = _make_user(
        "old-staff@example.com",
        last_login=_now() - datetime.timedelta(days=900),
        joined_days_ago=1200,
        is_staff=True,
    )
    buyer = _make_user(
        "old-buyer@example.com",
        last_login=_now() - datetime.timedelta(days=900),
        joined_days_ago=1200,
    )
    order.user = buyer
    order.save(update_fields=["user"])

    # when
    deleted = delete_dormant_customers(_cutoff())

    # then
    assert deleted == 0
    assert _exists(old_staff) is True
    assert _exists(buyer) is True
    assert Order.objects.filter(pk=order.pk, user=buyer).exists() is True


def test_behavior_returns_zero_when_nothing_is_dormant(db):
    # given
    _make_user(
        "active@example.com",
        last_login=_now() - datetime.timedelta(days=1),
        joined_days_ago=30,
    )

    # when
    deleted = delete_dormant_customers(_cutoff())

    # then
    assert deleted == 0


def test_rule_card_of_deleted_dormant_customer_stays_restricted(
    api_client, checkout_with_item, gift_card, gift_card_created_by_staff
):
    # given: one card restricted to a dormant customer, one ordinary bearer card
    dormant = _make_user(
        "dormant-owner@example.com",
        last_login=_now() - datetime.timedelta(days=700),
        joined_days_ago=900,
    )
    restricted = gift_card
    restricted.assigned_to = dormant
    restricted.assigned_to_email = dormant.email
    restricted.save(update_fields=["assigned_to", "assigned_to_email"])
    bearer = gift_card_created_by_staff
    assert bearer.assigned_to_id is None
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)

    # when
    deleted = delete_dormant_customers(_cutoff())

    # then: the customer is gone and a guest can no longer spend the restricted card
    assert deleted == 1
    assert _exists(dormant) is False
    restricted.refresh_from_db()
    assert restricted.assigned_to_email == dormant.email

    response = api_client.post_graphql(
        ADD_PROMO_CODE, {"id": checkout_id, "promoCode": restricted.code}
    )
    errors = get_graphql_content(response)["data"]["checkoutAddPromoCode"]["errors"]
    assert len(errors) == 1
    assert checkout_with_item.gift_cards.exists() is False

    # the same request path still works for an ordinary bearer card
    response = api_client.post_graphql(
        ADD_PROMO_CODE, {"id": checkout_id, "promoCode": bearer.code}
    )
    errors = get_graphql_content(response)["data"]["checkoutAddPromoCode"]["errors"]
    assert errors == []
    assert list(checkout_with_item.gift_cards.all()) == [bearer]


@pytest.mark.parametrize("_case", ["inactive_card", "active_card"])
def test_rule_restriction_is_kept_whatever_the_card_state(
    _case, user_api_client, checkout_with_item, gift_card
):
    # given a restricted card owned by a dormant customer, spent by someone else
    dormant = _make_user(
        "dormant-owner2@example.com",
        last_login=_now() - datetime.timedelta(days=700),
        joined_days_ago=900,
    )
    gift_card.assigned_to = dormant
    gift_card.assigned_to_email = dormant.email
    gift_card.is_active = _case == "active_card"
    gift_card.save(update_fields=["assigned_to", "assigned_to_email", "is_active"])
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)

    # when
    delete_dormant_customers(_cutoff())

    # then
    response = user_api_client.post_graphql(
        ADD_PROMO_CODE, {"id": checkout_id, "promoCode": gift_card.code}
    )
    errors = get_graphql_content(response)["data"]["checkoutAddPromoCode"]["errors"]
    assert len(errors) == 1
    assert checkout_with_item.gift_cards.exists() is False
