# -*- coding: utf-8 -*-
from pathlib import Path

from generar_import_sql2012 import (
    DB_NAME,
    DETALLE_TXT,
    DST_DET,
    DST_DET_COLS,
    DST_FACT,
    DST_FACT_COLS,
    FACTURAS_TXT,
    STG_DET,
    STG_FACT,
    create_staging_sql,
    dynamic_insert_sql,
    insert_one_line_sql,
    read_rows,
)

# Output SQL script (append mode: no borra tablas destino)
OUT_SQL = Path(r"D:\import\carga_por_linea_append.sql")


def main() -> None:
    fact_rows = read_rows(FACTURAS_TXT)
    det_rows = read_rows(DETALLE_TXT)

    file_fact_cols = max((len(r) for r in fact_rows), default=0)
    file_det_cols = max((len(r) for r in det_rows), default=0)

    fact_cols = max(file_fact_cols, DST_FACT_COLS)
    det_cols = max(file_det_cols, DST_DET_COLS)

    sql_parts: list[str] = []
    sql_parts.append(f"USE [{DB_NAME}];\nGO\nSET NOCOUNT ON;\nGO\n")
    sql_parts.append(create_staging_sql(STG_FACT, fact_cols) + "\nGO\n")
    sql_parts.append(create_staging_sql(STG_DET, det_cols) + "\nGO\n")

    for row in fact_rows:
        sql_parts.append(insert_one_line_sql(STG_FACT, row, fact_cols))
    sql_parts.append("\nGO\n")

    for row in det_rows:
        sql_parts.append(insert_one_line_sql(STG_DET, row, det_cols))
    sql_parts.append("\nGO\n")

    sql_parts.append(dynamic_insert_sql(DST_FACT, STG_FACT) + "\nGO\n")
    sql_parts.append(dynamic_insert_sql(DST_DET, STG_DET) + "\nGO\n")

    sql_parts.append(
        f"""
SELECT
 (SELECT COUNT(*) FROM dbo.{STG_FACT}) AS stg_facturas_rows,
 (SELECT COUNT(*) FROM dbo.{DST_FACT}) AS facturas_test_rows,
 (SELECT COUNT(*) FROM dbo.{STG_DET}) AS stg_det_rows,
 (SELECT COUNT(*) FROM dbo.{DST_DET}) AS facturas_det_test_rows;
GO
""".strip()
    )

    OUT_SQL.write_text("\n".join(sql_parts), encoding="utf-8")
    print("OK generado:", OUT_SQL)
    print("Modo append: NO se borran tablas destino.")
    print("facturas cols archivo:", file_fact_cols, "=> staging:", fact_cols)
    print("detalle  cols archivo:", file_det_cols, "=> staging:", det_cols)


if __name__ == "__main__":
    main()
