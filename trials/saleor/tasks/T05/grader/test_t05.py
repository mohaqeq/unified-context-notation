import datetime
from unittest import mock

import pytest
from dateutil.relativedelta import relativedelta
from django.contrib.sites.models import Site
from django.utils import timezone

from saleor.core import TimePeriodType
from saleor.giftcard.models import GiftCard
from saleor.graphql.tests.utils import get_graphql_content
from saleor.site import GiftCardSettingsExpiryType
from saleor.site.models import SiteSettings

MUTATION = """
    mutation GiftCardCreate($input: GiftCardCreateInput!) {
        giftCardCreate(input: $input) {
            giftCard { id expiryDate }
            errors { field code message }
        }
    }
"""


def _today():
    return timezone.now().date()


def _input(**extra):
    return {
        "balance": {"amount": 25, "currency": "USD"},
        "isActive": True,
        **extra,
    }


def _create(client, permission, **extra):
    client.user.user_permissions.add(permission)
    response = client.post_graphql(MUTATION, {"input": _input(**extra)})
    data = get_graphql_content(response)["data"]["giftCardCreate"]
    assert data["errors"] == []
    return data["giftCard"]


def _set_expiry_period(site_settings, amount, period_type):
    site_settings.gift_card_expiry_type = GiftCardSettingsExpiryType.EXPIRY_PERIOD
    site_settings.gift_card_expiry_period_type = period_type
    site_settings.gift_card_expiry_period = amount
    site_settings.save(
        update_fields=[
            "gift_card_expiry_type",
            "gift_card_expiry_period_type",
            "gift_card_expiry_period",
        ]
    )
    Site.objects.clear_cache()


@pytest.mark.parametrize(
    ("_case", "extra"), [("omitted", {}), ("explicit_null", {"expiryDate": None})]
)
def test_behavior_default_expiry_applied_when_no_date_given(
    _case, extra, staff_api_client, permission_manage_gift_card, site_settings
):
    # given
    _set_expiry_period(site_settings, 6, TimePeriodType.MONTH)

    # when
    created = _create(staff_api_client, permission_manage_gift_card, **extra)

    # then
    expected = _today() + relativedelta(months=6)
    assert created["expiryDate"] == expected.isoformat()
    assert GiftCard.objects.get().expiry_date == expected


def test_behavior_follows_current_settings_and_keeps_explicit_dates(
    staff_api_client, permission_manage_gift_card, site_settings
):
    # given a shop whose cards never expire
    assert site_settings.gift_card_expiry_type == GiftCardSettingsExpiryType.NEVER_EXPIRE

    # when
    never = _create(staff_api_client, permission_manage_gift_card)

    # then
    assert never["expiryDate"] is None

    # given the shop switches to a 6 months expiry
    _set_expiry_period(site_settings, 6, TimePeriodType.MONTH)

    # when
    defaulted = _create(staff_api_client, permission_manage_gift_card)
    explicit_date = _today() + datetime.timedelta(days=10)
    explicit = _create(
        staff_api_client,
        permission_manage_gift_card,
        expiryDate=explicit_date.isoformat(),
    )

    # then
    assert defaulted["expiryDate"] == (_today() + relativedelta(months=6)).isoformat()
    assert explicit["expiryDate"] == explicit_date.isoformat()
    assert GiftCard.objects.filter(expiry_date__isnull=True).count() == 1


def test_behavior_period_unit_is_respected(
    staff_api_client, permission_manage_gift_card, site_settings
):
    # given
    _set_expiry_period(site_settings, 3, TimePeriodType.WEEK)

    # when
    created = _create(staff_api_client, permission_manage_gift_card)

    # then
    assert created["expiryDate"] == (_today() + relativedelta(weeks=3)).isoformat()


def test_rule_expiry_comes_from_the_site_resolved_for_the_request(
    staff_api_client, permission_manage_gift_card, site_settings, settings
):
    # given a deployment where SITE_ID is not configured and the site is chosen by
    # the request host, with another site present that must not be used
    other_site = Site.objects.get(pk=site_settings.site_id)
    other_site.domain = "other-shop.example.com"
    other_site.save(update_fields=["domain"])
    _set_expiry_period(site_settings, 12, TimePeriodType.MONTH)

    request_host = "testserver"
    request_site = Site.objects.create(domain=request_host, name="request host site")
    SiteSettings.objects.create(
        site=request_site,
        gift_card_expiry_type=GiftCardSettingsExpiryType.EXPIRY_PERIOD,
        gift_card_expiry_period_type=TimePeriodType.MONTH,
        gift_card_expiry_period=2,
    )
    settings.SITE_ID = None
    Site.objects.clear_cache()

    try:
        # when
        with mock.patch(
            "saleor.graphql.views.is_storefront_traffic_blocked", return_value=False
        ):
            created = _create(staff_api_client, permission_manage_gift_card)
    finally:
        Site.objects.clear_cache()

    # then
    assert created["expiryDate"] == (_today() + relativedelta(months=2)).isoformat()
