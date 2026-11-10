import graphene

from saleor.graphql.tests.utils import get_graphql_content
from saleor.product.models import Category

QUERY = """
    query($id: ID!) {
      category(id: $id) {
        descendantsCount
        children(first: 10) { edges { node { name descendantsCount } } }
      }
    }
"""


def gid(category):
    return graphene.Node.to_global_id("Category", category.pk)


def count_for(api_client, category):
    content = get_graphql_content(api_client.post_graphql(QUERY, {"id": gid(category)}))
    return content["data"]["category"]


def test_behavior_counts_all_levels(api_client):
    root = Category.objects.create(name="root", slug="root")
    first = Category.objects.create(name="first", slug="first", parent=root)
    Category.objects.create(name="second", slug="second", parent=root)
    grandchild = Category.objects.create(name="gc", slug="gc", parent=first)
    Category.objects.create(name="ggc", slug="ggc", parent=grandchild)
    Category.objects.create(name="other-root", slug="other-root")

    data = count_for(api_client, root)

    assert data["descendantsCount"] == 4
    by_name = {e["node"]["name"]: e["node"] for e in data["children"]["edges"]}
    assert by_name["first"]["descendantsCount"] == 2
    assert by_name["second"]["descendantsCount"] == 0


def test_behavior_leaf_has_zero(api_client):
    leaf = Category.objects.create(name="leaf", slug="leaf")

    assert count_for(api_client, leaf)["descendantsCount"] == 0


def test_behavior_follows_tree_changes(api_client):
    root = Category.objects.create(name="root", slug="root")
    child = Category.objects.create(name="child", slug="child", parent=root)
    assert count_for(api_client, root)["descendantsCount"] == 1

    Category.objects.create(name="grandchild", slug="grandchild", parent=child)
    assert count_for(api_client, root)["descendantsCount"] == 2

    child.delete()
    assert count_for(api_client, root)["descendantsCount"] == 0
