"""Execute connector blocks using Ruby directly (no gem required)."""

from __future__ import annotations

import shutil
import subprocess  # noqa: S404
import sys
import textwrap

from pathlib import Path


def check_ruby_installed() -> bool:
    """Check if Ruby is available on the system."""
    return shutil.which("ruby") is not None


def _escape_ruby_str(value: str) -> str:
    """Escape for Ruby single-quoted string literals."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _load_json_file_code(var_name: str, path: str | None) -> str:
    """Generate Ruby code to load a JSON file into a variable."""
    if path:
        safe = _escape_ruby_str(path)
        return f"{var_name} = JSON.parse(File.read('{safe}'))\n"
    return f"{var_name} = {{}}\n"


def _load_settings_code(
    settings_path: str | None,
    connection_name: str | None = None,
) -> str:
    """Generate Ruby code to load settings."""
    if not settings_path:
        return "settings = {}\n"

    p = Path(settings_path)
    if p.suffix in (".yaml", ".yml"):
        code = textwrap.dedent(f"""\
            require 'yaml'
            all_settings = YAML.load_file('{_escape_ruby_str(settings_path)}')
        """)
    else:
        code = textwrap.dedent(f"""\
            all_settings = JSON.parse(File.read('{_escape_ruby_str(settings_path)}'))
        """)

    if connection_name:
        safe_name = _escape_ruby_str(connection_name)
        code += f"settings = all_settings['{safe_name}'] || all_settings\n"
    else:
        code += "settings = all_settings\n"

    return code


def _load_account_properties_code(
    account_properties_path: str | None,
) -> str:
    """Generate Ruby code to load account properties."""
    if not account_properties_path:
        return "account_properties = {}\n"

    p = Path(account_properties_path)
    safe = _escape_ruby_str(account_properties_path)
    if p.suffix in (".yaml", ".yml"):
        return (
            f"require 'yaml'\n"
            f"account_properties = YAML.load_file('{safe}') || {{}}\n"
        )
    return f"account_properties = JSON.parse(File.read('{safe}')) || {{}}\n"


def build_ruby_script(  # noqa: PLR0913
    connector_path: str,
    block_path: str,
    settings_path: str | None = None,
    connection_name: str | None = None,
    account_properties_path: str | None = None,
    input_path: str | None = None,
    closure_path: str | None = None,
    args_path: str | None = None,
    extended_input_schema_path: str | None = None,
    extended_output_schema_path: str | None = None,
    config_fields_path: str | None = None,
    continue_path: str | None = None,
    from_byte: int | None = None,
    frame_size: int | None = None,
    webhook_headers: str | None = None,
    webhook_params: str | None = None,
    webhook_payload_path: str | None = None,
    webhook_url: str | None = None,
) -> str:
    """Build a Ruby script that loads and executes a connector block."""
    settings_code = _load_settings_code(settings_path, connection_name)
    account_properties_code = _load_account_properties_code(account_properties_path)
    input_code = _load_json_file_code("input", input_path)
    closure_code = _load_json_file_code("closure", closure_path)
    args_code = _load_json_file_code("args_data", args_path)
    ext_in_code = _load_json_file_code(
        "extended_input_schema", extended_input_schema_path
    )
    ext_out_code = _load_json_file_code(
        "extended_output_schema", extended_output_schema_path
    )
    config_code = _load_json_file_code("config_fields", config_fields_path)
    continue_code = _load_json_file_code("continue_data", continue_path)
    webhook_payload_code = _load_json_file_code("webhook_payload", webhook_payload_path)

    # Webhook extras
    wh_headers = f"'{_escape_ruby_str(webhook_headers)}'" if webhook_headers else "nil"
    wh_params = f"'{_escape_ruby_str(webhook_params)}'" if webhook_params else "nil"
    wh_url = f"'{_escape_ruby_str(webhook_url)}'" if webhook_url else "nil"
    from_val = str(from_byte) if from_byte is not None else "nil"
    frame_val = str(frame_size) if frame_size is not None else "nil"

    # Navigate the connector hash using dig for safe access
    parts = block_path.split(".")
    dig_args = ", ".join(f":{p}" for p in parts)
    navigation = f"connector.dig({dig_args})"

    return textwrap.dedent(f"""\
        require 'json'
        require 'yaml' if defined?(YAML)
        require 'net/http'
        require 'uri'

        connector = eval(File.read('{_escape_ruby_str(connector_path)}'))

        {settings_code}
        {account_properties_code}
        {input_code}
        {closure_code}
        {args_code}
        {ext_in_code}
        {ext_out_code}
        {config_code}
        {continue_code}
        {webhook_payload_code}

        webhook_headers_raw = {wh_headers}
        webhook_params_raw = {wh_params}
        webhook_url = {wh_url}
        from_byte = {from_val}
        frame_size_val = {frame_val}

        # Capture auth headers from apply lambda
        $auth_headers = {{}}

        def headers(h = {{}})
          $auth_headers.merge!(
            h.transform_keys(&:to_s)
          )
        end

        apply_block = connector.dig(
          :connection, :authorization, :apply
        )
        if apply_block.is_a?(Proc)
          token = settings['access_token'] || ''
          case apply_block.arity.abs
          when 1
            apply_block.call(settings)
          when 2
            apply_block.call(settings, token)
          end
        end

        # Resolve base_uri from connector
        $base_uri = ''
        bu = connector.dig(:connection, :base_uri)
        if bu.is_a?(Proc)
          $base_uri = bu.call(settings).to_s rescue ''
        elsif bu.is_a?(String)
          $base_uri = bu
        end

        def resolve_url(path)
          if path.start_with?('http')
            path
          else
            $base_uri.chomp('/') + '/' + path.sub(/^\\//, '')
          end
        end

        def apply_auth(req)
          $auth_headers.each {{ |k, v| req[k] = v.to_s }}
          req
        end

        def get(path, params = {{}})
          url = resolve_url(path)
          uri = URI.parse(url)
          if params.is_a?(Hash) && !params.empty?
            uri.query = URI.encode_www_form(params)
          end
          req = apply_auth(Net::HTTP::Get.new(uri))
          res = Net::HTTP.start(uri.hostname, uri.port,
            use_ssl: uri.scheme == 'https') {{ |http|
            http.request(req) }}
          JSON.parse(res.body) rescue res.body
        end

        def post(path, body = nil, headers = {{}})
          url = resolve_url(path)
          uri = URI.parse(url)
          req = apply_auth(Net::HTTP::Post.new(uri))
          headers.each {{ |k, v| req[k.to_s] = v.to_s }}
          if body.is_a?(Hash)
            req.body = body.to_json
            req['Content-Type'] ||= 'application/json'
          elsif body
            req.body = body.to_s
          end
          res = Net::HTTP.start(uri.hostname, uri.port,
            use_ssl: uri.scheme == 'https') {{ |http|
            http.request(req) }}
          JSON.parse(res.body) rescue res.body
        end

        def put(path, body = nil, headers = {{}})
          url = resolve_url(path)
          uri = URI.parse(url)
          req = apply_auth(Net::HTTP::Put.new(uri))
          headers.each {{ |k, v| req[k.to_s] = v.to_s }}
          if body.is_a?(Hash)
            req.body = body.to_json
            req['Content-Type'] ||= 'application/json'
          elsif body
            req.body = body.to_s
          end
          res = Net::HTTP.start(uri.hostname, uri.port,
            use_ssl: uri.scheme == 'https') {{ |http|
            http.request(req) }}
          JSON.parse(res.body) rescue res.body
        end

        def patch(path, body = nil, headers = {{}})
          url = resolve_url(path)
          uri = URI.parse(url)
          req = apply_auth(Net::HTTP::Patch.new(uri))
          headers.each {{ |k, v| req[k.to_s] = v.to_s }}
          if body.is_a?(Hash)
            req.body = body.to_json
            req['Content-Type'] ||= 'application/json'
          elsif body
            req.body = body.to_s
          end
          res = Net::HTTP.start(uri.hostname, uri.port,
            use_ssl: uri.scheme == 'https') {{ |http|
            http.request(req) }}
          JSON.parse(res.body) rescue res.body
        end

        def delete(path, headers = {{}})
          url = resolve_url(path)
          uri = URI.parse(url)
          req = apply_auth(Net::HTTP::Delete.new(uri))
          headers.each {{ |k, v| req[k.to_s] = v.to_s }}
          res = Net::HTTP.start(uri.hostname, uri.port,
            use_ssl: uri.scheme == 'https') {{ |http|
            http.request(req) }}
          JSON.parse(res.body) rescue res.body
        end

        block = {navigation}

        if block.nil?
          STDERR.puts "Error: Block '{block_path}' not found"
          exit 1
        end

        if block.is_a?(Proc)
          a = block.arity.abs
          case a
          when 0 then result = block.call
          when 1 then result = block.call(settings)
          when 2 then result = block.call(settings, input)
          when 3 then result = block.call(settings, input, closure)
          when 4 then result = block.call(settings, input, closure, account_properties)
          else result = block.call(settings, input, closure, account_properties)
          end
        elsif block.is_a?(Hash)
          result = block.keys.map(&:to_s)
        else
          result = block
        end

        puts JSON.pretty_generate(result) rescue puts result.inspect
    """)


def execute_block(  # noqa: PLR0913
    connector_path: str,
    block_path: str,
    settings_path: str | None = None,
    connection_name: str | None = None,
    account_properties_path: str | None = None,
    input_path: str | None = None,
    output_path: str | None = None,
    closure_path: str | None = None,
    args_path: str | None = None,
    extended_input_schema_path: str | None = None,
    extended_output_schema_path: str | None = None,
    config_fields_path: str | None = None,
    continue_path: str | None = None,
    from_byte: int | None = None,
    frame_size: int | None = None,
    webhook_headers: str | None = None,
    webhook_params: str | None = None,
    webhook_payload_path: str | None = None,
    webhook_url: str | None = None,
    verbose: bool = False,
    debug: bool = False,
) -> tuple[int, str, str]:
    """Execute a connector block using Ruby.

    Returns (exit_code, stdout, stderr).
    """
    script = build_ruby_script(
        connector_path=connector_path,
        block_path=block_path,
        settings_path=settings_path,
        connection_name=connection_name,
        account_properties_path=account_properties_path,
        input_path=input_path,
        closure_path=closure_path,
        args_path=args_path,
        extended_input_schema_path=extended_input_schema_path,
        extended_output_schema_path=extended_output_schema_path,
        config_fields_path=config_fields_path,
        continue_path=continue_path,
        from_byte=from_byte,
        frame_size=frame_size,
        webhook_headers=webhook_headers,
        webhook_params=webhook_params,
        webhook_payload_path=webhook_payload_path,
        webhook_url=webhook_url,
    )

    ruby_path = shutil.which("ruby")
    if ruby_path is None:
        return 1, "", "Ruby is not installed"

    if verbose:
        sys.stderr.write(f"--- Ruby script ---\n{script}\n---\n")

    result = subprocess.run(  # noqa: S603
        [ruby_path, "-e", script],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if debug and result.returncode != 0:
        sys.stderr.write(f"--- DEBUG stderr ---\n{result.stderr}\n---\n")

    # Write output to file if requested
    if output_path and result.returncode == 0 and result.stdout.strip():
        Path(output_path).write_text(result.stdout)

    return result.returncode, result.stdout, result.stderr
