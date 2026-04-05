"""Connector SDK commands."""

import json

from pathlib import Path

import asyncclick as click

from dependency_injector.wiring import Provide, inject

from workato_platform_cli import Workato
from workato_platform_cli.cli.commands.sdk.connector_pusher import push_connector
from workato_platform_cli.cli.commands.sdk.scaffold import generate_scaffold
from workato_platform_cli.cli.commands.sdk.sdk_runner import SdkRunner
from workato_platform_cli.cli.containers import Container
from workato_platform_cli.cli.utils import Spinner
from workato_platform_cli.cli.utils.exception_handler import (
    handle_api_exceptions,
    handle_cli_exceptions,
)


@click.group()
def sdk() -> None:
    """Connector SDK commands"""
    pass


# --- sdk new ---


@sdk.command(name="new")
@click.argument("path")
@handle_cli_exceptions
async def new_connector(path: str) -> None:
    """Create a new connector project scaffold"""
    project_path = Path(path).resolve()

    if project_path.exists() and any(project_path.iterdir()):
        raise click.ClickException(
            f"Directory '{path}' already exists and is not empty"
        )

    name = project_path.name
    click.echo(f"🔧 Creating connector project: {name}")

    created_files = generate_scaffold(project_path, name)

    click.echo(f"✅ Connector project created at {project_path}")
    click.echo()
    click.echo("  Created files:")
    for f in created_files:
        click.echo(f"    {f}")
    click.echo()
    click.echo("💡 Next steps:")
    click.echo(f"  cd {path}")
    click.echo("  bundle install")
    click.echo("  # Edit connector.rb to implement your connector")
    click.echo("  bundle exec rspec")


# --- sdk push ---


@sdk.command(name="push")
@click.option(
    "--connector",
    default="connector.rb",
    help="Path to connector file",
    type=click.Path(exists=True),
)
@click.option("--title", required=True, help="Connector title")
@click.option("--description", default=None, help="Connector description (markdown)")
@click.option("--notes", default=None, help="Release notes")
@click.option(
    "--connector-id",
    default=None,
    type=int,
    help="Existing connector ID (for updates)",
)
@click.option(
    "--no-release",
    is_flag=True,
    default=False,
    help="Upload without releasing",
)
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def push(
    connector: str,
    title: str,
    description: str | None,
    notes: str | None,
    connector_id: int | None,
    no_release: bool,
    workato_api_client: Workato = Provide[Container.workato_api_client],
) -> None:
    """Push connector code to Workato platform"""
    connector_path = Path(connector)

    await push_connector(
        workato_api_client=workato_api_client,
        connector_path=connector_path,
        title=title,
        description=description,
        notes=notes,
        connector_id=connector_id,
        release=not no_release,
    )


# --- sdk generate ---


@sdk.group(name="generate")
def generate() -> None:
    """Generate schemas and test stubs"""
    pass


@generate.command(name="schema")
@click.option(
    "--json-file",
    "json_file",
    default=None,
    help="JSON sample file",
    type=click.Path(exists=True),
)
@click.option(
    "--csv-file",
    "csv_file",
    default=None,
    help="CSV sample file",
    type=click.Path(exists=True),
)
@click.option(
    "--col-sep",
    default=None,
    type=click.Choice(["comma", "space", "tab", "colon", "semicolon", "pipe"]),
    help="CSV column separator",
)
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def generate_schema(
    json_file: str | None,
    csv_file: str | None,
    col_sep: str | None,
    workato_api_client: Workato = Provide[Container.workato_api_client],
) -> None:
    """Generate Workato schema from JSON or CSV sample"""
    if not json_file and not csv_file:
        raise click.ClickException("Provide --json-file or --csv-file")
    if json_file and csv_file:
        raise click.ClickException("Provide only one of --json-file or --csv-file")

    spinner = Spinner("Generating schema")
    spinner.start()

    try:
        if json_file:
            with open(json_file) as f:
                raw_json = f.read()
            result = await workato_api_client.sdk_api.generate_schema_from_json(
                body={"sample": raw_json},
            )
        else:
            with open(csv_file) as f:  # type: ignore[arg-type]
                csv_content = f.read()
            result = await workato_api_client.sdk_api.generate_schema_from_csv(
                body={"sample": csv_content},
                col_sep=col_sep,
            )
    finally:
        elapsed = spinner.stop()

    click.echo(f"📋 Generated Schema ({elapsed:.1f}s)")
    click.echo()
    click.echo(json.dumps(result, indent=2))


# --- sdk exec ---


