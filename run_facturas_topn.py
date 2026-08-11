import argparse
import csv
import re
import sys

from sqlalchemy import text

from app.database import engine

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

    columns_sql = ", ".join(f"[{col}]" for col in columns)
    query = f"SELECT TOP (:top_n) {columns_sql} FROM [KardexVH].[dbo].[Facturas]"

    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), {"top_n": args.top})
            rows = result.fetchall()
    except Exception as exc:  # noqa: BLE001
        print(f"Error ejecutando consulta: {exc}", file=sys.stderr)
        return 1

    writer = csv.writer(sys.stdout)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row._mapping.get(col) for col in columns])

    print(f"\nTotal filas: {len(rows)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
