from django.contrib.sites.models import Site

from saleor.graphql.api import schema
from saleor.graphql.context import get_context_value
from saleor.graphql.tests.utils import get_graphql_content
from saleor.site.models import SiteSettings

QUERY = """
    query($token: UUID!) {
      checkout(token: $token) {
        token
        lineQuantityLimit
      }
    }
"""


def test_behavior_returns_shop_limit(api_client, checkout, site_settings):
    site_settings.limit_quantity_per_checkout = 7
    site_settings.save(update_fields=["limit_quantity_per_checkout"])

    content = get_graphql_content(
        api_client.post_graphql(QUERY, {"token": str(checkout.token)})
    )

    assert content["data"]["checkout"]["lineQuantityLimit"] == 7


def test_behavior_follows_setting_changes(api_client, checkout, site_settings):
    for value in (5, 12):
        site_settings.limit_quantity_per_checkout = value
        site_settings.save(update_fields=["limit_quantity_per_checkout"])
        content = get_graphql_content(
            api_client.post_graphql(QUERY, {"token": str(checkout.token)})
        )
        assert content["data"]["checkout"]["lineQuantityLimit"] == value


def test_rule_second_site_gets_its_own_limit(checkout, site_settings, settings, rf):
    # a deployment serving several sites: no fixed SITE_ID, the site comes from the host
    site_settings.limit_quantity_per_checkout = 9
    site_settings.save(update_fields=["limit_quantity_per_checkout"])
    other_site = Site.objects.create(domain="second.example.com", name="Second")
    other_settings, _ = SiteSettings.objects.get_or_create(site=other_site)
    other_settings.limit_quantity_per_checkout = 3
    other_settings.save(update_fields=["limit_quantity_per_checkout"])

    settings.SITE_ID = None
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, other_site.domain]
    request = rf.post("/graphql/", HTTP_HOST=other_site.domain)
    context = get_context_value(request)
    result = schema.execute(
        QUERY, variables={"token": str(checkout.token)}, context_value=context
    )

    assert result.errors is None
    assert result.data["checkout"]["lineQuantityLimit"] == 3


def test_rule_other_site_selected_by_site_id(
    api_client, checkout, site_settings, settings
):
    site_settings.limit_quantity_per_checkout = 9
    site_settings.save(update_fields=["limit_quantity_per_checkout"])
    other_site = Site.objects.create(domain="third.example.com", name="Third")
    other_settings, _ = SiteSettings.objects.get_or_create(site=other_site)
    other_settings.limit_quantity_per_checkout = 4
    other_settings.save(update_fields=["limit_quantity_per_checkout"])

    settings.SITE_ID = other_site.pk
    content = get_graphql_content(
        api_client.post_graphql(QUERY, {"token": str(checkout.token)})
    )

    assert content["data"]["checkout"]["lineQuantityLimit"] == 4
