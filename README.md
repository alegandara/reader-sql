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
