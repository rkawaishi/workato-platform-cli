"""Tests for jobs CLI commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, Mock

import pytest

from workato_platform_cli.cli.commands.jobs import (
    get_job,
    list_jobs,
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
        "workato_platform_cli.cli.commands.jobs.Spinner",
        DummySpinner,
    )


@pytest.fixture(autouse=True)
def capture_echo(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    captured: list[str] = []

    def _capture(message: str = "") -> None:
        captured.append(message)

    monkeypatch.setattr(
        "workato_platform_cli.cli.commands.jobs.click.echo",
        _capture,
    )
    return captured


@pytest.mark.asyncio
async def test_list_jobs_empty(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    workato_client = _workato_stub(
        jobs_api=Mock(
            list_jobs=AsyncMock(
                return_value=Mock(
                    items=[],
                    job_succeeded_count=0,
                    job_failed_count=0,
                    job_count=0,
                    job_scope_count=0,
                )
            )
        )
    )

    list_cb = _get_callback(list_jobs)
    await list_cb(
        recipe_id=123,
        status=None,
        rerun_only=False,
        workato_api_client=workato_client,
    )

    output = "\n".join(capture_echo)
    assert "No jobs found" in output
    assert "Recipe 123" in output


@pytest.mark.asyncio
async def test_list_jobs_with_entries(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    job1 = Mock(
        id="1001",
        title="New Salesforce record",
        status="succeeded",
        started_at="2025-01-01T00:00:00Z",
        completed_at="2025-01-01T00:00:05Z",
        error=None,
    )
    job2 = Mock(
        id="1002",
        title="Failed sync",
        status="failed",
        started_at="2025-01-01T01:00:00Z",
        completed_at="2025-01-01T01:00:03Z",
        error="Connection timeout",
    )

    workato_client = _workato_stub(
        jobs_api=Mock(
            list_jobs=AsyncMock(
                return_value=Mock(
                    items=[job1, job2],
                    job_succeeded_count=1,
                    job_failed_count=1,
                    job_count=2,
                    job_scope_count=2,
                )
            )
        )
    )

    list_cb = _get_callback(list_jobs)
    await list_cb(
        recipe_id=456,
        status=None,
        rerun_only=False,
        workato_api_client=workato_client,
    )

    output = "\n".join(capture_echo)
    assert "1001" in output
    assert "New Salesforce record" in output
    assert "1002" in output
    assert "Connection timeout" in output
    assert "Succeeded: 1" in output
    assert "Failed: 1" in output


@pytest.mark.asyncio
async def test_list_jobs_with_status_filter(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    job = Mock(
        id="2001",
        title="Succeeded job",
        status="succeeded",
        started_at="2025-01-01T00:00:00Z",
        completed_at="2025-01-01T00:00:01Z",
        error=None,
    )

    mock_list_jobs = AsyncMock(
        return_value=Mock(
            items=[job],
            job_succeeded_count=1,
            job_failed_count=0,
            job_count=1,
            job_scope_count=1,
        )
    )
    workato_client = _workato_stub(
        jobs_api=Mock(list_jobs=mock_list_jobs)
    )

    list_cb = _get_callback(list_jobs)
    await list_cb(
        recipe_id=789,
        status="succeeded",
        rerun_only=False,
        workato_api_client=workato_client,
    )

    mock_list_jobs.assert_called_once_with(
        recipe_id=789,
        status="succeeded",
        rerun_only=None,
    )


@pytest.mark.asyncio
async def test_get_job(
    monkeypatch: pytest.MonkeyPatch, capture_echo: list[str]
) -> None:
    line1 = Mock(
        recipe_line_number=1,
        adapter_name="salesforce",
        adapter_operation="search_records",
        line_stat={"total": 1.23},
    )
    line2 = Mock(
        recipe_line_number=2,
        adapter_name="slack",
        adapter_operation="post_message",
        line_stat={"total": 0.45},
    )

    job_detail = Mock(
        id="3001",
        title="Sync contacts",
        status="succeeded",
        recipe_id=100,
        started_at="2025-01-01T00:00:00Z",
        completed_at="2025-01-01T00:00:05Z",
        error=None,
        is_repeat=False,
        is_test=False,
        calling_recipe_id=None,
        calling_job_id=None,
        root_recipe_id=None,
        root_job_id=None,
        lines=[line1, line2],
    )

    workato_client = _workato_stub(
        jobs_api=Mock(
            get_job=AsyncMock(return_value=job_detail)
        )
    )

    get_cb = _get_callback(get_job)
    await get_cb(
        recipe_id=100,
        job_id="3001",
        workato_api_client=workato_client,
    )

    output = "\n".join(capture_echo)
    assert "3001" in output
    assert "Sync contacts" in output
    assert "salesforce" in output
    assert "search_records" in output
    assert "slack" in output
    assert "post_message" in output
    assert "Execution Steps (2 steps)" in output
