"""Connector SDK commands."""

import json

from pathlib import Path

import asyncclick as click

from dependency_injector.wiring import Provide, inject

from workato_platform_cli import Workato
from workato_platform_cli.cli.commands.sdk.connector_pusher import push_connector
from workato_platform_cli.cli.commands.sdk.scaffold import generate_scaffold
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


def _resolve_settings(
    settings: str | None,
    key_path: str,
) -> str | None:
    """Resolve settings file path, decrypting .enc files if needed.

    If settings is None, auto-detects settings.yaml.enc or settings.yaml.
    If settings ends with .enc, decrypts to a temp .yaml file.
    """
    import tempfile

    from workato_platform_cli.cli.commands.sdk.encrypted_file import (
        read_encrypted_file,
    )

    # Auto-detect settings file
    if settings is None:
        if Path("settings.yaml.enc").exists():
            settings = "settings.yaml.enc"
        elif Path("settings.yaml").exists():
            settings = "settings.yaml"
        else:
            return None

    # Decrypt .enc files to temp file
    if settings.endswith(".enc"):
        key_file = Path(key_path)
        enc_file = Path(settings)
        try:
            content = read_encrypted_file(enc_file, key_file)
        except FileNotFoundError as e:
            raise click.ClickException(str(e)) from e

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(content)
        click.echo(f"🔓 Decrypted {settings}")
        return tmp.name

    return settings


