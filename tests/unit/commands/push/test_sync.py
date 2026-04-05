"""Tests for push --delete sync logic."""

from __future__ import annotations

from workato_platform_cli.cli.commands.push.sync import (
    AssetsToDelete,
    RemoteAsset,
    RemoteFolder,
    find_assets_to_delete,
)


def test_find_assets_to_delete_empty_remote() -> None:
    result = find_assets_to_delete([], [], {"recipe_a"})
    assert result.is_empty


def test_find_assets_to_delete_all_matched() -> None:
    assets = [
        RemoteAsset(id=1, name="Recipe A", type="recipe", zip_name="recipe_a"),
        RemoteAsset(id=2, name="Recipe B", type="recipe", zip_name="recipe_b"),
    ]
    folders = [
        RemoteFolder(id=10, name="folder_x"),
    ]
    local_names = {"recipe_a", "recipe_b", "folder_x"}
    result = find_assets_to_delete(assets, folders, local_names)
    assert result.is_empty


def test_find_assets_to_delete_recipes_to_remove() -> None:
    assets = [
        RemoteAsset(id=1, name="Recipe A", type="recipe", zip_name="recipe_a"),
        RemoteAsset(id=2, name="Recipe B", type="recipe", zip_name="recipe_b"),
        RemoteAsset(id=3, name="Recipe C", type="recipe", zip_name="recipe_c"),
    ]
    result = find_assets_to_delete(assets, [], {"recipe_a"})

    assert len(result.recipes) == 2
    assert result.recipes[0].zip_name == "recipe_b"
    assert result.total == 2


def test_find_assets_to_delete_folders_to_remove() -> None:
    folders = [RemoteFolder(id=10, name="old_folder")]
    result = find_assets_to_delete([], folders, set())

    assert len(result.folders) == 1
    assert result.folders[0].name == "old_folder"
    assert result.total == 1


def test_find_assets_to_delete_mixed_types() -> None:
    assets = [
        RemoteAsset(id=1, name="Recipe A", type="recipe", zip_name="recipe_a"),
        RemoteAsset(id=2, name="Conn B", type="connection", zip_name="conn_b"),
        RemoteAsset(id=3, name="Lookup", type="lookup_table", zip_name="lookup"),
    ]
    folders = [RemoteFolder(id=10, name="old_folder")]
    result = find_assets_to_delete(assets, folders, {"recipe_a"})

    assert len(result.connections) == 1
    assert len(result.others) == 1
    assert len(result.folders) == 1
    assert result.total == 3


def test_assets_to_delete_properties() -> None:
    to_delete = AssetsToDelete(
        assets=[
            RemoteAsset(id=1, name="R", type="recipe", zip_name="r"),
            RemoteAsset(id=2, name="C", type="connection", zip_name="c"),
            RemoteAsset(id=3, name="L", type="lookup_table", zip_name="l"),
        ],
        folders=[RemoteFolder(id=4, name="f")],
    )
    assert to_delete.total == 4
    assert not to_delete.is_empty
    assert len(to_delete.recipes) == 1
    assert len(to_delete.connections) == 1
    assert len(to_delete.others) == 1
    assert len(to_delete.folders) == 1


def test_assets_to_delete_empty() -> None:
    to_delete = AssetsToDelete()
    assert to_delete.total == 0
    assert to_delete.is_empty
