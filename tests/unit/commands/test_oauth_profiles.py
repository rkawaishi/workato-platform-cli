"""Tests for Custom OAuth Profile CLI commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, Mock

import pytest

from workato_platform_cli.cli.commands.oauth_profiles import (
    create_profile,
    delete_profile,
    get_profile,
    list_profiles,
    update_profile,
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
        "workato_platform_cli.cli.commands.oauth_profiles.Spinner",
        DummySpinner,
    )


@pytest.fixture(autouse=True)
def capture_echo(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    captured: list[str] = []

    def _capture(message: str = "") -> None:
        captured.append(message)

    monkeypatch.setattr(
        "workato_platform_cli.cli.commands.oauth_profiles.click.echo",
        _capture,
    )
    return captured


def _mock_profile(
    id: int = 1,
    name: str = "My App",
    provider: str = "salesforce",
    client_id: str = "abc123",
) -> Mock:
    return Mock(
        id=id,
        name=name,
        provider=provider,
        data=Mock(client_id=client_id),
        shared_accounts_count=2,
        oem_customers_count=0,
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-02T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_list_profiles_empty(capture_echo: list[str]) -> None:
    workato_client = _workato_stub(
        oauth_profiles_api=Mock(
            list_custom_oauth_profiles=AsyncMock(return_value=Mock(result=[]))
        )
    )

    cb = _get_callback(list_profiles)
    await cb(workato_api_client=workato_client)

    output = "\n".join(capture_echo)
    assert "No custom OAuth profiles found" in output


@pytest.mark.asyncio
async def test_list_profiles_with_entries(capture_echo: list[str]) -> None:
    profiles = [
        _mock_profile(id=1, name="SF App"),
        _mock_profile(id=2, name="Slack App"),
    ]
    workato_client = _workato_stub(
        oauth_profiles_api=Mock(
            list_custom_oauth_profiles=AsyncMock(return_value=Mock(result=profiles))
        )
    )

    cb = _get_callback(list_profiles)
    await cb(workato_api_client=workato_client)

    output = "\n".join(capture_echo)
    assert "2 found" in output
    assert "SF App" in output
    assert "Slack App" in output


@pytest.mark.asyncio
async def test_get_profile(capture_echo: list[str]) -> None:
    profile = _mock_profile()
    workato_client = _workato_stub(
        oauth_profiles_api=Mock(
            get_custom_oauth_profile=AsyncMock(return_value=profile)
        )
    )

    cb = _get_callback(get_profile)
    await cb(profile_id=1, workato_api_client=workato_client)

    output = "\n".join(capture_echo)
    assert "My App" in output
    assert "salesforce" in output
    assert "abc123" in output


@pytest.mark.asyncio
async def test_create_profile(capture_echo: list[str]) -> None:
    profile = _mock_profile(id=10, name="New App")
    workato_client = _workato_stub(
        oauth_profiles_api=Mock(
            create_custom_oauth_profile=AsyncMock(return_value=profile)
        )
    )

    cb = _get_callback(create_profile)
    await cb(
        name="New App",
        provider="salesforce",
        client_id="id123",
        client_secret="secret456",
        token=None,
        workato_api_client=workato_client,
    )

    output = "\n".join(capture_echo)
    assert "created" in output.lower()
    assert "New App" in output


@pytest.mark.asyncio
async def test_update_profile(capture_echo: list[str]) -> None:
    profile = _mock_profile(id=5, name="Updated App")
    workato_client = _workato_stub(
        oauth_profiles_api=Mock(
            update_custom_oauth_profile=AsyncMock(return_value=profile)
        )
    )

    cb = _get_callback(update_profile)
    await cb(
        profile_id=5,
        name="Updated App",
        provider="slack",
        client_id="new_id",
        client_secret="new_secret",
        token=None,
        workato_api_client=workato_client,
    )

    output = "\n".join(capture_echo)
    assert "updated" in output.lower()
    assert "Updated App" in output


@pytest.mark.asyncio
async def test_delete_profile(capture_echo: list[str]) -> None:
    workato_client = _workato_stub(
        oauth_profiles_api=Mock(
            delete_custom_oauth_profile=AsyncMock(
                return_value={"result": {"success": True}}
            )
        )
    )

    cb = _get_callback(delete_profile)
    await cb(profile_id=99, workato_api_client=workato_client)

    output = "\n".join(capture_echo)
    assert "deleted" in output.lower()
    assert "99" in output
