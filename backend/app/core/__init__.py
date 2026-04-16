"""Core configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./absnexus.db"
    upload_directory: str = "./uploads"
    export_directory: str = "./exports"
    dag_archive_directory: str = "./dag_archive"
    oracle_dsn: str = ""
    oracle_user: str = ""
    oracle_password: str = ""
    testing: bool = False

    model_config = {"env_prefix": "ABSNEXUS_", "env_file": ".env"}


settings = Settings()
