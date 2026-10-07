import argparse
import json
import shlex
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.table_mode import facturas_tables, normalized_app_mode

SOURCE_DB = settings.invoice_source_db
SOURCE_SCHEMA = settings.invoice_source_schema
APP_MODE = normalized_app_mode()
HEADER_TABLE, _DETAIL_TABLE = facturas_tables()

ID_COLUMN = "ID"
API_URL = "https://conectorsm.fullapps.us/api/invoices/baja"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Envia una baja de factura por ID al API de invoices."
    )
    parser.add_argument(
        "--id",
        required=True,
        type=int,
        help="ID de la tabla Facturas a enviar en baja.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No envia al API; solo muestra payload y curl.",
    )
    return parser.parse_args()


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _read_api_token_from_env_file() -> str:
    env_path = Path(".env")
    if not env_path.exists():
        raise ValueError("No existe archivo .env en el directorio del proyecto.")

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "API_TOKEN":
            token = value.strip().strip("'").strip('"')
            if token:
                return token
            break

    raise ValueError("No se encontro API_TOKEN en el archivo .env.")


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
            query, {"schema_name": SOURCE_SCHEMA, "table_name": table_name}
        ).fetchall()
    return [str(row[0]) for row in rows]


def _resolve_column(required_name: str, columns: list[str]) -> str:
    for col in columns:
        if col.lower() == required_name.lower():
            return col
    raise ValueError(f"No existe la columna '{required_name}' en la tabla.")


def _resolve_optional_column(name: str, columns: list[str]) -> str | None:
    for col in columns:
        if col.lower() == name.lower():
            return col
    return None


def _fetch_header_by_id(invoice_id: int, header_columns: list[str]) -> dict[str, Any]:
    id_col = _resolve_column(ID_COLUMN, header_columns)
    select_cols = ", ".join(f"[{col}]" for col in header_columns)
    query = text(
        f"""
        SELECT TOP 1 {select_cols}
        FROM [{SOURCE_DB}].[{SOURCE_SCHEMA}].[{HEADER_TABLE}]
        WHERE [{id_col}] = :invoice_id
        """
    )
    with engine.connect() as conn:
        row = conn.execute(query, {"invoice_id": invoice_id}).fetchone()
    if row is None:
        raise LookupError(f"No existe factura con ID={invoice_id}.")
    return dict(row._mapping)


def _required_text(value: Any, field_name: str) -> str:
    txt = "" if value is None else str(_json_value(value))
    txt = txt.strip()
    if not txt:
        raise ValueError(f"El campo {field_name} esta vacio y es requerido para la baja.")
    return txt


def _build_payload(invoice_id: int) -> dict[str, Any]:
    header_columns = _get_table_columns(HEADER_TABLE)
    header = _fetch_header_by_id(invoice_id, header_columns)

    cod_col = _resolve_column("codigounico", header_columns)
    tip_col = _resolve_column("tip_doc", header_columns)
    ruc_col = _resolve_column("ruc_emisor", header_columns)
    serie_col = _resolve_column("serie", header_columns)
    folio_col = _resolve_column("folio", header_columns)

    fecha_baja_col = _resolve_optional_column("fecha_baja", header_columns)
    mot_baja_col = _resolve_optional_column("mot_baja", header_columns)

    codigounico = _required_text(header.get(cod_col), "codigounico")
    tipo_doc = _required_text(header.get(tip_col), "tip_doc")
    ruc_emisor = _required_text(header.get(ruc_col), "ruc_emisor")
    serie = _required_text(header.get(serie_col), "serie")
    folio = _required_text(header.get(folio_col), "folio")

    fecha_baja_raw = header.get(fecha_baja_col) if fecha_baja_col else None
    fecha_baja = _json_value(fecha_baja_raw)
    if isinstance(fecha_baja, str):
        fecha_baja = fecha_baja.strip()
    if not fecha_baja:
        fecha_baja = date.today().isoformat()

    mot_baja_raw = header.get(mot_baja_col) if mot_baja_col else None
    mot_baja = _json_value(mot_baja_raw)
    if mot_baja is None:
        mot_baja = ""
    else:
        mot_baja = str(mot_baja).strip()

    return {
        "codigounico": codigounico,
        "id_sql": invoice_id,
        "tipo_doc": tipo_doc,
        "serie_sunat": f"{ruc_emisor}-{tipo_doc}-{serie}-{folio}",
        "baja": True,
        "fecha_baja": str(fecha_baja),
        "mot_baja": mot_baja,
    }


def _build_curl_command(token: str, payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    return (
        'curl -X POST "https://conectorsm.fullapps.us/api/invoices/baja" \\\n'
        f'  -H "Authorization: Bearer {token}" \\\n'
        '  -H "Accept: application/json" \\\n'
        '  -H "Content-Type: application/json" \\\n'
        f"  --data-raw {shlex.quote(payload_json)}"
    )


def _write_sent_file(invoice_id: int, curl_command: str) -> Path:
    sent_dir = Path("sent")
    sent_dir.mkdir(parents=True, exist_ok=True)
    output_path = sent_dir / f"sent_baja_{invoice_id}.txt"
    output_path.write_text(curl_command + "\n", encoding="utf-8")
    return output_path


def _write_result_file(invoice_id: int, status_text: str, data: Any) -> Path:
    result_dir = Path("result")
    result_dir.mkdir(parents=True, exist_ok=True)
    output_path = result_dir / f"result_baja_{invoice_id}.txt"

    if isinstance(data, dict):
        body = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    else:
        body = str(data)

    content = f"status: {status_text}\n\n{body}\n"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _send_to_api(token: str, payload: dict[str, Any]) -> tuple[int, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    try:
        data = response.json()
    except ValueError:
        data = response.text
    return response.status_code, data


def main() -> int:
    args = parse_args()

    try:
        token = _read_api_token_from_env_file()
        payload = _build_payload(args.id)
        curl_command = _build_curl_command(token, payload)
        sent_path = _write_sent_file(args.id, curl_command)
    except Exception as exc:  # noqa: BLE001
        print(f"Error preparando envio de baja: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        print(f"Modo: {APP_MODE} | Tabla: {HEADER_TABLE}", file=sys.stderr)
        print(f"\nCurl guardado en: {sent_path}", file=sys.stderr)
        return 0

    try:
        status_code, data = _send_to_api(token, payload)
        result_path = _write_result_file(args.id, f"HTTP {status_code}", data)
    except Exception as exc:  # noqa: BLE001
        result_path = _write_result_file(args.id, "ERROR", str(exc))
        print(f"Error enviando baja al API: {exc}", file=sys.stderr)
        print(f"Resultado guardado en: {result_path}", file=sys.stderr)
        return 1

    print(f"HTTP {status_code}")
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        print(data)
    print(f"Modo: {APP_MODE} | Tabla: {HEADER_TABLE}", file=sys.stderr)
    print(f"Curl guardado en: {sent_path}", file=sys.stderr)
    print(f"Resultado guardado en: {result_path}", file=sys.stderr)
    return 0 if status_code in (200, 201) else 1


if __name__ == "__main__":
    raise SystemExit(main())
