import asyncclick as click

from dependency_injector.wiring import Provide, inject

from workato_platform_cli import Workato
from workato_platform_cli.cli.containers import Container
from workato_platform_cli.cli.utils import Spinner
from workato_platform_cli.cli.utils.exception_handler import (
    handle_api_exceptions,
    handle_cli_exceptions,
)
from workato_platform_cli.client.workato_api.models.job import Job
from workato_platform_cli.client.workato_api.models.job_detail import JobDetail


@click.group(name="jobs")
def jobs() -> None:
    """Manage recipe jobs"""
    pass


@jobs.command(name="list")
@click.option(
    "--recipe-id",
    required=True,
    type=int,
    help="Recipe ID to list jobs for",
)
@click.option(
    "--status",
    type=click.Choice(["succeeded", "failed", "pending"], case_sensitive=False),
    default=None,
    help="Filter by job status",
)
@click.option(
    "--rerun-only",
    is_flag=True,
    default=False,
    help="Show only rerun jobs",
)
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def list_jobs(
    recipe_id: int,
    status: str | None,
    rerun_only: bool,
    workato_api_client: Workato = Provide[Container.workato_api_client],
) -> None:
    """List jobs for a recipe"""
    spinner = Spinner("Fetching jobs")
    spinner.start()

    try:
        response = await workato_api_client.jobs_api.list_jobs(
            recipe_id=recipe_id,
            status=status,
            rerun_only=rerun_only if rerun_only else None,
        )
    finally:
        elapsed = spinner.stop()

    items = response.items or []
    click.echo(
        f"📋 Jobs for Recipe {recipe_id} ({len(items)} found) - ({elapsed:.1f}s)"
    )

    if response.job_count is not None:
        click.echo(
            f"  ✅ Succeeded: {response.job_succeeded_count or 0}  "
            f"❌ Failed: {response.job_failed_count or 0}  "
            f"📊 Total: {response.job_count}"
        )

    if not items:
        click.echo("  ℹ️  No jobs found")
        return

    click.echo()

    for job in items:
        display_job_summary(job)
        click.echo()

    click.echo("💡 Commands:")
    click.echo(
        f"  • Job details: workato jobs get --recipe-id {recipe_id} --job-id <JOB_ID>"
    )


@jobs.command(name="get")
@click.option(
    "--recipe-id",
    required=True,
    type=int,
    help="Recipe ID the job belongs to",
)
@click.option(
    "--job-id",
    required=True,
    type=str,
    help="Job ID to retrieve",
)
@handle_cli_exceptions
@inject
@handle_api_exceptions
async def get_job(
    recipe_id: int,
    job_id: str,
    workato_api_client: Workato = Provide[Container.workato_api_client],
) -> None:
    """Get detailed information about a specific job"""
    spinner = Spinner("Fetching job details")
    spinner.start()

    try:
        job = await workato_api_client.jobs_api.get_job(
            recipe_id=recipe_id,
            job_id=job_id,
        )
    finally:
        elapsed = spinner.stop()

    click.echo(f"📋 Job Details ({elapsed:.1f}s)")
    display_job_detail(job)


def display_job_summary(job: Job) -> None:
    """Display a summary of a job."""
    status_icon = _status_icon(job.status)
    click.echo(f"  {status_icon} Job {job.id}")
    if job.title:
        click.echo(f"     📝 Title: {job.title}")
    click.echo(f"     🔖 Status: {job.status or 'unknown'}")
    if job.started_at:
        click.echo(f"     🕐 Started: {job.started_at}")
    if job.completed_at:
        click.echo(f"     🕑 Completed: {job.completed_at}")
    if job.error:
        click.echo(f"     ⚠️  Error: {job.error}")


def display_job_detail(job: JobDetail) -> None:
    """Display detailed information about a job."""
    status_icon = _status_icon(job.status)
    click.echo(f"  {status_icon} Job {job.id}")
    if job.title:
        click.echo(f"     📝 Title: {job.title}")
    click.echo(f"     🔖 Status: {job.status or 'unknown'}")
    click.echo(f"     🆔 Recipe ID: {job.recipe_id}")
    if job.started_at:
        click.echo(f"     🕐 Started: {job.started_at}")
    if job.completed_at:
        click.echo(f"     🕑 Completed: {job.completed_at}")
    if job.is_repeat:
        click.echo("     🔄 Rerun: Yes")
    if job.is_test:
        click.echo("     🧪 Test: Yes")
    if job.error:
        click.echo(f"     ⚠️  Error: {job.error}")
    if job.calling_recipe_id:
        msg = f"     📞 Called by Recipe: {job.calling_recipe_id}"
        if job.calling_job_id is not None:
            msg += f" (Job: {job.calling_job_id})"
        click.echo(msg)
    if job.root_recipe_id:
        msg = f"     🌳 Root Recipe: {job.root_recipe_id}"
        if job.root_job_id is not None:
            msg += f" (Job: {job.root_job_id})"
        click.echo(msg)

    if job.lines:
        click.echo()
        click.echo(f"  📊 Execution Steps ({len(job.lines)} steps)")
        for line in job.lines:
            line_num = (
                line.recipe_line_number if line.recipe_line_number is not None else "?"
            )
            adapter = line.adapter_name or "unknown"
            operation = line.adapter_operation or ""
            click.echo(f"     Step {line_num}: {adapter} → {operation}")
            if line.line_stat and line.line_stat.get("total") is not None:
                click.echo(f"       ⏱️  {line.line_stat['total']:.2f}s")


def _status_icon(status: str | None) -> str:
    """Return an icon for the job status."""
    icons = {
        "succeeded": "✅",
        "failed": "❌",
        "pending": "⏳",
    }
    return icons.get(status or "", "❓")
