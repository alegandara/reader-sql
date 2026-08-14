import argparse
import csv
import re
import sys

from sqlalchemy import text

from app.database import engine

SOURCE_DB = "KardexVH"
SOURCE_SCHEMA = "dbo"
SOURCE_TABLE = "Facturas"

DEFAULT_COLUMNS = [
    "ruc_emisor",
    "serie",
    "tip_doc",
    "folio",
    "tipo_op",
    "fecha_emision",
    "moneda",
    "placa",
    "vendedor",
    "dir_agencia",
    "tipo_ident",
    "ident_fiscal",
    "razon_social",
    "dom_fiscal",
    "correo",
    "telefono",
    "ubigeo",
    "tot_gra",
    "tot_exo",
    "tot_ina",
    "tot_desc",
    "igv",
    "tipo_igv",
    "isc",
    "otros",
    "anticipo",
    "total_ventas",
    "total_imp",
    "neto",
    "motivo_nc",
    "descr_motivo_nc",
    "motivo_nd",
    "descr_motivo_nd",
    "baja",
    "fecha_baja",
    "mot_baja",
    "cod_det",
    "por_det",
    "monto_det",
    "medio_pago",
    "tipo_cambio",
    "term_pago",
    "fecha_ven",
    "forma_pag",
    "num_pagos",
    "dias",
    "base_credito",
]

COLUMN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta SELECT TOP N sobre KardexVH.dbo.Facturas y muestra resultados."
    )
    parser.add_argument(
        "--top",
        type=int,
        default=1000,
        help="Cantidad de filas (TOP N). Rango permitido: 1..1000.",
    )
    parser.add_argument(
        "--columns",
        default="",
        help=(
            "Columnas separadas por coma. "
            "Ejemplo: ruc_emisor,serie,folio,neto"
        ),
    )
    parser.add_argument(
        "--last",
        action="store_true",
        help="Trae los ultimos registros (ORDER BY DESC).",
    )
    parser.add_argument(
        "--order-by",
        default="id",
        help="Columna para ordenar cuando usas --last. Default: id.",
    )
    return parser.parse_args()


def _parse_columns(columns_arg: str) -> list[str]:
    if not columns_arg.strip():
        return DEFAULT_COLUMNS

    columns = [c.strip() for c in columns_arg.split(",") if c.strip()]
    if not columns:
        raise ValueError("Debes indicar al menos una columna en --columns.")

    invalid = [c for c in columns if not COLUMN_RE.match(c)]
    if invalid:
        raise ValueError(f"Nombre de columna invalido: {', '.join(invalid)}")

    return columns


def _get_table_columns() -> list[str]:
    query = text(
        f"""
        SELECT COLUMN_NAME
        FROM [{SOURCE_DB}].INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = :schema_name
          AND TABLE_NAME = :table_name
        ORDER BY ORDINAL_POSITION
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {"schema_name": SOURCE_SCHEMA, "table_name": SOURCE_TABLE},
        ).fetchall()
    return [str(row[0]) for row in rows]


def _resolve_columns_case_insensitive(
    requested_columns: list[str],
    table_columns: list[str],
) -> tuple[list[str], list[str]]:
    table_columns_map = {col.lower(): col for col in table_columns}
    resolved: list[str] = []
    missing: list[str] = []

    for col in requested_columns:
        real_col = table_columns_map.get(col.lower())
        if real_col is None:
            missing.append(col)
        else:
            resolved.append(real_col)

    return resolved, missing


def main() -> int:
    args = parse_args()
    if args.top < 1 or args.top > 1000:
        print("Error: --top debe estar entre 1 y 1000.", file=sys.stderr)
        return 1
    try:
        columns = _parse_columns(args.columns)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if not COLUMN_RE.match(args.order_by):
        print("Error: Nombre invalido en --order-by.", file=sys.stderr)
        return 1

    try:
        table_columns = _get_table_columns()
    except Exception as exc:  # noqa: BLE001
        print(f"Error leyendo metadatos de tabla: {exc}", file=sys.stderr)
        return 1

    table_columns_set_lower = {col.lower() for col in table_columns}
    resolved_columns, missing = _resolve_columns_case_insensitive(columns, table_columns)
    if missing:
        print(
            "Error: estas columnas no existen en Facturas: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 1
    if args.last and args.order_by.lower() not in table_columns_set_lower:
        print(
            f"Error: la columna de orden '{args.order_by}' no existe en Facturas.",
            file=sys.stderr,
        )
        return 1

    order_by_resolved = args.order_by
    if args.last:
        order_by_resolved = next(
            col for col in table_columns if col.lower() == args.order_by.lower()
        )

    columns_sql = ", ".join(f"[{col}]" for col in resolved_columns)
    query = f"SELECT TOP (:top_n) {columns_sql} FROM [{SOURCE_DB}].[{SOURCE_SCHEMA}].[{SOURCE_TABLE}]"
    if args.last:
        query += f" ORDER BY [{order_by_resolved}] DESC"

    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), {"top_n": args.top})
            rows = result.fetchall()
    except Exception as exc:  # noqa: BLE001
        print(f"Error ejecutando consulta: {exc}", file=sys.stderr)
        return 1

    writer = csv.writer(sys.stdout)
    writer.writerow(resolved_columns)
    for row in rows:
        writer.writerow([row._mapping.get(col) for col in resolved_columns])

    print(f"\nTotal filas: {len(rows)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