def _save_tokens_to_settings(
    settings: str | None,
    key_path: str,
    token_response: dict[str, str],
) -> None:
    """Merge token response into settings file.

    Following workato-connector-sdk convention, tokens (access_token,
    refresh_token, etc.) are stored directly in settings.yaml.
    """
    import yaml

    from workato_platform_cli.cli.commands.sdk.encrypted_file import (
        read_encrypted_file,
        write_encrypted_file,
    )

    # Determine target settings file
    target = settings
    if target is None:
        if Path("settings.yaml.enc").exists():
            target = "settings.yaml.enc"
        else:
            target = "settings.yaml"

    target_path = Path(target)
    key_file = Path(key_path)

    # Load existing settings
    existing: dict[str, str] = {}
    if target_path.exists():
        if target.endswith(".enc"):
            content = read_encrypted_file(target_path, key_file)
            existing = yaml.safe_load(content) or {}
        else:
            existing = yaml.safe_load(target_path.read_text()) or {}

    # Merge token response
    for key in (
        "access_token",
        "refresh_token",
        "token_type",
        "expires_in",
        "scope",
    ):
        if key in token_response:
            existing[key] = token_response[key]

    # Save
    new_content = yaml.dump(existing, default_flow_style=False)
    if target.endswith(".enc"):
        write_encrypted_file(target_path, key_file, new_content)
        click.echo(f"🔐 Tokens saved to {target} (encrypted)")
    else:
        target_path.write_text(new_content)
        click.echo(f"💾 Tokens saved to {target}")


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
@click.option(
    "--key", "-k", "key_path", default="master.key", help="Encryption key file"
)
@click.option(
    "--connection",
    "-n",
    "connection_name",
    default=None,
    help="Connection name (for multiple credential sets)",
)
@click.option("--input", "-i", "input_file", default=None, help="Input JSON file")
@click.option("--output", "-o", "output_file", default=None, help="Output JSON file")
@click.option("--closure", default=None, help="Closure/state JSON file (for triggers)")
@click.option(
    "--args", "args_file", default=None, help="Arguments JSON file (for methods)"
)
@click.option(
    "--extended-input-schema",
    default=None,
    help="Extended input schema JSON file",
)
@click.option(
    "--extended-output-schema",
    default=None,
    help="Extended output schema JSON file",
)
@click.option("--config-fields", default=None, help="Config fields JSON file")
@click.option(
    "--continue", "continue_data", default=None, help="Continue data JSON file"
)
@click.option(
    "--from",
    "from_byte",
    default=None,
    type=int,
    help="Starting byte range (for streams)",
)
@click.option(
    "--frame-size",
    default=None,
    type=int,
    help="Requested frame size in bytes",
)
@click.option("--webhook-headers", default=None, help="Webhook headers JSON")
@click.option("--webhook-params", default=None, help="Webhook params JSON")
@click.option("--webhook-payload", default=None, help="Webhook payload JSON file")
@click.option("--webhook-url", default=None, help="Webhook URL")
@click.option("--verbose", is_flag=True, help="Show all requests/responses")
@click.option("--debug", is_flag=True, help="Show complete stacktrace on errors")
@handle_cli_exceptions
async def exec_connector(  # noqa: PLR0913
    path: str,
    connector: str,
    settings: str | None,
    key_path: str,
    connection_name: str | None,
    input_file: str | None,
    output_file: str | None,
    closure: str | None,
    args_file: str | None,
    extended_input_schema: str | None,
    extended_output_schema: str | None,
    config_fields: str | None,
    continue_data: str | None,
    from_byte: int | None,
    frame_size: int | None,
    webhook_headers: str | None,
    webhook_params: str | None,
    webhook_payload: str | None,
    webhook_url: str | None,
    verbose: bool,
    debug: bool,
) -> None:
    """Execute a connector block (requires Ruby)

    PATH: Block path (e.g., actions.search.execute, triggers.new_record.poll,
    methods.my_method, pick_lists.my_list, object_definitions.my_obj)
    """
    from workato_platform_cli.cli.commands.sdk.ruby_executor import (
        check_ruby_installed,
        execute_block,
    )

    if not check_ruby_installed():
        raise click.ClickException(
            "Ruby is not installed. Install Ruby to use 'sdk exec'.\n"
            "  macOS: brew install ruby"
        )

    click.echo(f"🔧 Executing: {path}")

    # Resolve settings (decrypt .enc files)
    settings_resolved = _resolve_settings(settings, key_path)

    # Resolve paths to absolute
    connector_abs = str(Path(connector).resolve())
    settings_abs = str(Path(settings_resolved).resolve()) if settings_resolved else None
    input_abs = str(Path(input_file).resolve()) if input_file else None
    output_abs = str(Path(output_file).resolve()) if output_file else None

    def _resolve_opt(p: str | None) -> str | None:
        return str(Path(p).resolve()) if p else None

    exit_code, stdout, stderr = execute_block(
        connector_path=connector_abs,
        block_path=path,
        settings_path=settings_abs,
        connection_name=connection_name,
        input_path=input_abs,
        output_path=output_abs,
        closure_path=_resolve_opt(closure),
        args_path=_resolve_opt(args_file),
        extended_input_schema_path=_resolve_opt(extended_input_schema),
        extended_output_schema_path=_resolve_opt(extended_output_schema),
        config_fields_path=_resolve_opt(config_fields),
        continue_path=_resolve_opt(continue_data),
        from_byte=from_byte,
        frame_size=frame_size,
        webhook_headers=webhook_headers,
        webhook_params=webhook_params,
        webhook_payload_path=_resolve_opt(webhook_payload),
        webhook_url=webhook_url,
        verbose=verbose,
        debug=debug,
    )

    # Check for auth errors and attempt token refresh
    needs_refresh = False
    if stdout.strip():
        try:
            import json as json_mod

            resp = json_mod.loads(stdout)
            if isinstance(resp, dict):
                code = resp.get("code", "")
                status = resp.get("status", "")
                if any(
                    k in str(code).lower() + str(status).lower()
                    for k in ("expired", "unauthorized", "401", "403")
                ):
                    needs_refresh = True
        except (json_mod.JSONDecodeError, ValueError):
            pass

    if needs_refresh and settings_abs:
        click.echo("🔄 Token expired. Attempting refresh...")
        refreshed = _try_token_refresh(connector_abs, settings_abs, connection_name)
        if refreshed:
            # Update settings file with new tokens
            _save_tokens_to_settings(settings, key_path, refreshed)

            # Re-resolve settings and retry
            settings_resolved = _resolve_settings(settings, key_path)
            settings_abs = (
                str(Path(settings_resolved).resolve()) if settings_resolved else None
            )

            click.echo("🔧 Retrying with refreshed token...")
            exit_code, stdout, stderr = execute_block(
                connector_path=connector_abs,
                block_path=path,
                settings_path=settings_abs,
                connection_name=connection_name,
                input_path=input_abs,
                output_path=output_abs,
                closure_path=_resolve_opt(closure),
                args_path=_resolve_opt(args_file),
                extended_input_schema_path=_resolve_opt(extended_input_schema),
                extended_output_schema_path=_resolve_opt(extended_output_schema),
                config_fields_path=_resolve_opt(config_fields),
                continue_path=_resolve_opt(continue_data),
                from_byte=from_byte,
                frame_size=frame_size,
                webhook_headers=webhook_headers,
                webhook_params=webhook_params,
                webhook_payload_path=_resolve_opt(webhook_payload),
                webhook_url=webhook_url,
                verbose=verbose,
                debug=debug,
            )

    if stdout.strip():
        click.echo(stdout)
    if stderr.strip():
        click.echo(stderr, err=True)

    if exit_code != 0:
        raise click.ClickException(f"Execution failed with exit code {exit_code}")


