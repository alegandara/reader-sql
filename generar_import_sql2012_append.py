# -*- coding: utf-8 -*-
from pathlib import Path

# Input files (Windows server paths)
FACTURAS_TXT = Path(r"D:\import\facturas.txt")
DETALLE_TXT = Path(r"D:\import\detalle.txt")

# Output SQL script (append mode: no borra tablas destino)
OUT_SQL = Path(r"D:\import\carga_por_linea_append.sql")

DB_NAME = "KardexVH"

STG_FACT = "stg_facturas_import"
STG_DET = "stg_facturas_det_import"

DST_FACT = "facturas_test"
DST_DET = "facturas_det_test"

# Destination non-identity columns expected
DST_FACT_COLS = 72
DST_DET_COLS = 30


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def read_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            rows.append(line.rstrip("\r\n").split("|"))
    return rows


def create_staging_sql(table_name: str, ncols: int) -> str:
    columns = ",\n    ".join(
        [f"[c{i:03}] VARCHAR(4000) NULL" for i in range(1, ncols + 1)]
    )
    return f"""
IF OBJECT_ID('dbo.{table_name}', 'U') IS NOT NULL DROP TABLE dbo.{table_name};
CREATE TABLE dbo.{table_name} (
    {columns}
);
""".strip()


def insert_one_line_sql(table_name: str, row: list[str], ncols: int) -> str:
    padded = (row + [""] * ncols)[:ncols]
    col_list = ", ".join([f"[c{i:03}]" for i in range(1, ncols + 1)])

    values_sql: list[str] = []
    for value in padded:
        value = value.replace("\r", "")
        if value == "":
            values_sql.append("NULL")
        else:
            values_sql.append(sql_quote(value))

    return (
        f"INSERT INTO dbo.{table_name} ({col_list}) "
        f"VALUES ({', '.join(values_sql)});"
    )


