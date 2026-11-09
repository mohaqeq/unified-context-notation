import graphene
import pytest
from django.db import connection

from saleor.core.db.locks import AdvisoryLock
from saleor.graphql.tests.utils import get_graphql_content
from saleor.product.error_codes import ProductErrorCode
from saleor.product.models import Category

MUTATION_WITH_PARENT = """
    mutation($id: ID!, $parent: ID, $input: CategoryInput!) {
      categoryUpdate(id: $id, parent: $parent, input: $input) {
        errors { field code message }
        category { id name parent { id } level }
      }
    }
"""

MUTATION_WITHOUT_PARENT = """
    mutation($id: ID!, $input: CategoryInput!) {
      categoryUpdate(id: $id, input: $input) {
        errors { field code message }
        category { id name parent { id } level }
      }
    }
"""


def gid(category):
    return graphene.Node.to_global_id("Category", category.pk)


@pytest.fixture
def tree(db):
    """Two trees: A (A0, A1 (A1a)) and B."""
    root_a = Category.objects.create(name="A", slug="a")
    a0 = Category.objects.create(name="A0", slug="a0", parent=root_a)
    a1 = Category.objects.create(name="A1", slug="a1", parent=root_a)
    a1a = Category.objects.create(name="A1a", slug="a1a", parent=a1)
    root_b = Category.objects.create(name="B", slug="b")
    return {"a": root_a, "a0": a0, "a1": a1, "a1a": a1a, "b": root_b}


def assert_tree_is_consistent():
    categories = list(Category.objects.all())
    by_pk = {c.pk: c for c in categories}
    numbers_per_tree = {}
    for category in categories:
        if category.parent_id is None:
            assert category.level == 0
        else:
            parent = by_pk[category.parent_id]
            assert category.tree_id == parent.tree_id
            assert category.level == parent.level + 1
            assert parent.lft < category.lft < category.rght < parent.rght
        numbers_per_tree.setdefault(category.tree_id, []).extend(
            [category.lft, category.rght]
        )
    for tree_id, numbers in numbers_per_tree.items():
        assert sorted(numbers) == list(range(1, len(numbers) + 1)), tree_id


def move(client, permission, category, parent, **input_data):
    client.user.user_permissions.add(permission)
    return get_graphql_content(
        client.post_graphql(
            MUTATION_WITH_PARENT,
            {"id": gid(category), "parent": parent, "input": input_data},
        )
    )["data"]["categoryUpdate"]


def refresh_all(tree):
    for category in tree.values():
        category.refresh_from_db()


def test_behavior_move_subtree_under_other_tree(
    staff_api_client, permission_manage_products, tree
):
    data = move(
        staff_api_client,
        permission_manage_products,
        tree["a1"],
        gid(tree["b"]),
        name="A1 moved",
    )
    assert data["errors"] == []
    assert data["category"]["parent"]["id"] == gid(tree["b"])
    assert data["category"]["name"] == "A1 moved"

    refresh_all(tree)
    assert tree["a1"].parent_id == tree["b"].pk
    assert tree["a1a"].parent_id == tree["a1"].pk
    assert set(tree["b"].get_descendants()) == {tree["a1"], tree["a1a"]}
    assert set(tree["a"].get_descendants()) == {tree["a0"]}
    assert_tree_is_consistent()


def test_unchanged_omitted_parent_keeps_parent(
    staff_api_client, permission_manage_products, tree
):
    staff_api_client.user.user_permissions.add(permission_manage_products)
    content = get_graphql_content(
        staff_api_client.post_graphql(
            MUTATION_WITHOUT_PARENT,
            {"id": gid(tree["a1"]), "input": {"name": "Renamed"}},
        )
    )
    assert content["data"]["categoryUpdate"]["errors"] == []
    tree["a1"].refresh_from_db()
    assert tree["a1"].name == "Renamed"
    assert tree["a1"].parent_id == tree["a"].pk
    assert_tree_is_consistent()


@pytest.mark.parametrize("target", ["self", "descendant"])
def test_behavior_cannot_move_under_itself_or_descendant(
    target, staff_api_client, permission_manage_products, tree
):
    new_parent = tree["a1"] if target == "self" else tree["a1a"]
    data = move(
        staff_api_client, permission_manage_products, tree["a1"], gid(new_parent)
    )
    assert len(data["errors"]) == 1
    assert data["errors"][0]["field"] == "parent"
    assert data["errors"][0]["code"] == ProductErrorCode.INVALID.name
    tree["a1"].refresh_from_db()
    assert tree["a1"].parent_id == tree["a"].pk
    assert_tree_is_consistent()


def test_rule_move_takes_category_tree_advisory_lock_before_writing(
    staff_api_client,
    permission_manage_products,
    tree,
    assert_advisory_lock_before_tree_write,
):
    with assert_advisory_lock_before_tree_write(
        AdvisoryLock.CATEGORY_TREE, "product_category"
    ):
        data = move(
            staff_api_client, permission_manage_products, tree["a1"], gid(tree["b"])
        )
    assert data["errors"] == []


def test_rule_move_uses_tree_values_read_after_the_lock(
    staff_api_client, permission_manage_products, tree
):
    """A writer that got the lock first shifts the numbers the move relies on."""
    interfered = []

    def after_lock(execute, sql, params, many, context):
        result = execute(sql, params, many, context)
        if "pg_advisory_xact_lock" in sql and not interfered:
            interfered.append(True)
            # concurrent structural write, finished just before we got the lock:
            # it renumbers everything after A0, including A1 and A1a
            Category.objects.create(name="A0x", slug="a0x", parent=tree["a0"])
        return result

    with connection.execute_wrapper(after_lock):
        data = move(
            staff_api_client, permission_manage_products, tree["a1"], gid(tree["b"])
        )

    assert interfered == [True]
    assert data["errors"] == []
    refresh_all(tree)
    assert tree["a1"].parent_id == tree["b"].pk
    assert set(tree["b"].get_descendants()) == {tree["a1"], tree["a1a"]}
    assert_tree_is_consistent()
