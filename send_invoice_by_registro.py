import argparse
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import requests
from sqlalchemy import text

from app.config import settings
from app.database import engine

ALLOWED_REGISTRY_COLUMNS = {"id", "folio", "folio_char", "serie"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Toma una factura por numero de registro y la envia al API "
            "remoto con su detalle."
        )
    )
    parser.add_argument(
        "--registro",
        required=True,
        help="Numero/valor de registro a buscar en la tabla de facturas.",
    )
    parser.add_argument(
        "--registro-campo",
        default="id",
        help="Campo de busqueda en cabecera (id, folio, folio_char, serie).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No envia al API; solo imprime el payload que se mandaria.",
    )
    return parser.parse_args()


def _to_json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _fetch_header(registro: str, registro_campo: str) -> dict[str, Any]:
    if registro_campo not in ALLOWED_REGISTRY_COLUMNS:
        allowed = ", ".join(sorted(ALLOWED_REGISTRY_COLUMNS))
        raise ValueError(f"registro-campo invalido. Permitidos: {allowed}")

    registro_value: Any = registro
    if registro_campo == "id":
        try:
            registro_value = int(registro)
        except ValueError as exc:
            raise ValueError("Cuando usas --registro-campo id, --registro debe ser numerico.") from exc

    sql = text(
        f"""
        SELECT TOP 1 *
        FROM [{settings.invoice_source_db}].[{settings.invoice_source_schema}].[{settings.invoice_source_table}]
        WHERE [{registro_campo}] = :registro
        ORDER BY [id] DESC
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"registro": registro_value}).fetchone()
    if row is None:
        raise LookupError("No se encontro factura para el registro indicado.")
    return dict(row._mapping)


def _fetch_details(registro: str) -> list[dict[str, Any]]:
    sql = text(
        f"""
        SELECT *
        FROM [{settings.invoice_source_db}].[{settings.invoice_source_schema}].[{settings.invoice_detail_table}]
        WHERE [{settings.invoice_detail_join_column}] = :registro
        ORDER BY [linea]
        """
    )
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql, {"registro": registro}).fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception:
        # Si la tabla de detalles no existe o no coincide, enviamos detalle autogenerado.
        return []


def _build_payload(header: dict[str, Any], details: list[dict[str, Any]]) -> dict[str, Any]:
    folio = header.get("folio")
    serie = header.get("serie") or ""
    folio_char = header.get("folio_char") or f"{serie}{folio}"

    payload: dict[str, Any] = {
        "company_id": settings.invoice_company_id,
        "branch_id": settings.invoice_branch_id,
        "ruc_emisor": header.get("ruc_emisor"),
        "serie_id": settings.invoice_serie_id,
        "tipo_doc_id": settings.invoice_tipo_doc_id,
        "folio": int(folio) if folio is not None else None,
        "folio_char": folio_char,
        "fecha_emision": _to_json_value(header.get("fecha_emisi")),
        "moneda_id": settings.invoice_moneda_id,
        "razon_social": header.get("razon_social"),
        "ident_fiscal": header.get("ident_fiscal"),
        "tot_gra": _to_json_value(header.get("tot_gra") or 0),
        "igv": _to_json_value(header.get("igv") or 0),
        "neto": _to_json_value(header.get("neto") or 0),
        "details": [],
    }

    if details:
        payload["details"] = [
            {
                "linea": int(d.get("linea") or idx + 1),
                "cantidad": _to_json_value(d.get("cantidad") or 1),
                "cod_prod_id": _to_json_value(d.get("cod_prod_id")),
                "descripcion": d.get("descripcion") or f"Item factura {folio_char}",
                "valor_init": _to_json_value(d.get("valor_init") or d.get("gravado") or 0),
                "gravado": _to_json_value(d.get("gravado") or 0),
                "igv": _to_json_value(d.get("igv") or 0),
                "neto": _to_json_value(d.get("neto") or 0),
            }
            for idx, d in enumerate(details)
        ]
    else:
        payload["details"] = [
            {
                "linea": 1,
                "cantidad": 1,
                "descripcion": f"Detalle autogenerado para factura {folio_char}",
                "valor_init": _to_json_value(header.get("tot_gra") or 0),
                "gravado": _to_json_value(header.get("tot_gra") or 0),
                "igv": _to_json_value(header.get("igv") or 0),
                "neto": _to_json_value(header.get("neto") or 0),
            }
        ]

    return payload


def _send_invoice(payload: dict[str, Any]) -> tuple[int, dict[str, Any] | str]:
    if not settings.invoice_api_token:
        raise ValueError("Falta INVOICE_API_TOKEN en .env")

    url = f"{settings.invoice_api_base_url.rstrip('/')}/invoices"
    headers = {
        "Authorization": f"Bearer {settings.invoice_api_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    try:
        data = response.json()
    except ValueError:
        data = response.text
    return response.status_code, data


def main() -> int:
    args = parse_args()

    try:
        header = _fetch_header(args.registro, args.registro_campo)
        details = _fetch_details(str(header.get(settings.invoice_detail_join_column, args.registro)))
        payload = _build_payload(header, details)
    except Exception as exc:  # noqa: BLE001
        print(f"Error armando factura: {exc}")
        return 1

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=_to_json_value))
        return 0

    try:
        status_code, data = _send_invoice(payload)
    except Exception as exc:  # noqa: BLE001
        print(f"Error enviando al API: {exc}")
        return 1

    print(f"HTTP {status_code}")
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, ensure_ascii=False, default=_to_json_value))
    else:
        print(data)

    return 0 if status_code in (200, 201) else 1


if __name__ == "__main__":
    raise SystemExit(main())
