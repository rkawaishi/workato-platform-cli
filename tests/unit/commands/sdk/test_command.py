"""Tests for SDK CLI commands."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, Mock

import pytest

from workato_platform_cli.cli.commands.sdk.command import (
    exec_connector,
    generate_schema,
    new_connector,
    push,
)


if TYPE_CHECKING:
    from workato_platform_cli import Workato


def _get_callback(cmd: Any) -> Callable[..., Any]:
    callback = cmd.callback
    assert callback is not None
    return cast(Callable[..., Any], callback)


def _workato_stub(**kwargs: Any) -> Workato:
    return cast("Workato", Mock(**kwargs))


class DummySpinner:
    def __init__(self, _message: str) -> None:
        self.message = _message

    def start(self) -> None:
        pass

    def stop(self) -> float:
        return 0.1


@pytest.fixture(autouse=True)
def patch_spinner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "workato_platform_cli.cli.commands.sdk.command.Spinner",
        DummySpinner,
    )


@pytest.fixture(autouse=True)
def capture_echo(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    captured: list[str] = []

    def _capture(message: str = "") -> None:
        captured.append(message)

    monkeypatch.setattr(
        "workato_platform_cli.cli.commands.sdk.command.click.echo",
        _capture,
    )
    # Also patch connector_pusher's click.echo
    monkeypatch.setattr(
        "workato_platform_cli.cli.commands.sdk.connector_pusher.click.echo",
        _capture,
    )
    return captured


@pytest.mark.asyncio
async def test_new_connector_creates_project(
    tmp_path: Path,
    capture_echo: list[str],
) -> None:
    project_path = tmp_path / "test-connector"

    new_cb = _get_callback(new_connector)
    await new_cb(path=str(project_path))

    output = "\n".join(capture_echo)
    assert "Connector project created" in output
    assert (project_path / "connector.rb").exists()


@pytest.mark.asyncio
async def test_new_connector_fails_if_dir_not_empty(
    tmp_path: Path,
    capture_echo: list[str],
) -> None:
    project_path = tmp_path / "existing"
    project_path.mkdir()
    (project_path / "file.txt").write_text("existing")

    new_cb = _get_callback(new_connector)
    with pytest.raises(SystemExit):
        await new_cb(path=str(project_path))

    output = "\n".join(capture_echo)
    assert "not empty" in output


@pytest.mark.asyncio
async def test_push_creates_connector(
    tmp_path: Path,
    capture_echo: list[str],
) -> None:
    connector_file = tmp_path / "connector.rb"
    connector_file.write_text("{title: 'Test'}")

    mock_response = Mock(id=123, title="Test", latest_released_version=1)
    workato_client = _workato_stub(
        connectors_api=Mock(
            create_custom_connector=AsyncMock(return_value=mock_response),
            release_custom_connector=AsyncMock(return_value=mock_response),
        )
    )

    push_cb = _get_callback(push)
    await push_cb(
        connector=str(connector_file),
        title="Test",
        description=None,
        notes=None,
        connector_id=None,
        no_release=False,
        workato_api_client=workato_client,
    )

    output = "\n".join(capture_echo)
    assert "created" in output.lower() or "Created" in output
    assert "Released" in output


@pytest.mark.asyncio
async def test_push_updates_existing_connector(
    tmp_path: Path,
    capture_echo: list[str],
) -> None:
    connector_file = tmp_path / "connector.rb"
    connector_file.write_text("{title: 'Updated'}")

    mock_response = Mock(id=456, title="Updated", latest_released_version=2)
    workato_client = _workato_stub(
        connectors_api=Mock(
            update_custom_connector=AsyncMock(return_value=mock_response),
            release_custom_connector=AsyncMock(return_value=mock_response),
        )
    )

    push_cb = _get_callback(push)
    await push_cb(
        connector=str(connector_file),
        title="Updated",
        description=None,
        notes=None,
        connector_id=456,
        no_release=False,
        workato_api_client=workato_client,
    )

    output = "\n".join(capture_echo)
    assert "updated" in output.lower() or "Updated" in output


@pytest.mark.asyncio
async def test_generate_schema_json(
    tmp_path: Path,
    capture_echo: list[str],
) -> None:
    json_file = tmp_path / "sample.json"
    json_file.write_text('{"name": "test", "count": 42}')

    schema_result = {"type": "object", "properties": {"name": {"type": "string"}}}
    workato_client = _workato_stub(
        sdk_api=Mock(
            generate_schema_from_json=AsyncMock(return_value=schema_result),
        )
    )

    gen_cb = _get_callback(generate_schema)
    await gen_cb(
        json_file=str(json_file),
        csv_file=None,
        col_sep=None,
        workato_api_client=workato_client,
    )

    output = "\n".join(capture_echo)
    assert "Generated Schema" in output


@pytest.mark.asyncio
async def test_generate_schema_requires_file(capture_echo: list[str]) -> None:
    workato_client = _workato_stub()

    gen_cb = _get_callback(generate_schema)
    with pytest.raises(SystemExit):
        await gen_cb(
            json_file=None,
            csv_file=None,
            col_sep=None,
            workato_api_client=workato_client,
        )

    output = "\n".join(capture_echo)
    assert "json-file" in output or "csv-file" in output


@pytest.mark.asyncio
async def test_exec_checks_ruby(
    monkeypatch: pytest.MonkeyPatch,
    capture_echo: list[str],
) -> None:
    monkeypatch.setattr(
        "workato_platform_cli.cli.commands.sdk.command.SdkRunner.check_ruby_installed",
        lambda self: False,
    )

    exec_cb = _get_callback(exec_connector)
    with pytest.raises(SystemExit):
        await exec_cb(
            path="actions.test.execute",
            connector="connector.rb",
            settings=None,
            input_file=None,
            output_file=None,
            verbose=False,
        )

    output = "\n".join(capture_echo)
    assert "Ruby is not installed" in output