def _try_token_refresh(
    connector_path: str,
    settings_path: str,
    connection_name: str | None,
) -> dict[str, str] | None:
    """Try to refresh the OAuth2 token using the connector's refresh lambda."""
    from workato_platform_cli.cli.commands.sdk.ruby_executor import (
        execute_block,
    )

    exit_code, stdout, stderr = execute_block(
        connector_path=connector_path,
        block_path="connection.authorization.refresh",
        settings_path=settings_path,
        connection_name=connection_name,
    )

    if exit_code == 0 and stdout.strip():
        try:
            import json as json_mod

            result = json_mod.loads(stdout)
            if isinstance(result, dict) and "access_token" in result:
                click.echo("✅ Token refreshed successfully")
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    click.echo("⚠️  Token refresh failed. Please re-authenticate.")
    return None


# --- sdk oauth2 ---


@sdk.command(name="oauth2")
@click.option("--connector", "-c", default="connector.rb", help="Connector file path")
@click.option("--settings", "-s", default=None, help="Settings file path")
@click.option(
    "--key", "-k", "key_path", default="master.key", help="Encryption key file"
)
@click.option(
    "--connection",
    "-n",
    "connection_name",
    default=None,
    help="Connection name (for multiple credential sets)",
)
@click.option("--port", default=45555, type=int, help="Callback server port")
@click.option("--ip", default="127.0.0.1", help="Callback server IP")
@click.option(
    "--https/--no-https",
    "use_https",
    default=False,
    help="Use HTTPS with self-signed certificate",
)
@click.option("--verbose", is_flag=True, help="Show HTTP requests/responses")
@handle_cli_exceptions
async def oauth2(
    connector: str,
    settings: str | None,
    key_path: str,
    connection_name: str | None,
    port: int,
    ip: str,
    use_https: bool,
    verbose: bool,
) -> None:
    """Run OAuth2 authorization flow (requires Ruby for connector parsing)"""
    import json as json_mod

    from workato_platform_cli.cli.commands.sdk.oauth2_flow import (
        run_oauth2_flow,
    )

    settings_resolved = _resolve_settings(settings, key_path)

    click.echo("🔐 Starting OAuth2 authorization flow...")

    token_response = await run_oauth2_flow(
        connector_path=connector,
        settings_path=settings_resolved,
        port=port,
        ip=ip,
        use_https=use_https,
        verbose=verbose,
    )

    click.echo("✅ OAuth2 flow completed")
    click.echo()
    click.echo(json_mod.dumps(token_response, indent=2))

    # Save tokens to settings file
    _save_tokens_to_settings(settings, key_path, token_response)


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
        fd = os.open(str(key_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, new_key.encode())
        finally:
            os.close(fd)
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
    editor = os.environ.get("VISUAL", os.environ.get("EDITOR", "vi"))

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
