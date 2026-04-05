"""Delete sync logic for push --delete."""

from __future__ import annotations

from dataclasses import dataclass, field

import asyncclick as click

from workato_platform_cli import Workato


@dataclass
class RemoteAssets:
    """Remote asset inventory."""

    recipes: list[dict] = field(default_factory=list)
    connections: list[dict] = field(default_factory=list)
    folders: list[dict] = field(default_factory=list)


@dataclass
class AssetsToDelete:
    """Assets that exist on remote but not locally."""

    recipes: list[dict] = field(default_factory=list)
    connections: list[dict] = field(default_factory=list)
    folders: list[dict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.recipes) + len(self.connections) + len(self.folders)

    @property
    def is_empty(self) -> bool:
        return self.total == 0


async def get_remote_assets(
    workato_api_client: Workato,
    folder_id: int,
) -> RemoteAssets:
    """Get all remote assets in the project folder."""
    assets = RemoteAssets()

    # Get recipes in the folder (with subfolders)
    response = await workato_api_client.recipes_api.list_recipes(
        folder_id=folder_id,
    )
    if response and response.items:
        for recipe in response.items:
            assets.recipes.append(
                {
                    "id": recipe.id,
                    "name": recipe.name,
                    "running": getattr(recipe, "running", False),
                }
            )

    # Get connections
    conn_response = await workato_api_client.connections_api.list_connections()
    if conn_response and hasattr(conn_response, "items"):
        for conn in conn_response.items or []:
            assets.connections.append(
                {
                    "id": conn.id,
                    "name": conn.name,
                }
            )

    # Get folders
    folder_response = await workato_api_client.folders_api.list_folders(
        parent_id=folder_id,
    )
    if folder_response:
        items = folder_response if isinstance(folder_response, list) else []
        for f in items:
            assets.folders.append(
                {
                    "id": f.id,
                    "name": f.name,
                }
            )

    return assets


def find_assets_to_delete(
    remote: RemoteAssets,
    local_asset_names: set[str],
) -> AssetsToDelete:
    """Find remote assets not present locally."""
    to_delete = AssetsToDelete()

    for recipe in remote.recipes:
        if recipe["name"] not in local_asset_names:
            to_delete.recipes.append(recipe)

    for conn in remote.connections:
        if conn["name"] not in local_asset_names:
            to_delete.connections.append(conn)

    for folder in remote.folders:
        if folder["name"] not in local_asset_names:
            to_delete.folders.append(folder)

    return to_delete


def display_delete_plan(to_delete: AssetsToDelete) -> None:
    """Display assets that will be deleted."""
    click.echo()
    click.echo(f"⚠️  {to_delete.total} remote asset(s) will be deleted:")

    if to_delete.recipes:
        click.echo("  Recipes:")
        for r in to_delete.recipes:
            running = " (running)" if r.get("running") else ""
            click.echo(f"    - {r['name']} (ID: {r['id']}){running}")

    if to_delete.connections:
        click.echo("  Connections:")
        for c in to_delete.connections:
            click.echo(f"    - {c['name']} (ID: {c['id']})")

    if to_delete.folders:
        click.echo("  Folders:")
        for f in to_delete.folders:
            click.echo(f"    - {f['name']} (ID: {f['id']})")

    click.echo()


async def execute_delete(
    workato_api_client: Workato,
    to_delete: AssetsToDelete,
) -> None:
    """Execute deletion of remote assets."""
    # 1. Stop and delete recipes first
    for recipe in to_delete.recipes:
        try:
            if recipe.get("running"):
                await workato_api_client.recipes_api.stop_recipe(
                    recipe_id=recipe["id"],
                )
                click.echo(f"  ⏹️  Stopped recipe: {recipe['name']}")
            await workato_api_client.recipes_api.delete_recipe(
                recipe_id=recipe["id"],
            )
            click.echo(f"  🗑️  Deleted recipe: {recipe['name']}")
        except Exception as e:
            click.echo(f"  ❌ Failed to delete recipe {recipe['name']}: {e}")

    # 2. Delete connections
    for conn in to_delete.connections:
        try:
            await workato_api_client.connections_api.delete_connection(
                connection_id=conn["id"],
            )
            click.echo(f"  🗑️  Deleted connection: {conn['name']}")
        except Exception as e:
            click.echo(f"  ❌ Failed to delete connection {conn['name']}: {e}")

    # 3. Delete folders last (after contents removed)
    for folder in to_delete.folders:
        try:
            await workato_api_client.folders_api.delete_folder(
                folder_id=folder["id"],
                force=True,
            )
            click.echo(f"  🗑️  Deleted folder: {folder['name']}")
        except Exception as e:
            click.echo(f"  ❌ Failed to delete folder {folder['name']}: {e}")
