"""Unit tests for connectors CLI commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from workato_platform_cli.cli.commands.connectors import command
from workato_platform_cli.cli.commands.connectors.connector_manager import ProviderData


@pytest.fixture(autouse=True)
def capture_echo(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    captured: list[str] = []

    def _record(message: str = "") -> None:
        captured.append(message)

    monkeypatch.setattr(
        "workato_platform_cli.cli.commands.connectors.command.click.echo",
        _record,
    )
    return captured


@pytest.mark.asyncio
async def test_list_connectors_defaults(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    manager = Mock()

    connector = _make_connector("salesforce", "Salesforce")

    with (
        patch.object(
            manager,
            "list_platform_connectors",
            AsyncMock(return_value=[connector]),
        ) as mock_list_platform,
        patch.object(
            manager, "list_custom_connectors", AsyncMock()
        ) as mock_list_custom,
    ):
        assert command.list_connectors.callback

        await command.list_connectors.callback(
            platform=False,
            custom=False,
            provider=None,
            output_mode="table",
            connector_manager=manager,
        )

        mock_list_platform.assert_awaited_once()
        mock_list_custom.assert_awaited_once()
        assert any("Salesforce" in line for line in capture_echo)


@pytest.mark.asyncio
async def test_list_connectors_platform_only(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    manager = Mock()

    with (
        patch.object(manager, "list_platform_connectors", AsyncMock(return_value=[])),
        patch.object(
            manager, "list_custom_connectors", AsyncMock()
        ) as mock_list_custom,
    ):
        assert command.list_connectors.callback

        await command.list_connectors.callback(
            platform=True,
            custom=False,
            provider=None,
            output_mode="table",
            connector_manager=manager,
        )

        mock_list_custom.assert_not_awaited()
        assert any("No platform connectors" in line for line in capture_echo)


def _make_connector(
    name: str,
    title: str,
    triggers: list | None = None,
    actions: list | None = None,
) -> Mock:
    """Create a mock PlatformConnector."""
    c = Mock()
    c.name = name
    c.title = title
    c.triggers = triggers or []
    c.actions = actions or []
    c.to_dict.return_value = {
        "name": name,
        "title": title,
        "triggers": [{"name": t.name, "title": t.title} for t in (triggers or [])],
        "actions": [{"name": a.name, "title": a.title} for a in (actions or [])],
    }
    return c


def _make_action(
    name: str,
    title: str = "",
    deprecated: bool = False,
    bulk: bool = False,
    batch: bool = False,
) -> Mock:
    a = Mock()
    a.name = name
    a.title = title or name
    a.deprecated = deprecated
    a.bulk = bulk
    a.batch = batch
    return a


@pytest.mark.asyncio
async def test_list_connectors_platform_shows_triggers_actions_count(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    triggers = [_make_action("new_issue"), _make_action("updated_issue")]
    actions = [_make_action("create_issue")]
    connector = _make_connector("jira", "Jira", triggers, actions)
    manager = Mock()

    with (
        patch.object(
            manager,
            "list_platform_connectors",
            AsyncMock(return_value=[connector]),
        ),
        patch.object(manager, "list_custom_connectors", AsyncMock()),
    ):
        assert command.list_connectors.callback
        await command.list_connectors.callback(
            platform=True,
            custom=False,
            provider=None,
            output_mode="table",
            connector_manager=manager,
        )

    output = "\n".join(capture_echo)
    assert "Jira (jira)" in output
    assert "triggers: 2" in output
    assert "actions: 1" in output


@pytest.mark.asyncio
async def test_list_connectors_provider_detail(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    triggers = [_make_action("new_message", "New message")]
    actions = [
        _make_action("post_message", "Post message"),
        _make_action("old_action", "Old action", deprecated=True),
    ]
    connector = _make_connector("slack", "Slack", triggers, actions)
    manager = Mock()

    with patch.object(
        manager,
        "list_platform_connectors",
        AsyncMock(return_value=[connector]),
    ):
        assert command.list_connectors.callback
        await command.list_connectors.callback(
            platform=False,
            custom=False,
            provider="slack",
            output_mode="table",
            connector_manager=manager,
        )

    output = "\n".join(capture_echo)
    assert "Slack (slack)" in output
    assert "new_message" in output
    assert "post_message" in output
    assert "[deprecated]" in output


@pytest.mark.asyncio
async def test_list_connectors_provider_not_found(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    manager = Mock()

    with patch.object(
        manager,
        "list_platform_connectors",
        AsyncMock(return_value=[]),
    ):
        assert command.list_connectors.callback
        await command.list_connectors.callback(
            platform=False,
            custom=False,
            provider="nonexistent",
            output_mode="table",
            connector_manager=manager,
        )

    assert any("not found" in line for line in capture_echo)


@pytest.mark.asyncio
async def test_list_connectors_provider_json_output(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    import json

    triggers = [_make_action("new_issue")]
    connector = _make_connector("jira", "Jira", triggers, [])
    manager = Mock()

    with patch.object(
        manager,
        "list_platform_connectors",
        AsyncMock(return_value=[connector]),
    ):
        assert command.list_connectors.callback
        await command.list_connectors.callback(
            platform=False,
            custom=False,
            provider="jira",
            output_mode="json",
            connector_manager=manager,
        )

    parsed = json.loads(capture_echo[0])
    assert parsed["name"] == "jira"
    assert len(parsed["triggers"]) == 1


@pytest.mark.asyncio
async def test_parameters_no_data(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    manager = Mock(load_connection_data=Mock(return_value={}))

    assert command.parameters.callback

    await command.parameters.callback(
        provider=None,
        oauth_only=False,
        search=None,
        show_all=False,
        pretty=False,
        connector_manager=manager,
    )

    assert any("data not found" in line for line in capture_echo)


@pytest.mark.asyncio
async def test_parameters_specific_provider(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    provider_data = ProviderData(name="Salesforce", provider="salesforce", oauth=True)
    manager = Mock(
        load_connection_data=Mock(return_value={"salesforce": provider_data}),
        show_provider_details=Mock(),
    )

    assert command.parameters.callback

    await command.parameters.callback(
        provider="salesforce",
        oauth_only=False,
        search=None,
        show_all=False,
        pretty=False,
        connector_manager=manager,
    )

    manager.show_provider_details.assert_called_once_with("salesforce", provider_data)


@pytest.mark.asyncio
async def test_parameters_provider_not_found(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    manager = Mock(
        load_connection_data=Mock(
            return_value={
                "jira": ProviderData(name="Jira", provider="jira", oauth=True)
            }
        )
    )

    assert command.parameters.callback

    await command.parameters.callback(
        provider="unknown",
        oauth_only=False,
        search=None,
        show_all=False,
        pretty=False,
        connector_manager=manager,
    )

    assert any("not found" in line for line in capture_echo)


@pytest.mark.asyncio
async def test_parameters_filtered_list(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    manager = Mock()
    connection_data = {
        "jira": ProviderData(
            name="Jira", provider="jira", oauth=True, secure_tunnel=True
        ),
        "mysql": ProviderData(name="MySQL", provider="mysql", oauth=False),
    }

    with patch.object(manager, "load_connection_data", return_value=connection_data):
        assert command.parameters.callback

        await command.parameters.callback(
            provider=None,
            oauth_only=True,
            search="ji",
            show_all=False,
            pretty=False,
            connector_manager=manager,
        )

        output = "\n".join(capture_echo)
        assert "Jira" in output
        assert "MySQL" not in output
        assert "secure tunnel" in output


@pytest.mark.asyncio
async def test_parameters_filtered_none(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    manager = Mock()
    connection_data = {
        "jira": ProviderData(name="Jira", provider="jira", oauth=True),
    }

    with patch.object(manager, "load_connection_data", return_value=connection_data):
        assert command.parameters.callback

        await command.parameters.callback(
            provider=None,
            oauth_only=False,
            search="sales",
            show_all=False,
            pretty=False,
            connector_manager=manager,
        )

        assert any("No providers" in line for line in capture_echo)


@pytest.mark.asyncio
async def test_parameters_all_flag_json_output(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    """Test that --all flag outputs single-line JSON"""
    import json

    manager = Mock()
    connection_data = {
        "jira": ProviderData(
            name="Jira", provider="jira", oauth=True, secure_tunnel=True
        ),
        "mysql": ProviderData(name="MySQL", provider="mysql", oauth=False),
    }

    with patch.object(manager, "load_connection_data", return_value=connection_data):
        assert command.parameters.callback

        await command.parameters.callback(
            provider=None,
            oauth_only=False,
            search=None,
            show_all=True,
            pretty=False,
            connector_manager=manager,
        )

        # Should output single-line JSON
        assert len(capture_echo) == 1, "Should output exactly one line"
        output = capture_echo[0]

        # Verify it's valid JSON
        parsed = json.loads(output)
        assert "jira" in parsed
        assert "mysql" in parsed
        assert parsed["jira"]["name"] == "Jira"
        assert parsed["mysql"]["oauth"] is False


@pytest.mark.asyncio
async def test_parameters_all_with_pretty_flag(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    """Test that --all --pretty flags output pretty-printed JSON"""
    import json

    manager = Mock()
    connection_data = {
        "jira": ProviderData(
            name="Jira", provider="jira", oauth=True, secure_tunnel=True
        ),
    }

    with patch.object(manager, "load_connection_data", return_value=connection_data):
        assert command.parameters.callback

        await command.parameters.callback(
            provider=None,
            oauth_only=False,
            search=None,
            show_all=True,
            pretty=True,
            connector_manager=manager,
        )

        # Get the output (should be a single echo call with embedded newlines)
        assert len(capture_echo) == 1, "Should output exactly one echo call"
        output = capture_echo[0]

        # Verify it's valid JSON
        parsed = json.loads(output)
        assert "jira" in parsed
        assert parsed["jira"]["name"] == "Jira"

        # Verify it has proper indentation (pretty-printed with indent=2)
        # Pretty-printed JSON should have newlines and indentation
        assert "\n" in output, "Pretty-printed JSON should contain newlines"
        assert '  "jira"' in output or '  "name"' in output, "Should have indented keys"

        # Verify the non-pretty version would be different (compact)
        compact = json.dumps(parsed)
        assert len(output) > len(compact), (
            "Pretty-printed should be longer than compact"
        )
