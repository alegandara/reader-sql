# SQL Reader Agent (Python + SQL Server + REST)

Proyecto base en Python para exponer datos de SQL Server por medio de una API REST.

## Requisitos

- Python 3.10+
- Driver ODBC de SQL Server instalado (por ejemplo: `ODBC Driver 18 for SQL Server`)

## Instalacion

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` con tus credenciales reales.

## Ejecutar

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

- `GET /health` valida conexion con SQL Server.
- `GET /tables?schema=dbo` lista tablas del schema.
- `GET /rows/{schema}/{table}?limit=100` devuelve filas (solo lectura).

## Ejemplos

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/tables?schema=dbo"
curl "http://localhost:8000/rows/dbo/Users?limit=10"
```

## Ejecutar consulta Facturas por linea de comando

Este script ejecuta el `SELECT TOP N` sobre `[KardexVH].[dbo].[Facturas]` y muestra el resultado en formato CSV en la terminal.

```bash
python run_facturas_topn.py
```

Opcionalmente puedes cambiar el tope:

```bash
python run_facturas_topn.py --top 200
```

## Uso en Windows (actualizacion constante)

### 1) Primera instalacion en Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup_windows.ps1
```

Si necesitas cambiar carpeta o URL:

```powershell
.\setup_windows.ps1 -RepoUrl "git@github.com:alegandara/reader-sql.git" -TargetDir "reader-sql"
```

### 2) Actualizar proyecto (traer ultimos cambios)

Desde la carpeta del proyecto:

```powershell
.\update_windows.ps1
```

### 3) Ejecutar API REST en Windows

```powershell
.\run_api_windows.ps1
```

### 4) Ejecutar consulta Facturas desde Windows

```powershell
.\.venv\Scripts\python run_facturas_topn.py --top 1000
```

### 5) Auto-actualizacion cada N minutos (opcional)

```powershell
.\auto_update_windows.ps1 -Minutes 15
```

## Enviar factura por API usando numero de registro

Script: `send_invoice_by_registro.py`

Este procedimiento:
- busca la cabecera en `KardexVH.dbo.Facturas`,
- intenta buscar detalles en `KardexVH.dbo.FacturasDetalle`,
- arma el payload para `POST /invoices`,
- y envia la factura al API remoto.
- por defecto busca por `id` (registro fisico de la tabla).

Antes de ejecutar, configura en `.env`:
- `INVOICE_API_BASE_URL`
- `INVOICE_API_TOKEN`
- ids de catalogo (`INVOICE_COMPANY_ID`, `INVOICE_BRANCH_ID`, `INVOICE_SERIE_ID`, `INVOICE_TIPO_DOC_ID`, `INVOICE_MONEDA_ID`)

Ejemplo (preview sin enviar):

```bash
python send_invoice_by_registro.py --registro 123 --dry-run
```

Enviar al API:

```bash
python send_invoice_by_registro.py --registro 123
```

Si tu numero de registro se busca por otro campo:

```bash
python send_invoice_by_registro.py --registro F0010123 --registro-campo folio_char
```
