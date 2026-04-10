from __future__ import annotations

from typing import TYPE_CHECKING

import asyncclick as click

from dependency_injector.wiring import Provide, inject

from workato_platform_cli.cli.commands.connectors.connector_manager import (
    ConnectorManager,
)
from workato_platform_cli.cli.containers import Container
from workato_platform_cli.cli.utils.exception_handler import (
    handle_api_exceptions,
    handle_cli_exceptions,
)


if TYPE_CHECKING:
    from workato_platform_cli.client.workato_api.models.connector_action import (
        ConnectorAction,
    )
    from workato_platform_cli.client.workato_api.models.platform_connector import (
        PlatformConnector,
    )


@click.group()
def connectors() -> None:
    """Manage connectors"""
    pass


@connectors.command(name="list")
@click.option(
    "--platform",
    is_flag=True,
    help="List platform connectors with trigger and action metadata",
)
@click.option("--custom", is_flag=True, help="List custom connectors")
@click.option(
    "--provider",
    default=None,
    help="Filter by provider name (shows triggers/actions detail)",
)
@click.option(
    "--output-mode",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def list_connectors(
    platform: bool,
    custom: bool,
    provider: str | None,
    output_mode: str,
    connector_manager: ConnectorManager = Provide[Container.connector_manager],
) -> None:
    """List connectors (platform connectors include trigger and action metadata)"""
    import json

    # --provider implies --platform only
    if provider:
        platform = True
        custom = False

    # If neither flag is specified, show both
    if not platform and not custom:
        platform = True
        custom = True

    if platform:
        quiet = output_mode == "json" or provider is not None
        all_connectors = await connector_manager.list_platform_connectors(
            quiet=quiet
        )

        if provider:
            # Filter by provider name
            matched = [
                c for c in all_connectors if c.name == provider
            ]
            if not matched:
                click.echo(f"❌ Provider '{provider}' not found")
                return

            connector = matched[0]

            if output_mode == "json":
                click.echo(json.dumps(connector.to_dict(), indent=2))
                return

            _display_connector_detail(connector)
            return

        if all_connectors:
            if output_mode == "json":
                click.echo(
                    json.dumps(
                        [c.to_dict() for c in all_connectors],
                        indent=2,
                    )
                )
            else:
                for connector in all_connectors:
                    _display_connector_summary(connector)
        else:
            click.echo("  No platform connectors found")

    if custom:
        if platform:
            click.echo()  # Add spacing between sections
        await connector_manager.list_custom_connectors()


def _display_connector_summary(connector: PlatformConnector) -> None:
    """Display a single connector with triggers/actions count."""
    title = connector.title
    name = connector.name
    triggers = connector.triggers or []
    actions = connector.actions or []
    click.echo(f"  🔌 {title} ({name})")
    click.echo(
        f"     triggers: {len(triggers)}  actions: {len(actions)}"
    )


def _display_connector_detail(connector: PlatformConnector) -> None:
    """Display detailed connector info with triggers/actions list."""
    click.echo(f"🔌 {connector.title} ({connector.name})")

    triggers = connector.triggers or []
    if triggers:
        click.echo("  Triggers:")
        for t in triggers:
            label = t.title or t.name
            flags = _action_flags(t)
            click.echo(f"    • {t.name} — {label}{flags}")
    else:
        click.echo("  Triggers: (none)")

    actions = connector.actions or []
    if actions:
        click.echo("  Actions:")
        for a in actions:
            label = a.title or a.name
            flags = _action_flags(a)
            click.echo(f"    • {a.name} — {label}{flags}")
    else:
        click.echo("  Actions: (none)")


def _action_flags(action: ConnectorAction) -> str:
    """Build flag string for deprecated/bulk/batch indicators."""
    parts: list[str] = []
    if action.deprecated:
        parts.append("deprecated")
    if action.bulk:
        parts.append("bulk")
    if action.batch:
        parts.append("batch")
    return f" [{', '.join(parts)}]" if parts else ""


@connectors.command()
@click.option("--provider", help="Show parameters for a specific provider")
@click.option("--oauth-only", is_flag=True, help="Show only OAuth-enabled providers")
@click.option("--search", help="Search provider names (case-insensitive)")
@click.option("--all", "show_all", is_flag=True, help="Output full schema as JSON")
@click.option(
    "--pretty", is_flag=True, help="Pretty-print JSON output (use with --all)"
)
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def parameters(
    provider: str,
    oauth_only: bool,
    search: str,
    show_all: bool,
    pretty: bool,
    connector_manager: ConnectorManager = Provide[Container.connector_manager],
) -> None:
    """List connection parameters for connectors

    Shows configuration requirements for creating connections to different services.
    """
    import json

    # Load the bundled connection data using the injected manager
    connection_data = connector_manager.load_connection_data()

    # Handle --all flag - output raw schema data as JSON
    if show_all:
        # Convert ProviderData objects back to dict for JSON serialization
        json_data = {}
        for key, provider_data in connection_data.items():
            json_data[key] = provider_data.model_dump()

        # Pretty-print if --pretty flag is set
        if pretty:
            click.echo(json.dumps(json_data, indent=2))
        else:
            click.echo(json.dumps(json_data))
        return

    if not connection_data:
        click.echo("❌ Connection parameter data not found.")
        click.echo()
        click.echo("💡 This may indicate:")
        click.echo("  • CLI was not installed properly (data files missing)")
        click.echo("  • Development setup needs data generation")
        click.echo()
        click.echo("🔧 To resolve:")
        click.echo(
            "  1. If using installed CLI: try reinstalling with 'pip install "
            "--force-reinstall workato-platform-cli'"
        )
        click.echo(
            "  2. If developing: run 'python scripts/parse_connection_docs.py' "
            "to generate data"
        )
        click.echo(
            "  3. Alternative: use 'workato connectors list --platform' "
            "to see available providers"
        )
        return

    if provider:
        # Show details for specific provider
        if provider not in connection_data:
            click.echo(f"❌ Provider '{provider}' not found")
            # Suggest similar providers
            suggestions = [p for p in connection_data if provider.lower() in p.lower()]
            if suggestions:
                click.echo(f"💡 Did you mean: {', '.join(suggestions[:3])}")
            click.echo(
                "💡 Use 'workato connectors parameters' to see all available providers"
            )
            return

        connector_manager.show_provider_details(provider, connection_data[provider])

    else:
        # Show all providers with optional filtering
        filtered_providers = []
        for k, v in connection_data.items():
            if (not oauth_only or v.oauth) and (
                not search
                or search.lower() in v.name.lower()
                or search.lower() in k.lower()
            ):
                filtered_providers.append((k, v))

        # Show summary
        filter_text = ""
        if oauth_only:
            filter_text += " (OAuth only)"
        if search:
            filter_text += f" (matching '{search}')"

        click.echo(
            f"🔌 Connection Parameters ({len(filtered_providers)} "
            f"providers{filter_text})"
        )
        click.echo()

        if not filtered_providers:
            click.echo("  ℹ️  No providers found matching criteria")
            return

        # Sort by name for better readability
        filtered_providers.sort(key=lambda x: x[1].name)

        # Display providers in a compact format
        for provider_key, provider_data in filtered_providers:
            name = provider_data.name
            param_count = provider_data.parameter_count
            oauth_icon = "🔐" if provider_data.oauth else "🔑"
            tunnel_icon = "🔒" if provider_data.secure_tunnel else ""

            click.echo(f"  {oauth_icon} {name:<40} ({provider_key})")

            if param_count > 0:
                click.echo(
                    f"    📝 {param_count} parameter{'s' if param_count != 1 else ''}"
                )
            else:
                click.echo("    📝 No configuration required")

            if tunnel_icon:
                click.echo(f"    {tunnel_icon} Supports secure tunnel")

            click.echo()

        click.echo("💡 Commands:")
        click.echo(
            "  • View provider details: workato connectors parameters "
            "--provider salesforce"
        )
        click.echo("  • Get JSON schema: workato connectors parameters --all")
        click.echo("  • Get pretty JSON: workato connectors parameters --all --pretty")
        click.echo(
            "  • Create connection: workato connections create --provider <PROVIDER> "
            "--name 'My Connection'"
        )
