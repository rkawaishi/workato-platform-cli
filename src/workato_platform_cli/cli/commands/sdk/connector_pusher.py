"""Push connector code to Workato platform."""

from pathlib import Path

import asyncclick as click

from workato_platform_cli import Workato
from workato_platform_cli.client.workato_api.models.custom_connector_create_request import (  # noqa: E501
    CustomConnectorCreateRequest,
)


async def push_connector(
    workato_api_client: Workato,
    connector_path: Path,
    title: str,
    description: str | None = None,
    notes: str | None = None,
    connector_id: int | None = None,
    release: bool = True,
) -> None:
    """Push connector code to Workato.

    If connector_id is provided, updates the existing connector.
    Otherwise, creates a new one.
    """
    code = connector_path.read_text()

    request = CustomConnectorCreateRequest(
        title=title,
        code=code,
        description=description,
        note=notes,
    )

    if connector_id is not None:
        click.echo(f"  🔄 Updating connector {connector_id}...")
        response = await workato_api_client.connectors_api.update_custom_connector(
            id=connector_id,
            custom_connector_create_request=request,
        )
        click.echo(f"  ✅ Connector updated: {response.title} (ID: {response.id})")
    else:
        click.echo("  🆕 Creating new connector...")
        response = await workato_api_client.connectors_api.create_custom_connector(
            custom_connector_create_request=request,
        )
        click.echo(f"  ✅ Connector created: {response.title} (ID: {response.id})")

    if release and response.id is not None:
        click.echo("  📦 Releasing connector...")
        release_response = (
            await workato_api_client.connectors_api.release_custom_connector(
                id=response.id,
            )
        )
        if release_response.id is not None:
            version = release_response.latest_released_version or "?"
            click.echo(f"  🚀 Released version {version}")
        else:
            click.echo("  ℹ️  Already released (no code changes detected)")
