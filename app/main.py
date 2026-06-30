from fastapi import FastAPI, HTTPException, Query

from app.config import settings
from app.database import check_connection, list_user_tables, read_table_rows
from app.schemas import HealthResponse, RowsResponse, TablesResponse

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="REST API para lectura de SQL Server.",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        check_connection()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc

    return HealthResponse(status="ok", database="connected")


@app.get("/tables", response_model=TablesResponse)
def get_tables(schema: str = Query(default="dbo")) -> TablesResponse:
    try:
        tables = list_user_tables(schema=schema)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"error listing tables: {exc}") from exc

    return TablesResponse(schema=schema, tables=tables)


@app.get("/rows/{schema}/{table}", response_model=RowsResponse)
def get_rows(
    schema: str,
    table: str,
    limit: int = Query(default=100, ge=1, le=1000),
) -> RowsResponse:
    try:
        rows = read_table_rows(schema=schema, table=table, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"error reading rows: {exc}") from exc

    return RowsResponse(schema=schema, table=table, count=len(rows), rows=rows)