@sdk.command(name="exec")
@click.argument("path")
@click.option("--connector", "-c", default="connector.rb", help="Connector file path")
@click.option("--settings", "-s", default=None, help="Settings file path")
@click.option("--input", "-i", "input_file", default=None, help="Input JSON file")
@click.option("--output", "-o", "output_file", default=None, help="Output JSON file")
@click.option("--verbose", is_flag=True, help="Show all requests/responses")
@handle_cli_exceptions
async def exec_connector(
    path: str,
    connector: str,
    settings: str | None,
    input_file: str | None,
    output_file: str | None,
    verbose: bool,
) -> None:
    """Execute a connector block (requires Ruby + workato-connector-sdk gem)

    PATH: Block path (e.g., actions.search.execute, triggers.new_record.poll)
    """
    runner = SdkRunner()

    if not runner.check_ruby_installed():
        raise click.ClickException(
            "Ruby is not installed. Install Ruby to use 'sdk exec'.\n"
            "  macOS: brew install ruby"
        )

    if not runner.check_gem_installed():
        raise click.ClickException(
            "workato-connector-sdk gem is not installed.\n"
            "  Run: gem install workato-connector-sdk"
        )

    args = ["exec", path, "-c", connector]
    if settings:
        args.extend(["-s", settings])
    if input_file:
        args.extend(["-i", input_file])
    if output_file:
        args.extend(["-o", output_file])
    if verbose:
        args.append("--verbose")

    click.echo(f"🔧 Executing: {path}")
    exit_code = runner.run_interactive(*args)

    if exit_code != 0:
        raise click.ClickException(f"Execution failed with exit code {exit_code}")


# --- sdk oauth2 ---


@sdk.command(name="oauth2")
@click.option("--connector", "-c", default="connector.rb", help="Connector file path")
@click.option("--settings", "-s", default=None, help="Settings file path")
@click.option("--port", default=45555, type=int, help="Callback server port")
@click.option("--ip", default="127.0.0.1", help="Callback server IP")
@handle_cli_exceptions
async def oauth2(
    connector: str,
    settings: str | None,
    port: int,
    ip: str,
) -> None:
    """Run OAuth2 authorization flow (requires Ruby + workato-connector-sdk gem)"""
    runner = SdkRunner()

    if not runner.check_ruby_installed():
        raise click.ClickException("Ruby is not installed.")

    if not runner.check_gem_installed():
        raise click.ClickException(
            "workato-connector-sdk gem is not installed.\n"
            "  Run: gem install workato-connector-sdk"
        )

    args = ["oauth2", "-c", connector, "--port", str(port), "--ip", ip]
    if settings:
        args.extend(["-s", settings])

    click.echo("🔐 Starting OAuth2 authorization flow...")
    exit_code = runner.run_interactive(*args)

    if exit_code != 0:
        raise click.ClickException(f"OAuth2 flow failed with exit code {exit_code}")


# --- sdk edit ---


@sdk.command(name="edit")
@click.argument("path", default="settings.yaml.enc")
@click.option(
    "--key",
    "-k",
    "key_path",
    default="master.key",
    help="Path to encryption key file",
)
@handle_cli_exceptions
async def edit_encrypted(path: str, key_path: str) -> None:
    """Edit an encrypted file (e.g., settings.yaml.enc)

    Decrypts the file, opens it in $EDITOR, and re-encrypts on save.
    If the file doesn't exist, creates a new encrypted file.
    """
    import os
    import subprocess  # noqa: S404
    import tempfile

    from workato_platform_cli.cli.commands.sdk.encrypted_file import (
        generate_key,
        read_encrypted_file,
        write_encrypted_file,
    )

    enc_path = Path(path)
    key_file = Path(key_path)

    # Generate key if it doesn't exist
    if not key_file.exists():
        new_key = generate_key()
        key_file.write_text(new_key)
        key_file.chmod(0o600)
        click.echo(f"🔑 Generated new key: {key_file}")
        click.echo(
            "  ⚠️  Save this key securely. "
            "Without it, encrypted files cannot be decrypted."
        )

    # Decrypt existing file or start with empty content
    if enc_path.exists():
        try:
            content = read_encrypted_file(enc_path, key_file)
        except Exception as e:
            raise click.ClickException(f"Failed to decrypt {enc_path}: {e}") from e
    else:
        content = "# Add your connector credentials here\n"

    # Determine editor
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))

    # Write decrypted content to temp file, open in editor
    suffix = ".yaml" if "yaml" in path else ".txt"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        import shlex

        editor_cmd = shlex.split(editor) + [tmp_path]
        result = subprocess.run(  # noqa: S603
            editor_cmd, timeout=3600
        )
        if result.returncode != 0:
            raise click.ClickException(f"Editor exited with code {result.returncode}")

        # Read edited content
        edited = Path(tmp_path).read_text(encoding="utf-8")

        if edited == content:
            click.echo("ℹ️  No changes made")
            return

        # Re-encrypt and save
        write_encrypted_file(enc_path, key_file, edited)
        click.echo(f"✅ Encrypted and saved: {enc_path}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)
