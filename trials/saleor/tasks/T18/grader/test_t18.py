import pytest

from saleor.graphql.storefront_traffic import clear_allow_storefront_traffic_cache

QUERY = "{ __typename }"


@pytest.fixture
def set_flag(site_settings):
    def _set(allowed):
        site_settings.allow_storefront_traffic = allowed
        site_settings.save(update_fields=["allow_storefront_traffic"])
        clear_allow_storefront_traffic_cache()

    yield _set
    clear_allow_storefront_traffic_cache()


@pytest.mark.parametrize("client_fixture", ["api_client", "user_api_client"])
def test_behavior_rejection_is_not_cacheable(client_fixture, request, set_flag):
    client = request.getfixturevalue(client_fixture)
    set_flag(False)

    response = client.post_graphql(QUERY)

    assert response.status_code == 401
    assert response.json()["errors"][0]["extensions"]["code"] == (
        "STOREFRONT_TRAFFIC_NOT_ALLOWED"
    )
    assert response["Cache-Control"] == "no-store"


@pytest.mark.parametrize("client_fixture", ["app_api_client", "staff_api_client"])
def test_unchanged_privileged_requests_do_not_get_the_header(
    client_fixture, request, set_flag
):
    client = request.getfixturevalue(client_fixture)
    set_flag(False)

    response = client.post_graphql(QUERY)

    assert response.status_code == 200
    assert response.json()["data"] == {"__typename": "Query"}
    assert response.get("Cache-Control") != "no-store"


def test_unchanged_allowed_traffic_does_not_get_the_header(api_client, set_flag):
    set_flag(True)

    response = api_client.post_graphql(QUERY)

    assert response.status_code == 200
    assert response.get("Cache-Control") != "no-store"
