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
    assert "[:actions][:search][:execute]" in script
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

    assert "[:methods][:my_helper]" in script
