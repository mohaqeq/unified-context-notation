import graphene

from saleor.graphql.tests.utils import get_graphql_content
from saleor.thumbnail.utils import get_thumbnail_size

SIZE = 700  # between 512 and 1024, closer to 512


def thumbnail_url(category, query="", format=None):
    category_id = graphene.Node.to_global_id("Category", category.id)
    path = f"/thumbnail/{category_id}/{SIZE}/"
    if format:
        path += f"{format}/"
    return path + query


def test_behavior_rounding_nearest(client, category_with_image, settings):
    response = client.get(thumbnail_url(category_with_image, "?rounding=nearest"))
    assert response.status_code == 302
    file_path, ext = category_with_image.background_image.name.rsplit(".")
    assert (
        response.url
        == settings.MEDIA_URL + f"thumbnails/{file_path}_thumbnail_512.{ext}"
    )


def test_behavior_rounding_is_case_insensitive(
    client, category_with_image, settings
):
    response = client.get(thumbnail_url(category_with_image, "?rounding=NEAREST"))
    assert response.status_code == 302
    assert "_thumbnail_512." in response.url


def test_unchanged_rounding_up(client, category_with_image, settings):
    response = client.get(thumbnail_url(category_with_image, "?rounding=up"))
    assert response.status_code == 302
    assert "_thumbnail_1024." in response.url


def test_behavior_rounding_with_format(client, category_with_image, settings):
    response = client.get(
        thumbnail_url(category_with_image, "?rounding=nearest", format="webp")
    )
    assert response.status_code == 302
    assert response.url.endswith("_thumbnail_512.webp")


def test_behavior_unknown_rounding_is_404(client, category_with_image):
    response = client.get(thumbnail_url(category_with_image, "?rounding=sideways"))
    assert response.status_code == 404


def test_rule_without_parameter_still_rounds_up(client, category_with_image):
    response = client.get(thumbnail_url(category_with_image))
    assert response.status_code == 302
    assert "_thumbnail_1024." in response.url


def test_rule_graphql_thumbnail_without_size_rounding_rounds_up(
    api_client, category_with_image
):
    query = """
        query($id: ID!, $size: Int) {
          category(id: $id) {
            backgroundImage(size: $size) { url }
          }
        }
    """
    variables = {
        "id": graphene.Node.to_global_id("Category", category_with_image.id),
        "size": SIZE,
    }
    content = get_graphql_content(api_client.post_graphql(query, variables))
    url = content["data"]["category"]["backgroundImage"]["url"]
    assert f"/thumbnail/{variables['id']}/1024/" in url


def test_rule_default_size_matching_rounds_up():
    assert get_thumbnail_size(SIZE) == 1024
    assert get_thumbnail_size(1025) == 2048
