"""OAuth2 authorization code flow for connector development."""

from __future__ import annotations

import asyncio
import webbrowser

from pathlib import Path
from urllib.parse import urlencode

import asyncclick as click

from aiohttp import web


async def run_oauth2_flow(
    connector_path: str,
    settings_path: str | None = None,
    port: int = 45555,
    ip: str = "127.0.0.1",
) -> dict[str, str]:
    """Run OAuth2 authorization code flow.

    1. Reads OAuth config from connector.rb via Ruby
    2. Opens browser to authorization URL
    3. Starts local HTTP server to receive callback
    4. Exchanges authorization code for tokens

    Returns dict with token response fields.
    """
    # Extract OAuth config from connector using Ruby
    oauth_config = _extract_oauth_config(connector_path, settings_path)

    authorize_url = oauth_config.get("authorize_url")
    token_url = oauth_config.get("token_url")
    client_id = oauth_config.get("client_id")
    client_secret = oauth_config.get("client_secret")
    scope = oauth_config.get("scope")

    if not authorize_url:
        raise click.ClickException(
            "Could not extract authorize_url from connector. "
            "Ensure connection.authorization has type: 'oauth2' "
            "with authorization_url defined."
        )

    redirect_uri = f"http://{ip}:{port}/callback"

    # Build authorization URL
    params: dict[str, str] = {
        "response_type": "code",
        "redirect_uri": redirect_uri,
    }
    if client_id:
        params["client_id"] = client_id
    if scope:
        params["scope"] = scope

    sep = "&" if "?" in authorize_url else "?"
    auth_url = f"{authorize_url}{sep}{urlencode(params)}"

    # Captured values
    result: dict[str, str] = {}
    event = asyncio.Event()

    async def handle_callback(request: web.Request) -> web.Response:
        code = request.query.get("code")
        error = request.query.get("error")

        if error:
            result["error"] = error
            event.set()
            return web.Response(
                text="Authorization failed. You can close this window.",
                content_type="text/plain",
            )

        if code:
            result["code"] = code
            event.set()
            return web.Response(
                text="Authorization successful! You can close this window.",
                content_type="text/plain",
            )

        event.set()
        return web.Response(
            text="No authorization code received.",
            content_type="text/plain",
        )

    # Start server and open browser
    app = web.Application()
    app.router.add_get("/callback", handle_callback)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, ip, port)
    await site.start()

    click.echo(f"🌐 Listening on http://{ip}:{port}/callback")
    click.echo(f"🔗 Opening browser: {auth_url[:80]}...")
    webbrowser.open(auth_url)

    # Wait for callback
    try:
        await asyncio.wait_for(event.wait(), timeout=300)
    except TimeoutError as e:
        raise click.ClickException("OAuth2 flow timed out (5 minutes)") from e
    finally:
        await runner.cleanup()

    if "error" in result:
        raise click.ClickException(f"Authorization failed: {result['error']}")

    if "code" not in result:
        raise click.ClickException("No authorization code received")

    # Exchange code for token
    if token_url:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            token_data = {
                "grant_type": "authorization_code",
                "code": result["code"],
                "redirect_uri": redirect_uri,
            }
            if client_id:
                token_data["client_id"] = client_id
            if client_secret:
                token_data["client_secret"] = client_secret

            async with session.post(token_url, data=token_data) as resp:
                token_response: dict[str, str] = await resp.json()
                return token_response

    return {"code": result["code"]}


def _extract_oauth_config(
    connector_path: str,
    settings_path: str | None = None,
) -> dict[str, str]:
    """Extract OAuth configuration from connector.rb using Ruby."""
    import shutil
    import subprocess  # noqa: S404
    import textwrap

    ruby_path = shutil.which("ruby")
    if ruby_path is None:
        raise click.ClickException("Ruby is not installed")

    abs_connector = str(Path(connector_path).resolve())

    settings_code = ""
    if settings_path:
        abs_settings = str(Path(settings_path).resolve())
        p = Path(abs_settings)
        if p.suffix in (".yaml", ".yml"):
            settings_code = f"""
require 'yaml'
settings = YAML.load_file('{abs_settings}')
"""
        else:
            settings_code = f"""
require 'json'
settings = JSON.parse(File.read('{abs_settings}'))
"""
    else:
        settings_code = "settings = {}\n"

    # Ruby helper to extract a field from auth config
    ruby_extract = (
        "def extract(auth, key, settings)\n"
        "  v = auth[key]\n"
        "  if v.is_a?(Proc)\n"
        "    v.call(settings).to_s rescue nil\n"
        "  elsif v.is_a?(String)\n"
        "    v\n"
        "  else\n"
        "    settings[key.to_s] rescue nil\n"
        "  end\n"
        "end\n"
    )

    script = textwrap.dedent(f"""\
        require 'json'

        {ruby_extract}
        connector = eval(File.read('{abs_connector}'))
        {settings_code}

        auth = connector[:connection][:authorization] rescue {{}}
        result = {{}}

        url = extract(auth, :authorization_url, settings)
        result['authorize_url'] = url if url

        url = extract(auth, :token_url, settings)
        result['token_url'] = url if url

        v = extract(auth, :client_id, settings)
        result['client_id'] = v if v

        v = extract(auth, :client_secret, settings)
        result['client_secret'] = v if v

        if auth[:scope].is_a?(Array)
          result['scope'] = auth[:scope].join(' ')
        elsif auth[:scope].is_a?(String)
          result['scope'] = auth[:scope]
        end

        puts JSON.generate(result)
    """)

    proc = subprocess.run(  # noqa: S603
        [ruby_path, "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if proc.returncode != 0:
        raise click.ClickException(
            f"Failed to extract OAuth config: {proc.stderr.strip()}"
        )

    import json

    result: dict[str, str] = json.loads(proc.stdout.strip())
    return result
