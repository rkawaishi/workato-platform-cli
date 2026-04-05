"""Tests for push --delete sync logic."""

from __future__ import annotations

from workato_platform_cli.cli.commands.push.sync import (
    AssetsToDelete,
    RemoteAssets,
    find_assets_to_delete,
)


def test_find_assets_to_delete_empty_remote() -> None:
    remote = RemoteAssets()
    local_names: set[str] = {"recipe_a"}
    result = find_assets_to_delete(remote, local_names)
    assert result.is_empty


def test_find_assets_to_delete_all_matched() -> None:
    remote = RemoteAssets(
        recipes=[{"id": 1, "name": "recipe_a"}, {"id": 2, "name": "recipe_b"}],
        folders=[{"id": 10, "name": "folder_x"}],
    )
    local_names = {"recipe_a", "recipe_b", "folder_x"}
    result = find_assets_to_delete(remote, local_names)
    assert result.is_empty


def test_find_assets_to_delete_recipes_to_remove() -> None:
    remote = RemoteAssets(
        recipes=[
            {"id": 1, "name": "recipe_a"},
            {"id": 2, "name": "recipe_b"},
            {"id": 3, "name": "recipe_c"},
        ],
    )
    local_names = {"recipe_a"}
    result = find_assets_to_delete(remote, local_names)

    assert len(result.recipes) == 2
    assert result.recipes[0]["name"] == "recipe_b"
    assert result.recipes[1]["name"] == "recipe_c"
    assert result.total == 2


def test_find_assets_to_delete_folders_to_remove() -> None:
    remote = RemoteAssets(
        folders=[{"id": 10, "name": "old_folder"}],
    )
    local_names: set[str] = set()
    result = find_assets_to_delete(remote, local_names)

    assert len(result.folders) == 1
    assert result.folders[0]["name"] == "old_folder"


def test_assets_to_delete_total() -> None:
    to_delete = AssetsToDelete(
        recipes=[{"id": 1, "name": "a"}],
        connections=[{"id": 2, "name": "b"}, {"id": 3, "name": "c"}],
        folders=[{"id": 4, "name": "d"}],
    )
    assert to_delete.total == 4
    assert not to_delete.is_empty


def test_assets_to_delete_empty() -> None:
    to_delete = AssetsToDelete()
    assert to_delete.total == 0
    assert to_delete.is_empty
