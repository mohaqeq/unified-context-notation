from io import StringIO

import pytest
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.signals import post_save, pre_save

from saleor.site.models import SiteSettings


@pytest.fixture(autouse=True)
def site_settings(db, settings):
    """Same as the shared fixture, but tolerant of however settings rows get created."""
    site = Site.objects.get_or_create(
        domain="example.com", defaults={"name": "example.com"}
    )[0]
    settings_row = SiteSettings.objects.get_or_create(
        site=site, defaults={"default_mail_sender_name": "Example"}
    )[0]
    settings.SITE_ID = site.pk
    settings.ALLOWED_HOSTS += [site.domain]
    return settings_row


def run_create_site(domain, name):
    out = StringIO()
    call_command("create_site", domain, name, stdout=out)
    return out.getvalue()


def test_behavior_creates_site_with_default_settings(site_settings):
    domain, name = "tenant.example.com", "Tenant shop"

    output = run_create_site(domain, name)

    site = Site.objects.get(domain=domain)
    assert site.name == name
    assert domain in output
    settings_row = SiteSettings.objects.get(site=site)
    assert settings_row.allow_storefront_traffic is True
    assert settings_row.top_menu is None


def test_behavior_existing_site_untouched(site_settings):
    original_name = site_settings.site.name
    original_mail_sender = site_settings.default_mail_sender_name
    sites = Site.objects.count()
    settings_rows = SiteSettings.objects.count()

    run_create_site("tenant.example.com", "Tenant shop")

    assert Site.objects.count() == sites + 1
    assert SiteSettings.objects.count() == settings_rows + 1
    site_settings.refresh_from_db()
    assert site_settings.site.name == original_name
    assert site_settings.default_mail_sender_name == original_mail_sender


@pytest.mark.parametrize("domain", ["tenant.example.com", "TENANT.example.com"])
def test_behavior_duplicate_domain_fails_without_side_effects(site_settings, domain):
    run_create_site("tenant.example.com", "Tenant shop")
    sites = Site.objects.count()
    settings_rows = SiteSettings.objects.count()

    with pytest.raises(CommandError):
        run_create_site(domain, "Another name")

    assert Site.objects.count() == sites
    assert SiteSettings.objects.count() == settings_rows


def saleor_receivers(signal, sender):
    live = signal._live_receivers(sender)
    receivers = [r for part in live for r in part] if isinstance(live, tuple) else live
    return [r for r in receivers if getattr(r, "__module__", "").startswith("saleor")]


@pytest.mark.parametrize("signal", [pre_save, post_save])
@pytest.mark.parametrize("sender", [Site, SiteSettings])
def test_rule_no_signal_receivers_on_site_models(signal, sender):
    assert saleor_receivers(signal, sender) == []
