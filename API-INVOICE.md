# API Invoices

API REST para integrar otro frontend con las tablas `invoices` e `invoice_details`.

## Autenticacion por token

Todas las rutas de este documento requieren header `Authorization` con bearer token:

```http
Authorization: Bearer TU_API_TOKEN
Accept: application/json
Content-Type: application/json
```

Configurar token en backend (`.env`):

```env
API_TOKEN=tu_token_secreto_largo
```

## URL de acceso

URL base actual del API (segun configuracion `APP_URL`):

```text
https://conectorsm.fullapps.us/api
```

En local (si corres `php artisan serve`):

```text
http://127.0.0.1:8000/api
```

## Endpoints de invoices

### Listar invoices

- **GET** `/invoices`
- Query params opcionales:
  - `search`: busca por `ruc_emisor`, `razon_social`, `ident_fiscal` o `folio_char`.
  - `per_page`: cantidad por pagina (maximo 100).

Ejemplo:

```bash
curl -X GET "https://conectorsm.fullapps.us/api/invoices?search=F001&per_page=20" \
  -H "Authorization: Bearer TU_API_TOKEN" \
  -H "Accept: application/json"
```

### Ver invoice por ID

- **GET** `/invoices/{id}`

### Crear invoice (con details opcional)

- **POST** `/invoices`

Payload ejemplo:

```json
{
  "company_id": 1,
  "branch_id": 1,
  "ruc_emisor": "20123456789",
  "serie_id": 1,
  "tipo_doc_id": 1,
  "folio": 123,
  "folio_char": "F0010123",
  "fecha_emision": "2026-07-04",
  "moneda_id": 1,
  "razon_social": "CLIENTE DEMO SAC",
  "ident_fiscal": "20600000001",
  "tot_gra": 100.0,
  "igv": 18.0,
  "neto": 118.0,
  "details": [
    {
      "linea": 1,
      "cantidad": 1,
      "cod_prod_id": 10,
      "descripcion": "Servicio de mantenimiento",
      "valor_init": 100.0,
      "gravado": 100.0,
      "igv": 18.0,
      "neto": 118.0
    }
  ]
}
```

> Si se envia `company_id`, el sistema intenta tomar `ruc_emisor` desde la empresa.

### Actualizar invoice

- **PUT/PATCH** `/invoices/{id}`
- Si envias `details`, reemplaza todas las lineas existentes por las nuevas.
- Si no envias `details`, mantiene los detalles actuales.

### Eliminar invoice

- **DELETE** `/invoices/{id}`
- Respuesta: `204 No Content`.
- Elimina en cascada sus `invoice_details`.

## Endpoints de invoice-details

### Listar detalles

- **GET** `/invoice-details`
- Query params opcionales:
  - `invoice_id`: filtra por invoice.
  - `per_page`: cantidad por pagina (maximo 100).

Ejemplo:

```bash
curl -X GET "https://conectorsm.fullapps.us/api/invoice-details?invoice_id=5" \
  -H "Authorization: Bearer TU_API_TOKEN" \
  -H "Accept: application/json"
```

### Ver detalle por ID

- **GET** `/invoice-details/{id}`

### Crear detalle

- **POST** `/invoice-details`

Payload minimo:

```json
{
  "invoice_id": 5,
  "linea": 1,
  "descripcion": "Producto X",
  "cantidad": 2,
  "neto": 50.0
}
```

### Actualizar detalle

- **PUT/PATCH** `/invoice-details/{id}`

### Eliminar detalle

- **DELETE** `/invoice-details/{id}`
- Respuesta: `204 No Content`.

## Respuestas y errores

- Exitos:
  - `200 OK` (consultas/updates)
  - `201 Created` (creacion)
  - `204 No Content` (eliminacion)
- Errores comunes:
  - `401` token invalido o ausente.
  - `422` error de validacion (`errors` por campo).
  - `404` recurso no encontrado.
  - `500` si `API_TOKEN` no esta configurado en el servidor.

## Campos soportados

- `invoices`: soporta todos los campos de cabecera definidos en el modelo `Invoice`.
- `invoice_details`: soporta todos los campos de detalle definidos en el modelo `InvoiceDetail`.

Para referencia funcional, revisar tambien `tablas.md`.
