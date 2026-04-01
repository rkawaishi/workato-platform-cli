"""Subprocess wrapper for workato-connector-sdk Ruby gem commands."""

import shutil
import subprocess  # noqa: S404

import asyncclick as click


class SdkRunner:
    """Runs workato-connector-sdk (Ruby gem) commands via subprocess."""

    GEM_NAME = "workato-connector-sdk"

    def _get_gem_executable(self) -> str:
        """Find the 'gem' executable."""
        gem_path = shutil.which("gem")
        if gem_path is None:
            raise click.ClickException(
                "Ruby 'gem' command not found. Please install Ruby first.\n"
                "  macOS: brew install ruby\n"
                "  Ubuntu: sudo apt install ruby"
            )
        return gem_path

    def _build_command(self, *args: str) -> list[str]:
        """Build command list: ['gem', 'exec', 'workato', ...args]"""
        gem = self._get_gem_executable()
        return [gem, "exec", "workato", *args]

    def check_ruby_installed(self) -> bool:
        """Check if Ruby is available."""
        return shutil.which("ruby") is not None

    def check_gem_installed(self) -> bool:
        """Check if workato-connector-sdk gem is installed."""
        gem = shutil.which("gem")
        if gem is None:
            return False
        try:
            result = subprocess.run(  # noqa: S603
                [gem, "list", "--installed", "--exact", self.GEM_NAME],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def install_gem(self) -> subprocess.CompletedProcess[str]:
        """Install workato-connector-sdk gem."""
        gem = self._get_gem_executable()
        return subprocess.run(  # noqa: S603
            [gem, "install", self.GEM_NAME],
            capture_output=True,
            text=True,
            timeout=300,
        )

    def run_interactive(self, *args: str, timeout: int = 600) -> int:
        """Run SDK command with stdin/stdout passthrough.

        Returns the exit code.
        """
        cmd = self._build_command(*args)
        result = subprocess.run(cmd, timeout=timeout)  # noqa: S603
        return result.returncode

    def run_captured(
        self, *args: str, timeout: int = 300
    ) -> subprocess.CompletedProcess[str]:
        """Run SDK command capturing output.

        Returns CompletedProcess.
        """
        cmd = self._build_command(*args)
        return subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
