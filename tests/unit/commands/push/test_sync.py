"""Tests for push --delete sync logic."""

from __future__ import annotations

from workato_platform_cli.cli.commands.push.sync import (
    AssetsToDelete,
    RemoteAsset,
    find_assets_to_delete,
)


def test_find_assets_to_delete_empty_remote() -> None:
    remote: list[RemoteAsset] = []
    local_names: set[str] = {"recipe_a"}
    result = find_assets_to_delete(remote, local_names)
    assert result.is_empty


def test_find_assets_to_delete_all_matched() -> None:
    remote = [
        RemoteAsset(id=1, name="Recipe A", type="recipe", zip_name="recipe_a"),
        RemoteAsset(id=2, name="Recipe B", type="recipe", zip_name="recipe_b"),
        RemoteAsset(id=10, name="Folder X", type="folder", zip_name="folder_x"),
    ]
    local_names = {"recipe_a", "recipe_b", "folder_x"}
    result = find_assets_to_delete(remote, local_names)
    assert result.is_empty


def test_find_assets_to_delete_recipes_to_remove() -> None:
    remote = [
        RemoteAsset(id=1, name="Recipe A", type="recipe", zip_name="recipe_a"),
        RemoteAsset(id=2, name="Recipe B", type="recipe", zip_name="recipe_b"),
        RemoteAsset(id=3, name="Recipe C", type="recipe", zip_name="recipe_c"),
    ]
    local_names = {"recipe_a"}
    result = find_assets_to_delete(remote, local_names)

    assert len(result.recipes) == 2
    assert result.recipes[0].zip_name == "recipe_b"
    assert result.recipes[1].zip_name == "recipe_c"
    assert result.total == 2


def test_find_assets_to_delete_mixed_types() -> None:
    remote = [
        RemoteAsset(id=1, name="Recipe A", type="recipe", zip_name="recipe_a"),
        RemoteAsset(id=2, name="Conn B", type="connection", zip_name="conn_b"),
        RemoteAsset(id=3, name="Old Folder", type="folder", zip_name="old_folder"),
    ]
    local_names = {"recipe_a"}
    result = find_assets_to_delete(remote, local_names)

    assert len(result.connections) == 1
    assert len(result.folders) == 1
    assert result.total == 2


def test_assets_to_delete_properties() -> None:
    to_delete = AssetsToDelete(
        assets=[
            RemoteAsset(id=1, name="R", type="recipe", zip_name="r"),
            RemoteAsset(id=2, name="C", type="connection", zip_name="c"),
            RemoteAsset(id=3, name="F", type="folder", zip_name="f"),
        ]
    )
    assert to_delete.total == 3
    assert not to_delete.is_empty
    assert len(to_delete.recipes) == 1
    assert len(to_delete.connections) == 1
    assert len(to_delete.folders) == 1


def test_assets_to_delete_empty() -> None:
    to_delete = AssetsToDelete()
    assert to_delete.total == 0
    assert to_delete.is_empty
