"""Tests for connector scaffold generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from workato_platform_cli.cli.commands.sdk.scaffold import generate_scaffold


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return tmp_path / "my-connector"


def test_generate_scaffold_creates_files(project_dir: Path) -> None:
    created = generate_scaffold(project_dir, "my-connector")

    assert "connector.rb" in created
    assert "Gemfile" in created
    assert ".rspec" in created
    assert ".gitignore" in created
    assert "settings.yaml" in created
    assert "spec/spec_helper.rb" in created
    assert "spec/connector_spec.rb" in created


def test_generate_scaffold_connector_has_title(project_dir: Path) -> None:
    generate_scaffold(project_dir, "my-connector")

    content = (project_dir / "connector.rb").read_text()
    assert "title: 'My Connector'" in content


def test_generate_scaffold_creates_directories(project_dir: Path) -> None:
    generate_scaffold(project_dir, "test")

    assert (project_dir / "spec").is_dir()
    assert (project_dir / "fixtures" / "actions").is_dir()
    assert (project_dir / "fixtures" / "triggers").is_dir()
    assert (project_dir / "fixtures" / "methods").is_dir()
    assert (project_dir / "tape_library").is_dir()


def test_generate_scaffold_gemfile_has_sdk(project_dir: Path) -> None:
    generate_scaffold(project_dir, "test")

    content = (project_dir / "Gemfile").read_text()
    assert "workato-connector-sdk" in content
    assert "rspec" in content


def test_generate_scaffold_gitignore_has_master_key(project_dir: Path) -> None:
    generate_scaffold(project_dir, "test")

    content = (project_dir / ".gitignore").read_text()
    assert "master.key" in content


def test_generate_scaffold_spec_helper_has_vcr(project_dir: Path) -> None:
    generate_scaffold(project_dir, "test")

    content = (project_dir / "spec" / "spec_helper.rb").read_text()
    assert "VCR.configure" in content
    assert "tape_library" in content
