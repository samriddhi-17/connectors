"""Application-wide configuration, fully driven by environment variables.

Every value is read from the environment (and optionally an env-file, whose
path is controlled by the ``ENV_FILE`` variable). There is deliberately no
hard-coded configuration anywhere else in the project.
"""
import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = os.environ.get("ENV_FILE", ".env")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    app_name: str = "connects-demo"
    environment: str = "dev"
    log_level: str = "INFO"
    version: str = "0.1.0"
    # Comma-separated list of allowed CORS origins ("*" allows all).
    cors_origins: str = "*"
    metrics_prefix: str = "demo"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


class _ConnectorBase(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    enabled: bool = True
    host: str
    port: int
    connect_timeout_s: float = 3.0
    query_timeout_s: float = 5.0


class AerospikeConfig(_ConnectorBase):
    model_config = SettingsConfigDict(env_prefix="AEROSPIKE_", env_file=_ENV_FILE, extra="ignore")

    host: str = "aerospike"
    port: int = 3000
    namespace: str = "test"
    set_name: str = "demo"
    auth_mode: str = "none"  # none | sha256 | pki
    username: str = ""
    password: str = ""


class YugabyteConfig(_ConnectorBase):
    model_config = SettingsConfigDict(env_prefix="YUGABYTE_", env_file=_ENV_FILE, extra="ignore")

    host: str = "yugabyte"
    port: int = 5433
    database: str = "yugabyte"
    user: str = "yugabyte"
    password: str = ""
    sslmode: str = "disable"
    table_name: str = "demo_records"
    pool_min: int = 1
    pool_max: int = 5

    @property
    def conninfo(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} password={self.password} sslmode={self.sslmode} "
            f"connect_timeout={int(self.connect_timeout_s)}"
        )


class OpensreConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENSRE_", env_file=_ENV_FILE, extra="ignore")

    # Where the bridge writes OpenSRE-compatible alert JSON files.
    alerts_dir: str = "./opensre/alerts"
    # Whether the bridge should shell out to `opensre investigate -i <file>`.
    invoke_cli: bool = False
    bin: str = "opensre"
    cli_timeout_s: float = 120.0

    # Mirrors the OpenSRE CLI's own Grafana integration environment variables
    # (see https://www.opensre.com/docs/grafana). Exposed here so the demo
    # can wire OpenSRE back to the demo Grafana for evidence collection.
    grafana_instance_url: str = ""
    grafana_read_token: str = ""
    grafana_verify_ssl: bool = True


class Settings(BaseSettings):
    """Root settings object, composed of namespaced sub-settings.

    Each sub-settings block reads its own ``<PREFIX>_<FIELD>`` variables from
    the environment, e.g. ``AEROSPIKE_HOST``, ``YUGABYTE_PASSWORD``.
    """

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    app: AppConfig = Field(default_factory=AppConfig)
    aerospike: AerospikeConfig = Field(default_factory=AerospikeConfig)
    yugabyte: YugabyteConfig = Field(default_factory=YugabyteConfig)
    opensre: OpensreConfig = Field(default_factory=OpensreConfig)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_settings_for_testing(**overrides) -> Settings:
    """Build a Settings object without touching the repo env-file.

    Used by tests to force connectors into a predictable (unavailable)
    state regardless of what a developer has in their local ``.env``.
    """
    return Settings(_env_file=None, **overrides)