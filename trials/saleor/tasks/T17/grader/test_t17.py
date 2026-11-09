import graphene
import pytest

from saleor.core.db.locks import AdvisoryLock
from saleor.graphql.tests.utils import get_graphql_content
from saleor.menu.models import Menu, MenuItem

MUTATION = """
    mutation($id: ID!, $keepChildren: Boolean) {
      menuItemDelete(id: $id, keepChildren: $keepChildren) {
        errors { field code message }
        menuItem { id name }
      }
    }
"""


def gid(item):
    return graphene.Node.to_global_id("MenuItem", item.pk)


@pytest.fixture
def items(db):
    menu = Menu.objects.create(name="tree-menu", slug="tree-menu")

    def make(name, parent=None):
        return MenuItem.objects.create(menu=menu, name=name, parent=parent)

    root = make("R")
    target = make("M", root)
    c1 = make("C1", target)
    c1a = make("C1a", c1)
    c2 = make("C2", target)
    c3 = make("C3", target)
    c3a = make("C3a", c3)
    sibling = make("S", root)
    other_root = make("X")
    other_child = make("X1", other_root)
    top = make("T")
    top_child_1 = make("T1", top)
    top_child_2 = make("T2", top)
    top_grandchild = make("T2a", top_child_2)
    return {
        "r": root,
        "m": target,
        "c1": c1,
        "c1a": c1a,
        "c2": c2,
        "c3": c3,
        "c3a": c3a,
        "s": sibling,
        "x": other_root,
        "x1": other_child,
        "t": top,
        "t1": top_child_1,
        "t2": top_child_2,
        "t2a": top_grandchild,
    }


def assert_tree_is_consistent():
    all_items = list(MenuItem.objects.all())
    by_pk = {i.pk: i for i in all_items}
    numbers_per_tree = {}
    for item in all_items:
        if item.parent_id is None:
            assert item.level == 0
        else:
            parent = by_pk[item.parent_id]
            assert item.tree_id == parent.tree_id
            assert item.level == parent.level + 1
            assert parent.lft < item.lft < item.rght < parent.rght
        numbers_per_tree.setdefault(item.tree_id, []).extend([item.lft, item.rght])
    for tree_id, numbers in numbers_per_tree.items():
        assert sorted(numbers) == list(range(1, len(numbers) + 1)), tree_id


def delete(client, permission, item, keep_children):
    client.user.user_permissions.add(permission)
    variables = {"id": gid(item)}
    if keep_children is not None:
        variables["keepChildren"] = keep_children
    return get_graphql_content(client.post_graphql(MUTATION, variables))["data"][
        "menuItemDelete"
    ]


def parent_of(item):
    item.refresh_from_db()
    return item.parent_id


def test_behavior_children_move_to_deleted_items_parent(
    staff_api_client, permission_manage_menus, items
):
    data = delete(staff_api_client, permission_manage_menus, items["m"], True)

    assert data["errors"] == []
    assert data["menuItem"]["id"] == gid(items["m"])
    assert MenuItem.objects.filter(pk=items["m"].pk).exists() is False
    for name in ("c1", "c2", "c3", "s"):
        assert parent_of(items[name]) == items["r"].pk
    assert parent_of(items["c1a"]) == items["c1"].pk
    assert parent_of(items["c3a"]) == items["c3"].pk
    assert MenuItem.objects.count() == 13


def test_behavior_children_of_top_level_item_become_top_level(
    staff_api_client, permission_manage_menus, items
):
    data = delete(staff_api_client, permission_manage_menus, items["t"], True)

    assert data["errors"] == []
    assert MenuItem.objects.filter(pk=items["t"].pk).exists() is False
    assert parent_of(items["t1"]) is None
    assert parent_of(items["t2"]) is None
    assert parent_of(items["t2a"]) == items["t2"].pk
    for name in ("t1", "t2", "t2a"):
        items[name].refresh_from_db()
        assert items[name].menu_id == items["t"].menu_id


@pytest.mark.parametrize("keep_children", [False, None])
def test_unchanged_without_keep_children_whole_subtree_is_deleted(
    keep_children, staff_api_client, permission_manage_menus, items
):
    data = delete(staff_api_client, permission_manage_menus, items["m"], keep_children)

    assert data["errors"] == []
    remaining = set(MenuItem.objects.values_list("name", flat=True))
    assert remaining == {"R", "S", "X", "X1", "T", "T1", "T2", "T2a"}


def test_rule_nested_set_stays_consistent_after_promoting_children(
    staff_api_client, permission_manage_menus, items
):
    delete(staff_api_client, permission_manage_menus, items["m"], True)
    assert_tree_is_consistent()
    delete(staff_api_client, permission_manage_menus, items["t"], True)
    assert_tree_is_consistent()
    r = items["r"]
    r.refresh_from_db()
    assert {i.name for i in r.get_descendants()} == {
        "S",
        "C1",
        "C1a",
        "C2",
        "C3",
        "C3a",
    }


def test_rule_promoting_children_takes_menu_item_tree_lock_before_writing(
    staff_api_client,
    permission_manage_menus,
    items,
    assert_advisory_lock_before_tree_write,
):
    with assert_advisory_lock_before_tree_write(
        AdvisoryLock.MENU_ITEM_TREE, "menu_menuitem"
    ):
        data = delete(staff_api_client, permission_manage_menus, items["m"], True)
    assert data["errors"] == []
