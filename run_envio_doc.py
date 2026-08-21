import argparse
import json
import shlex
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import text

from app.database import engine

SOURCE_DB = "KardexVH"
SOURCE_SCHEMA = "dbo"
HEADER_TABLE = "Facturas"
DETAIL_TABLE = "facturas_det"
LINK_COLUMN = "codigounico"
ID_COLUMN = "ID"
API_URL = "https://conectorsm.fullapps.us/api/invoices"
NOTE_REASON_FIELDS = {"motivo_nc", "descr_motivo_nc", "motivo_nd", "descr_motivo_nd"}






def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Envia una factura por ID (con detalle) al API de invoices."
    )
    parser.add_argument(
        "--id",
        required=True,
        type=int,
        help="ID de la tabla Facturas a enviar.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No envia al API; solo muestra payload y curl.",
    )
    return parser.parse_args()


def _json_value(value: Any, field_name: str | None = None) -> Any:
    if isinstance(value, str):
        if field_name and field_name.lower() in NOTE_REASON_FIELDS:
            return value.rstrip()
        return value.strip()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _serialize_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value, key) for key, value in row.items()}


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


def _fetch_details_by_codigounico(
    codigo_unico: Any, detail_columns: list[str]
) -> list[dict[str, Any]]:
    if codigo_unico is None:
        return []

    link_col = _resolve_column(LINK_COLUMN, detail_columns)
    select_cols = ", ".join(f"[{col}]" for col in detail_columns)
    order_by = f"[{link_col}]"
    maybe_line_col = next((c for c in detail_columns if c.lower() == "linea"), None)
    if maybe_line_col:
        order_by += f", [{maybe_line_col}]"

    query = text(
        f"""
        SELECT {select_cols}
        FROM [{SOURCE_DB}].[{SOURCE_SCHEMA}].[{DETAIL_TABLE}]
        WHERE [{link_col}] = :codigo
        ORDER BY {order_by}
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"codigo": codigo_unico}).fetchall()
    return [dict(row._mapping) for row in rows]


def _build_payload(invoice_id: int) -> dict[str, Any]:
    header_columns = _get_table_columns(HEADER_TABLE)
    detail_columns = _get_table_columns(DETAIL_TABLE)
    link_col_header = _resolve_column(LINK_COLUMN, header_columns)

    header = _fetch_header_by_id(invoice_id, header_columns)
    details = _fetch_details_by_codigounico(header.get(link_col_header), detail_columns)

    payload = _serialize_dict(header)
    payload["details"] = [_serialize_dict(d) for d in details]
    return payload


def _build_curl_command(token: str, payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    return (
        'curl -X POST "https://conectorsm.fullapps.us/api/invoices" \\\n'
        f'  -H "Authorization: Bearer {token}" \\\n'
        '  -H "Accept: application/json" \\\n'
        '  -H "Content-Type: application/json" \\\n'
        f"  --data-raw {shlex.quote(payload_json)}"
    )


def _write_sent_file(invoice_id: int, curl_command: str) -> Path:
    sent_dir = Path("sent")
    sent_dir.mkdir(parents=True, exist_ok=True)
    output_path = sent_dir / f"sent_{invoice_id}.txt"
    output_path.write_text(curl_command + "\n", encoding="utf-8")
    return output_path


def _write_result_file(invoice_id: int, status_text: str, data: Any) -> Path:
    result_dir = Path("result")
    result_dir.mkdir(parents=True, exist_ok=True)
    output_path = result_dir / f"result_{invoice_id}.txt"

    if isinstance(data, dict):
        body = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    else:
        body = str(data)

    content = f"status: {status_text}\n\n{body}\n"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _get_payload_value(payload: dict[str, Any], field_path: str) -> Any:
    current: Any = payload
    for part in field_path.split("."):
        if isinstance(current, list):
            if not part.isdigit():
                return None
            idx = int(part)
            if idx < 0 or idx >= len(current):
                return None
            current = current[idx]
            continue

        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue

        return None
    return current


def _friendly_validation_errors(data: Any, payload: dict[str, Any]) -> list[str]:
    if not isinstance(data, dict):
        return []

    errors = data.get("errors")
    if not isinstance(errors, dict):
        return []

    friendly: list[str] = []
    for field, messages in errors.items():
        value = _get_payload_value(payload, field)
        value_text = "null" if value is None else str(value)

        field_messages: list[str]
        if isinstance(messages, list):
            field_messages = [str(msg) for msg in messages]
        else:
            field_messages = [str(messages)]

        for msg in field_messages:
            msg_lower = msg.lower()
            if "exist" in msg_lower or "no existe" in msg_lower:
                friendly.append(f'El campo {field} con valor "{value_text}" no existe.')
            else:
                friendly.append(
                    f'Error en campo {field} con valor "{value_text}": {msg}'
                )
    return friendly


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
        print(f"Error preparando envio: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        print(f"\nCurl guardado en: {sent_path}", file=sys.stderr)
        return 0

    try:
        status_code, data = _send_to_api(token, payload)
        friendly_errors = _friendly_validation_errors(data, payload)
        if friendly_errors and isinstance(data, dict):
            data = {**data, "friendly_errors": friendly_errors}
        result_path = _write_result_file(args.id, f"HTTP {status_code}", data)
    except Exception as exc:  # noqa: BLE001
        result_path = _write_result_file(args.id, "ERROR", str(exc))
        print(f"Error enviando al API: {exc}", file=sys.stderr)
        print(f"Resultado guardado en: {result_path}", file=sys.stderr)
        return 1

    print(f"HTTP {status_code}")
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        if isinstance(data.get("friendly_errors"), list):
            print("\nErrores detectados:")
            for err in data["friendly_errors"]:
                print(f"- {err}")
    else:
        print(data)
    print(f"Curl guardado en: {sent_path}", file=sys.stderr)
    print(f"Resultado guardado en: {result_path}", file=sys.stderr)

    return 0 if status_code in (200, 201) else 1


if __name__ == "__main__":
    raise SystemExit(main())
