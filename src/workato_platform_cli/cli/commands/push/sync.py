"""Delete sync logic for push --delete."""

from __future__ import annotations

import contextlib

from dataclasses import dataclass, field
from pathlib import Path

import asyncclick as click

from workato_platform_cli import Workato


@dataclass
class RemoteAsset:
    """A single remote asset."""

    id: int
    name: str
    type: str
    zip_name: str


@dataclass
class AssetsToDelete:
    """Assets that exist on remote but not locally."""

    assets: list[RemoteAsset] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.assets)

    @property
    def is_empty(self) -> bool:
        return self.total == 0

    @property
    def recipes(self) -> list[RemoteAsset]:
        return [a for a in self.assets if a.type == "recipe"]

    @property
    def connections(self) -> list[RemoteAsset]:
        return [a for a in self.assets if a.type == "connection"]

    @property
    def folders(self) -> list[RemoteAsset]:
        return [a for a in self.assets if a.type not in ("recipe", "connection")]


async def get_remote_assets(
    workato_api_client: Workato,
    folder_id: int,
) -> list[RemoteAsset]:
    """Get all remote assets in the project folder using export API.

    Uses list_assets_in_folder which returns Asset objects with zip_name,
    enabling accurate matching with local file names.
    """
    assets: list[RemoteAsset] = []

    response = await workato_api_client.export_api.list_assets_in_folder(
        folder_id=folder_id,
    )
    if response and response.result and response.result.assets:
        for asset in response.result.assets:
            # Strip extensions from zip_name for matching
            zip_stem = asset.zip_name
            while Path(zip_stem).suffix:
                zip_stem = Path(zip_stem).stem

            assets.append(
                RemoteAsset(
                    id=asset.id,
                    name=asset.name,
                    type=asset.type,
                    zip_name=zip_stem,
                )
            )

    return assets


def find_assets_to_delete(
    remote_assets: list[RemoteAsset],
    local_asset_names: set[str],
) -> AssetsToDelete:
    """Find remote assets not present locally by comparing zip_name."""
    to_delete = AssetsToDelete()

    for asset in remote_assets:
        if asset.zip_name not in local_asset_names:
            to_delete.assets.append(asset)

    return to_delete


def display_delete_plan(to_delete: AssetsToDelete) -> None:
    """Display assets that will be deleted."""
    click.echo()
    click.echo(f"⚠️  {to_delete.total} remote asset(s) will be deleted:")

    for asset in to_delete.assets:
        click.echo(f"    - [{asset.type}] {asset.name} (ID: {asset.id})")

    click.echo()


async def execute_delete(
    workato_api_client: Workato,
    to_delete: AssetsToDelete,
) -> None:
    """Execute deletion of remote assets.

    Order: recipes first, then connections, then others (folders).
    """
    # 1. Delete recipes first
    for asset in to_delete.recipes:
        try:
            # Stop recipe if running before deleting
            with contextlib.suppress(Exception):
                await workato_api_client.recipes_api.stop_recipe(
                    recipe_id=asset.id,
                )
            await workato_api_client.recipes_api.delete_recipe(
                recipe_id=asset.id,
            )
            click.echo(f"  🗑️  Deleted recipe: {asset.name}")
        except Exception as e:
            click.echo(f"  ❌ Failed to delete recipe {asset.name}: {e}")

    # 2. Delete connections
    for asset in to_delete.connections:
        try:
            await workato_api_client.connections_api.delete_connection(
                connection_id=asset.id,
            )
            click.echo(f"  🗑️  Deleted connection: {asset.name}")
        except Exception as e:
            click.echo(f"  ❌ Failed to delete connection {asset.name}: {e}")

    # 3. Delete folders/others last
    for asset in to_delete.folders:
        try:
            await workato_api_client.folders_api.delete_folder(
                folder_id=asset.id,
                force=True,
            )
            click.echo(f"  🗑️  Deleted {asset.type}: {asset.name}")
        except Exception as e:
            click.echo(f"  ❌ Failed to delete {asset.type} {asset.name}: {e}")
