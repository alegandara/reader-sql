import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import bindparam, text

from app.database import engine

SOURCE_DB = "KardexVH"
SOURCE_SCHEMA = "dbo"
SOURCE_TABLE = "Facturas"
DETAIL_TABLE = "facturas_det"
DETAIL_LINK_COLUMN = "codigounico"
HEADER_LINK_COLUMN = "codigounico"

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

DEFAULT_DETAIL_COLUMNS = [
    "linea",
    "cantidad",
    "cod_prod",
    "descripcion",
    "valor_init",
    "gravado",
    "igv",
    "neto",
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
        help="Compatibilidad: ahora --top ya trae ultimos registros.",
    )
    parser.add_argument(
        "--order-by",
        default="id",
        help="Columna para ordenar cuando usas --last. Default: id.",
    )
    parser.add_argument(
        "--detail-columns",
        default="",
        help=(
            "Columnas de facturas_det separadas por coma. "
            "Ejemplo: linea,cantidad,descripcion,neto"
        ),
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


def _parse_detail_columns(detail_columns_arg: str) -> list[str]:
    if not detail_columns_arg.strip():
        return DEFAULT_DETAIL_COLUMNS

    columns = [c.strip() for c in detail_columns_arg.split(",") if c.strip()]
    if not columns:
        raise ValueError("Debes indicar al menos una columna en --detail-columns.")

    invalid = [c for c in columns if not COLUMN_RE.match(c)]
    if invalid:
        raise ValueError(f"Nombre de columna invalido en detalle: {', '.join(invalid)}")

    return columns


def _get_table_columns(table_name: str) -> list[str]:
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
            {"schema_name": SOURCE_SCHEMA, "table_name": table_name},
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


def _json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _fetch_details_by_codigounico(
    codigos: list[str],
    detail_columns: list[str],
    detail_table_columns: list[str],
) -> dict[str, list[dict]]:
    if not codigos:
        return {}

    if DETAIL_LINK_COLUMN.lower() not in {col.lower() for col in detail_table_columns}:
        raise ValueError(
            f"La tabla {DETAIL_TABLE} no tiene columna de enlace '{DETAIL_LINK_COLUMN}'."
        )

    link_col_resolved = next(
        col for col in detail_table_columns if col.lower() == DETAIL_LINK_COLUMN.lower()
    )
    selected_cols = [link_col_resolved] + [
        col for col in detail_columns if col.lower() != link_col_resolved.lower()
    ]

    cols_sql = ", ".join(f"[{col}]" for col in selected_cols)
    order_sql = f"[{link_col_resolved}]"
    if "linea" in {c.lower() for c in detail_table_columns}:
        linea_col = next(col for col in detail_table_columns if col.lower() == "linea")
        order_sql += f", [{linea_col}]"

    query = text(
        f"""
        SELECT {cols_sql}
        FROM [{SOURCE_DB}].[{SOURCE_SCHEMA}].[{DETAIL_TABLE}]
        WHERE [{link_col_resolved}] IN :codigos
        ORDER BY {order_sql}
        """
    ).bindparams(bindparam("codigos", expanding=True))

    details_map: dict[str, list[dict]] = {}
    with engine.connect() as conn:
        rows = conn.execute(query, {"codigos": codigos}).fetchall()

    for row in rows:
        row_map = dict(row._mapping)
        key = str(row_map.get(link_col_resolved, ""))
        detail_data = {col: row_map.get(col) for col in selected_cols if col != link_col_resolved}
        details_map.setdefault(key, []).append(detail_data)

    return details_map


def main() -> int:
    args = parse_args()
    if args.top < 1 or args.top > 1000:
        print("Error: --top debe estar entre 1 y 1000.", file=sys.stderr)
        return 1
    try:
        columns = _parse_columns(args.columns)
        detail_columns = _parse_detail_columns(args.detail_columns)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if not COLUMN_RE.match(args.order_by):
        print("Error: Nombre invalido en --order-by.", file=sys.stderr)
        return 1

    try:
        table_columns = _get_table_columns(SOURCE_TABLE)
        detail_table_columns = _get_table_columns(DETAIL_TABLE)
    except Exception as exc:  # noqa: BLE001
        print(f"Error leyendo metadatos de tabla: {exc}", file=sys.stderr)
        return 1

    table_columns_set_lower = {col.lower() for col in table_columns}
    resolved_columns, missing = _resolve_columns_case_insensitive(columns, table_columns)
    resolved_detail_columns, missing_detail = _resolve_columns_case_insensitive(
        detail_columns, detail_table_columns
    )
    if missing:
        print(
            "Error: estas columnas no existen en Facturas: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 1
    if missing_detail:
        print(
            f"Error: estas columnas no existen en {DETAIL_TABLE}: "
            + ", ".join(missing_detail),
            file=sys.stderr,
        )
        return 1
    if args.order_by.lower() not in table_columns_set_lower:
        print(
            f"Error: la columna de orden '{args.order_by}' no existe en Facturas.",
            file=sys.stderr,
        )
        return 1
    if HEADER_LINK_COLUMN.lower() not in table_columns_set_lower:
        print(
            f"Error: Facturas no tiene columna de enlace '{HEADER_LINK_COLUMN}'.",
            file=sys.stderr,
        )
        return 1

    order_by_resolved = next(
        col for col in table_columns if col.lower() == args.order_by.lower()
    )
    header_link_col_resolved = next(
        col for col in table_columns if col.lower() == HEADER_LINK_COLUMN.lower()
    )
    query_columns = list(resolved_columns)
    if header_link_col_resolved not in query_columns:
        query_columns.append(header_link_col_resolved)

    columns_sql = ", ".join(f"[{col}]" for col in query_columns)
    query = f"SELECT TOP (:top_n) {columns_sql} FROM [{SOURCE_DB}].[{SOURCE_SCHEMA}].[{SOURCE_TABLE}]"
    query += f" ORDER BY [{order_by_resolved}] DESC"

    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), {"top_n": args.top})
            rows = result.fetchall()
    except Exception as exc:  # noqa: BLE001
        print(f"Error ejecutando consulta: {exc}", file=sys.stderr)
        return 1

    codigos = [
        str(row._mapping.get(header_link_col_resolved))
        for row in rows
        if row._mapping.get(header_link_col_resolved) is not None
    ]
    codigos = list(dict.fromkeys(codigos))

    try:
        details_map = _fetch_details_by_codigounico(
            codigos,
            resolved_detail_columns,
            detail_table_columns,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error leyendo detalle de facturas: {exc}", file=sys.stderr)
        return 1

    writer = csv.writer(sys.stdout)
    writer.writerow(resolved_columns + ["details_json"])
    for row in rows:
        row_map = row._mapping
        key = row_map.get(header_link_col_resolved)
        details = details_map.get(str(key), []) if key is not None else []
        details_json = json.dumps(details, ensure_ascii=False, default=_json_default)
        writer.writerow([row_map.get(col) for col in resolved_columns] + [details_json])

    print(f"\nTotal filas: {len(rows)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
