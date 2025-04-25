from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource, PydanticBaseSettingsSource

CONFIG_YAML_PATH = Path(__file__).parent.parent / "settings.yaml"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(yaml_file=CONFIG_YAML_PATH, case_sensitive=False, extra="ignore")

    """Holds required environment settings for the tests."""
    rpc_url: str = Field(default=...)
    websocket_url: str = Field(default=...)
    private_key: str = Field(default=...)
    user_address: str = Field(default=...)
    quicknode_hash: str | None = Field(default=None)

    def full_rpc_url(self):
        """Returns the full RPC URL with the private key."""
        if self.rpc_url.find("quiknode.pro") != -1 and self.quicknode_hash:
            return f"{self.rpc_url}/{self.quicknode_hash}/"

        return self.rpc_url

    # --- Custom Source Loading Order ---
    @classmethod
    def settings_customise_sources(
        cls, settings_cls: type[BaseSettings], init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource, dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, YamlConfigSettingsSource(settings_cls), env_settings

