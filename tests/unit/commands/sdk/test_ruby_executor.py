"""Tests for Ruby executor."""

from __future__ import annotations

from workato_platform_cli.cli.commands.sdk.ruby_executor import (
    build_ruby_script,
)


def test_build_ruby_script_basic() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="actions.search.execute",
    )

    assert "connector.rb" in script
    assert "connector.dig(:actions, :search, :execute)" in script
    assert "settings = {}" in script


def test_build_ruby_script_with_settings() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="test",
        settings_path="settings.yaml",
    )

    assert "YAML.load_file" in script
    assert "settings.yaml" in script


def test_build_ruby_script_with_json_settings() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="test",
        settings_path="settings.json",
    )

    assert "JSON.parse" in script
    assert "settings.json" in script


def test_build_ruby_script_with_input() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="actions.create.execute",
        input_path="input.json",
    )

    assert "input.json" in script
    assert "input = JSON.parse" in script


def test_build_ruby_script_methods() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="methods.my_helper",
    )

    assert "connector.dig(:methods, :my_helper)" in script


def test_build_ruby_script_with_connection_name() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="test",
        settings_path="settings.yaml",
        connection_name="production",
    )

    assert "all_settings['production']" in script


def test_build_ruby_script_with_closure() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="triggers.new_deal.poll",
        closure_path="closure.json",
    )

    assert "closure = JSON.parse" in script
    assert "closure.json" in script


def test_build_ruby_script_pick_lists() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="pick_lists.deal_types",
    )

    assert "connector.dig(:pick_lists, :deal_types)" in script


def test_build_ruby_script_object_definitions() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="object_definitions.deal",
    )

    assert "connector.dig(:object_definitions, :deal)" in script


def test_build_ruby_script_has_auth_apply() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="test",
    )

    assert "$auth_headers" in script
    assert "apply_auth" in script


def test_build_ruby_script_has_base_uri() -> None:
    script = build_ruby_script(
        connector_path="connector.rb",
        block_path="test",
    )

    assert "$base_uri" in script
    assert "resolve_url" in script