def dynamic_insert_sql(dst_table: str, stg_table: str) -> str:
    # SQL Server 2012 compatible: no TRY_CONVERT
    return f"""
DECLARE @insertCols NVARCHAR(MAX), @selectCols NVARCHAR(MAX), @sql NVARCHAR(MAX);

;WITH c AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY col.column_id) AS rn,
        col.name AS col_name,
        typ.name AS typ_name,
        col.is_nullable,
        col.max_length,
        col.precision,
        col.scale
    FROM sys.columns col
    JOIN sys.types typ ON typ.user_type_id = col.user_type_id
    WHERE col.object_id = OBJECT_ID('dbo.{dst_table}')
      AND col.is_identity = 0
)
SELECT
    @insertCols = STUFF((
        SELECT ',' + QUOTENAME(col_name)
        FROM c
        ORDER BY rn
        FOR XML PATH(''), TYPE
    ).value('.', 'nvarchar(max)'), 1, 1, ''),
    @selectCols = STUFF((
        SELECT
            ',' +
            CASE
                WHEN typ_name IN ('char','varchar','nchar','nvarchar') THEN
                    CASE
                        WHEN is_nullable = 1 THEN
                            'NULLIF(LEFT(' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))),' +
                            CAST(CASE WHEN typ_name IN ('nchar','nvarchar') THEN max_length/2 ELSE max_length END AS varchar(10)) +
                            '), '''')'
                        ELSE
                            'LEFT(ISNULL(' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), ''''),' +
                            CAST(CASE WHEN typ_name IN ('nchar','nvarchar') THEN max_length/2 ELSE max_length END AS varchar(10)) +
                            ')'
                    END

                WHEN typ_name IN ('decimal','numeric') THEN
                    CASE
                        WHEN is_nullable = 1 THEN
                            'CASE WHEN NULLIF(' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), '''') ' +
                            'IS NULL THEN NULL ' +
                            'WHEN PATINDEX(''%[^0-9.-]%'', LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) = 0 ' +
                            'AND LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))) NOT IN (''.'',''-'',''-.'') ' +
                            'AND LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))) NOT LIKE ''%.%.%'' ' +
                            'AND (CHARINDEX(''-'', LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) IN (0,1)) ' +
                            'THEN CONVERT(' + typ_name + '(' + CAST(precision AS varchar(10)) + ',' + CAST(scale AS varchar(10)) + '), ' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) ' +
                            'ELSE NULL END'
                        ELSE
                            'CASE WHEN NULLIF(' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), '''') ' +
                            'IS NULL THEN 0 ' +
                            'WHEN PATINDEX(''%[^0-9.-]%'', LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) = 0 ' +
                            'AND LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))) NOT IN (''.'',''-'',''-.'') ' +
                            'AND LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))) NOT LIKE ''%.%.%'' ' +
                            'AND (CHARINDEX(''-'', LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) IN (0,1)) ' +
                            'THEN CONVERT(' + typ_name + '(' + CAST(precision AS varchar(10)) + ',' + CAST(scale AS varchar(10)) + '), ' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) ' +
                            'ELSE 0 END'
                    END

                WHEN typ_name IN ('int','bigint','smallint','tinyint') THEN
                    CASE
                        WHEN is_nullable = 1 THEN
                            'CASE WHEN NULLIF(' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), '''') ' +
                            'IS NULL THEN NULL ' +
                            'WHEN ISNUMERIC(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) = 1 ' +
                            'THEN CONVERT(' + typ_name + ', CONVERT(decimal(38,10), LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))))) ' +
                            'ELSE NULL END'
                        ELSE
                            'CASE WHEN NULLIF(' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), '''') ' +
                            'IS NULL THEN 0 ' +
                            'WHEN ISNUMERIC(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) = 1 ' +
                            'THEN CONVERT(' + typ_name + ', CONVERT(decimal(38,10), LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))))) ' +
                            'ELSE 0 END'
                    END

                WHEN typ_name IN ('date','datetime','smalldatetime','datetime2') THEN
                    CASE
                        WHEN is_nullable = 1 THEN
                            'CASE WHEN NULLIF(' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), '''') ' +
                            'IS NULL THEN NULL ' +
                            'WHEN ISDATE(REPLACE(REPLACE(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))),''.'',''-''),''/'',''-'')) = 1 ' +
                            'THEN CONVERT(' + typ_name + ', REPLACE(REPLACE(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))),''.'',''-''),''/'',''-''), 120) ' +
                            'ELSE NULL END'
                        ELSE
                            'CASE WHEN NULLIF(' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), '''') ' +
                            'IS NULL THEN ''19000101'' ' +
                            'WHEN ISDATE(REPLACE(REPLACE(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))),''.'',''-''),''/'',''-'')) = 1 ' +
                            'THEN CONVERT(' + typ_name + ', REPLACE(REPLACE(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))),''.'',''-''),''/'',''-''), 120) ' +
                            'ELSE ''19000101'' END'
                    END

                WHEN typ_name = 'bit' THEN
                    CASE
                        WHEN is_nullable = 1 THEN
                            'CASE WHEN NULLIF(' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), '''') ' +
                            'IS NULL THEN NULL ' +
                            'WHEN LOWER(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) IN (''1'',''true'',''t'',''si'',''s'',''yes'',''y'') THEN 1 ' +
                            'WHEN LOWER(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) IN (''0'',''false'',''f'',''no'',''n'') THEN 0 ' +
                            'ELSE NULL END'
                        ELSE
                            'CASE WHEN NULLIF(' +
                            'LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), '''') ' +
                            'IS NULL THEN 0 ' +
                            'WHEN LOWER(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) IN (''1'',''true'',''t'',''si'',''s'',''yes'',''y'') THEN 1 ' +
                            'WHEN LOWER(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', '''')))) IN (''0'',''false'',''f'',''no'',''n'') THEN 0 ' +
                            'ELSE 0 END'
                    END

                ELSE
                    CASE
                        WHEN is_nullable = 1 THEN
                            'NULLIF(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), '''')'
                        ELSE
                            'ISNULL(LTRIM(RTRIM(REPLACE(REPLACE([c' + RIGHT('000'+CAST(rn AS varchar(3)),3) + '],CHAR(13),''''), ''.  .'', ''''))), '''')'
                    END
            END
        FROM c
        ORDER BY rn
        FOR XML PATH(''), TYPE
    ).value('.', 'nvarchar(max)'), 1, 1, '');

SET @sql = N'INSERT INTO dbo.{dst_table} (' + @insertCols + N') SELECT ' + @selectCols + N' FROM dbo.{stg_table};';
EXEC sp_executesql @sql;
""".strip()


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
