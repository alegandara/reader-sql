from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SQL Reader API"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "dev"

    db_host: str = "localhost"
    db_port: int = 1433
    db_name: str = "master"
    db_user: str = "sa"
    db_password: str = ""
    db_driver: str = "ODBC Driver 18 for SQL Server"
    db_trust_server_certificate: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
