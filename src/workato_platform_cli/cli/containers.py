import certifi

from dependency_injector import containers, providers

from workato_platform_cli import Workato
from workato_platform_cli.cli.commands.connectors.connector_manager import (
    ConnectorManager,
)
from workato_platform_cli.cli.commands.projects.project_manager import ProjectManager
from workato_platform_cli.cli.commands.recipes.validator import RecipeValidator
from workato_platform_cli.cli.utils.config import ConfigManager
from workato_platform_cli.client.workato_api.configuration import Configuration


def create_workato_config(access_token: str, host: str) -> Configuration:
    """Create Workato API configuration with SSL verification disabled"""
    config_obj = Configuration(
        access_token=access_token,
        host=host,
        ssl_ca_cert=certifi.where(),
    )
    return config_obj


def create_profile_aware_workato_config(
    config_manager: ConfigManager, cli_profile: str | None = None
) -> Configuration:
    """Create Workato API configuration using profile-based resolution"""
    # Get config data for profile resolution
    config_data = config_manager.load_config()

    # Use CLI profile if provided, otherwise fall back to legacy profile
    # or workspace_id-based resolution
    effective_profile_override = cli_profile or config_data.profile

    # Resolve credentials using profile manager (workspace_id for auto-matching)
    api_token, api_host = config_manager.profile_manager.resolve_environment_variables(
        effective_profile_override, workspace_id=config_data.workspace_id
    )

    if not api_token or not api_host:
        raise ValueError(
            "Could not resolve API credentials. Please check your profile "
            "configuration or run 'workato init' to set up authentication."
        )

    return create_workato_config(api_token, api_host)


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    config_manager: providers.Singleton[ConfigManager] = providers.Singleton(
        ConfigManager, skip_validation=True
    )

    workato_api_configuration = providers.Factory(
        create_profile_aware_workato_config,
        config_manager=config_manager,
        cli_profile=config.cli_profile,
    )
    workato_api_client: providers.Singleton[Workato] = providers.Singleton(
        Workato,
        configuration=workato_api_configuration,
    )

    project_manager: providers.Singleton[ProjectManager] = providers.Singleton(
        ProjectManager,
        workato_api_client=workato_api_client,
    )

    recipe_validator: providers.Singleton[RecipeValidator] = providers.Singleton(
        RecipeValidator,
        workato_api_client=workato_api_client,
    )

    connector_manager: providers.Singleton[ConnectorManager] = providers.Singleton(
        ConnectorManager,
        workato_api_client=workato_api_client,
    )
