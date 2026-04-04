"""Custom OAuth Profile management commands."""

import asyncclick as click

from dependency_injector.wiring import Provide, inject

from workato_platform_cli import Workato
from workato_platform_cli.cli.containers import Container
from workato_platform_cli.cli.utils import Spinner
from workato_platform_cli.cli.utils.exception_handler import (
    handle_api_exceptions,
    handle_cli_exceptions,
)
from workato_platform_cli.client.workato_api.models.custom_oauth_profile import (
    CustomOAuthProfile,
)


@click.group(name="oauth-profiles")
def oauth_profiles() -> None:
    """Manage custom OAuth profiles"""
    pass


@oauth_profiles.command(name="list")
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def list_profiles(
    workato_api_client: Workato = Provide[Container.workato_api_client],
) -> None:
    """List all custom OAuth profiles"""
    spinner = Spinner("Fetching OAuth profiles")
    spinner.start()

    try:
        api = workato_api_client.oauth_profiles_api
        response = await api.list_custom_oauth_profiles()
        profiles = response.result or []
    finally:
        elapsed = spinner.stop()

    click.echo(f"🔐 Custom OAuth Profiles ({len(profiles)} found) - ({elapsed:.1f}s)")

    if not profiles:
        click.echo("  ℹ️  No custom OAuth profiles found")
        click.echo(
            "  💡 Create one: workato oauth-profiles create "
            "--name 'My App' --provider salesforce "
            "--client-id <ID> --client-secret <SECRET>"
        )
        return

    click.echo()

    for profile in profiles:
        _display_profile(profile)
        click.echo()

    click.echo("💡 Commands:")
    click.echo("  • Details: workato oauth-profiles get --id <ID>")
    click.echo(
        "  • Create: workato oauth-profiles create "
        "--name 'Name' --provider <PROVIDER> "
        "--client-id <ID> --client-secret <SECRET>"
    )


@oauth_profiles.command(name="get")
@click.option("--id", "profile_id", required=True, type=int, help="Profile ID")
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def get_profile(
    profile_id: int,
    workato_api_client: Workato = Provide[Container.workato_api_client],
) -> None:
    """Get a custom OAuth profile by ID"""
    spinner = Spinner("Fetching OAuth profile")
    spinner.start()

    try:
        api = workato_api_client.oauth_profiles_api
        profile = await api.get_custom_oauth_profile(id=profile_id)
    finally:
        elapsed = spinner.stop()

    click.echo(f"🔐 Custom OAuth Profile ({elapsed:.1f}s)")
    click.echo()
    _display_profile(profile)


@oauth_profiles.command(name="create")
@click.option("--name", required=True, help="Profile name")
@click.option("--provider", required=True, help="App provider (e.g. salesforce, slack)")
@click.option("--client-id", required=True, help="OAuth client ID")
@click.option("--client-secret", required=True, help="OAuth client secret")
@click.option("--token", default=None, help="Token (Slack only)")
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def create_profile(
    name: str,
    provider: str,
    client_id: str,
    client_secret: str,
    token: str | None,
    workato_api_client: Workato = Provide[Container.workato_api_client],
) -> None:
    """Create a custom OAuth profile"""
    spinner = Spinner("Creating OAuth profile")
    spinner.start()

    try:
        api = workato_api_client.oauth_profiles_api
        profile = await api.create_custom_oauth_profile(
            name=name,
            provider=provider,
            client_id=client_id,
            client_secret=client_secret,
            token=token,
        )
    finally:
        elapsed = spinner.stop()

    click.echo(f"✅ OAuth profile created ({elapsed:.1f}s)")
    click.echo()
    _display_profile(profile)


@oauth_profiles.command(name="update")
@click.option("--id", "profile_id", required=True, type=int, help="Profile ID")
@click.option("--name", required=True, help="Profile name")
@click.option("--provider", required=True, help="App provider")
@click.option("--client-id", required=True, help="OAuth client ID")
@click.option("--client-secret", required=True, help="OAuth client secret")
@click.option("--token", default=None, help="Token (Slack only)")
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def update_profile(
    profile_id: int,
    name: str,
    provider: str,
    client_id: str,
    client_secret: str,
    token: str | None,
    workato_api_client: Workato = Provide[Container.workato_api_client],
) -> None:
    """Update a custom OAuth profile"""
    spinner = Spinner("Updating OAuth profile")
    spinner.start()

    try:
        api = workato_api_client.oauth_profiles_api
        profile = await api.update_custom_oauth_profile(
            id=profile_id,
            name=name,
            provider=provider,
            client_id=client_id,
            client_secret=client_secret,
            token=token,
        )
    finally:
        elapsed = spinner.stop()

    click.echo(f"✅ OAuth profile updated ({elapsed:.1f}s)")
    click.echo()
    _display_profile(profile)


@oauth_profiles.command(name="delete")
@click.option("--id", "profile_id", required=True, type=int, help="Profile ID")
@click.confirmation_option(prompt="Are you sure you want to delete this profile?")
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def delete_profile(
    profile_id: int,
    workato_api_client: Workato = Provide[Container.workato_api_client],
) -> None:
    """Delete a custom OAuth profile"""
    spinner = Spinner("Deleting OAuth profile")
    spinner.start()

    try:
        api = workato_api_client.oauth_profiles_api
        await api.delete_custom_oauth_profile(id=profile_id)
    finally:
        elapsed = spinner.stop()

    click.echo(f"✅ OAuth profile {profile_id} deleted ({elapsed:.1f}s)")


def _display_profile(profile: CustomOAuthProfile) -> None:
    """Display a custom OAuth profile."""
    click.echo(f"  🆔 ID: {profile.id}")
    click.echo(f"  📝 Name: {profile.name}")
    click.echo(f"  🔌 Provider: {profile.provider}")
    if profile.data and profile.data.client_id:
        click.echo(f"  🔑 Client ID: {profile.data.client_id}")
    if profile.shared_accounts_count is not None:
        click.echo(f"  👥 Shared accounts: {profile.shared_accounts_count}")
    if profile.created_at:
        click.echo(f"  📅 Created: {profile.created_at}")
    if profile.updated_at:
        click.echo(f"  📅 Updated: {profile.updated_at}")
