from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import re

from app.config import settings


def _connection_url() -> str:
    driver = quote_plus(settings.db_driver)
    password = quote_plus(settings.db_password)
    trust_cert = "yes" if settings.db_trust_server_certificate else "no"
    return (
        f"mssql+pyodbc://{settings.db_user}:{password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
        f"?driver={driver}&TrustServerCertificate={trust_cert}"
    )


engine: Engine = create_engine(
    _connection_url(),
    pool_pre_ping=True,
    future=True,
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(identifier: str, label: str) -> str:
    if not _IDENTIFIER_RE.match(identifier):
        raise ValueError(f"invalid {label} value")
    return identifier


def check_connection() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


def list_user_tables(schema: str = "dbo") -> list[str]:
    schema = _validate_identifier(schema, "schema")
    query = text(
        """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
          AND TABLE_SCHEMA = :schema_name
        ORDER BY TABLE_NAME
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"schema_name": schema}).fetchall()
    return [row[0] for row in rows]


def read_table_rows(schema: str, table: str, limit: int = 100) -> list[dict]:
    schema = _validate_identifier(schema, "schema")
    table = _validate_identifier(table, "table")

    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")

    query = text(f"SELECT TOP ({limit}) * FROM [{schema}].[{table}]")
    with engine.connect() as conn:
        result = conn.execute(query)
        return [dict(row._mapping) for row in result]
