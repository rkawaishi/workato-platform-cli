"""Execute connector blocks using Ruby directly (no gem required)."""

from __future__ import annotations

import shutil
import subprocess  # noqa: S404
import textwrap

from pathlib import Path


def check_ruby_installed() -> bool:
    """Check if Ruby is available on the system."""
    return shutil.which("ruby") is not None


def build_ruby_script(
    connector_path: str,
    block_path: str,
    settings_path: str | None = None,
    input_path: str | None = None,
) -> str:
    """Build a Ruby script that loads and executes a connector block.

    Args:
        connector_path: Path to connector.rb
        block_path: Dot-separated path to the block
            (e.g., "actions.search.execute", "methods.my_method")
        settings_path: Optional path to settings YAML file
        input_path: Optional path to input JSON file
    """
    # Load settings
    settings_code = ""
    if settings_path:
        p = Path(settings_path)
        if p.suffix in (".yaml", ".yml"):
            settings_code = textwrap.dedent(f"""\
                require 'yaml'
                settings = YAML.load_file('{settings_path}')
            """)
        else:
            settings_code = textwrap.dedent(f"""\
                require 'json'
                settings = JSON.parse(File.read('{settings_path}'))
            """)
    else:
        settings_code = "settings = {}\n"

    # Load input
    input_code = ""
    if input_path:
        input_code = textwrap.dedent(f"""\
            require 'json'
            input = JSON.parse(File.read('{input_path}'))
        """)
    else:
        input_code = "input = {}\n"

    # Navigate the connector hash to find the target block
    parts = block_path.split(".")
    navigation = "connector"
    for part in parts:
        navigation += f"[:{part}]"

    return textwrap.dedent(f"""\
        require 'json'
        require 'yaml' if defined?(YAML)
        require 'net/http'
        require 'uri'

        connector = eval(File.read('{connector_path}'))

        {settings_code}
        {input_code}

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

        def get(path, params = {{}})
          url = resolve_url(path)
          uri = URI.parse(url)
          if params.is_a?(Hash) && !params.empty?
            uri.query = URI.encode_www_form(params)
          end
          req = Net::HTTP::Get.new(uri)
          res = Net::HTTP.start(uri.hostname, uri.port,
            use_ssl: uri.scheme == 'https') {{ |http|
            http.request(req) }}
          JSON.parse(res.body) rescue res.body
        end

        def post(path, body = nil, headers = {{}})
          url = resolve_url(path)
          uri = URI.parse(url)
          req = Net::HTTP::Post.new(uri)
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
          req = Net::HTTP::Put.new(uri)
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
          req = Net::HTTP::Patch.new(uri)
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
          req = Net::HTTP::Delete.new(uri)
          headers.each {{ |k, v| req[k.to_s] = v.to_s }}
          res = Net::HTTP.start(uri.hostname, uri.port,
            use_ssl: uri.scheme == 'https') {{ |http|
            http.request(req) }}
          JSON.parse(res.body) rescue res.body
        end

        block = {navigation}

        if block.nil?
          STDERR.puts "Error: Block '#{block_path}' not found in connector"
          exit 1
        end

        if block.is_a?(Proc)
          # Determine arity and call with appropriate args
          case block.arity.abs
          when 0
            result = block.call
          when 1
            result = block.call(settings)
          when 2
            result = block.call(settings, input)
          else
            result = block.call(settings, input)
          end
        elsif block.is_a?(Hash)
          # It's a nested hash, print its keys
          result = block.keys.map(&:to_s)
        else
          result = block
        end

        puts JSON.pretty_generate(result) rescue puts result.inspect
    """)


def execute_block(
    connector_path: str,
    block_path: str,
    settings_path: str | None = None,
    input_path: str | None = None,
    output_path: str | None = None,
    verbose: bool = False,
) -> tuple[int, str, str]:
    """Execute a connector block using Ruby.

    Returns (exit_code, stdout, stderr).
    """
    script = build_ruby_script(
        connector_path=connector_path,
        block_path=block_path,
        settings_path=settings_path,
        input_path=input_path,
    )

    ruby_path = shutil.which("ruby")
    if ruby_path is None:
        return 1, "", "Ruby is not installed"

    if verbose:
        import sys

        sys.stderr.write(f"--- Ruby script ---\n{script}\n---\n")

    result = subprocess.run(  # noqa: S603
        [ruby_path, "-e", script],
        capture_output=True,
        text=True,
        timeout=300,
    )

    # Write output to file if requested
    if output_path and result.returncode == 0 and result.stdout.strip():
        Path(output_path).write_text(result.stdout)

    return result.returncode, result.stdout, result.stderr
