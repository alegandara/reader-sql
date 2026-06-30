from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database: str


class TablesResponse(BaseModel):
    schema: str
    tables: list[str]


class RowsResponse(BaseModel):
    schema: str
    table: str
    count: int
    rows: list[dict] = Field(default_factory=list)
