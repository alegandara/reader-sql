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

    invoice_api_base_url: str = "https://conectorsm.fullapps.us/api"
    invoice_api_token: str = ""
    invoice_source_db: str = "KardexVH"
    invoice_source_schema: str = "dbo"
    app_mode: str = "prod"
    facturas_table_prod: str = "Facturas"
    facturas_det_table_prod: str = "facturas_det"
    facturas_table_test: str = "facturas_test"
    facturas_det_table_test: str = "facturas_det_test"
    invoice_source_table: str = "Facturas"
    invoice_detail_table: str = "facturas_det"
    invoice_detail_join_column: str = "folio"
    invoice_company_id: int = 1
    invoice_branch_id: int = 1
    invoice_serie_id: int = 1
    invoice_tipo_doc_id: int = 1
    invoice_moneda_id: int = 1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
