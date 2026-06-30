import argparse
import csv
import sys

from sqlalchemy import text

from app.database import engine


QUERY = """
/****** Script para el comando SelectTopNRows de SSMS  ******/
SELECT TOP (:top_n) [ruc_emisor]
      ,[serie]
      ,[tip_doc]
      ,[folio]
      ,[tipo_op]
      ,[fecha_emisi]
      ,[moneda]
      ,[placa]
      ,[vendedor]
      ,[dir_agencia]
      ,[tipo_ident]
      ,[ident_fiscal]
      ,[razon_social]
      ,[dom_fiscal]
      ,[correo]
      ,[telefono]
      ,[ubigeo]
      ,[tot_gra]
      ,[tot_exo]
      ,[tot_ina]
      ,[tot_desc]
      ,[igv]
      ,[tipo_igv]
      ,[isc]
      ,[otros]
      ,[anticipo]
      ,[total_ventas]
      ,[total_imp]
      ,[neto]
      ,[motivo_nc]
      ,[descr_motivo_nc]
      ,[motivo_nd]
      ,[descr_motivo_nd]
      ,[baja]
      ,[fecha_baja]
      ,[mot_baja]
      ,[cod_det]
      ,[por_det]
      ,[monto_det]
      ,[medio_pago]
      ,[tipo_cambio]
      ,[term_pago]
      ,[fecha_ven]
      ,[forma_pag]
      ,[num_pagos]
      ,[dias]
      ,[base_credito]
  FROM [KardexVH].[dbo].[Facturas]
"""


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.top < 1 or args.top > 1000:
        print("Error: --top debe estar entre 1 y 1000.", file=sys.stderr)
        return 1

    try:
        with engine.connect() as conn:
            result = conn.execute(text(QUERY), {"top_n": args.top})
            columns = list(result.keys())
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
