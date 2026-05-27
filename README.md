# Affiliate Collector

API REST construida con **FastAPI** que descarga y normaliza datos de afiliados desde múltiples plataformas. Centraliza métricas de clicks, registros, depósitos e ingresos en un único formato unificado (`DataRow`).

---

## Requisitos

- Python 3.10+
- pip

---

## Instalación y puesta en marcha

### 1. Clonar el repositorio

```bash
git clone https://github.com/jla25/affiliate-collector.git
cd affiliate-collector
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r backend/requirements.txt
```

### 3. Configurar variables de entorno

Copia el archivo de ejemplo y rellena tus credenciales:

```bash
cp .env.example .env
```

Edita `.env` con los valores reales de cada operador. Las credenciales también se pueden gestionar directamente desde la API (`POST /operators/`), en cuyo caso el `.env` es opcional.

### 4. Inicializar la base de datos y el usuario admin

La base de datos SQLite se crea automáticamente al arrancar. Al primer inicio, crea el usuario administrador:

```bash
cd backend
uvicorn main:app --reload
```

Con la API corriendo, llama a:

```bash
POST http://localhost:8000/auth/init
{
  "username": "admin",
  "password": "tu_password_seguro"
}
```

> Este endpoint solo funciona si no existe ningún usuario en la base de datos.

### 5. Autenticación

Obtén un token JWT para el resto de llamadas:

```bash
POST http://localhost:8000/auth/login
{
  "username": "admin",
  "password": "tu_password_seguro"
}
```

Incluye el token en todas las peticiones posteriores:

```
Authorization: Bearer <token>
```

### 6. Documentación interactiva

Con el servidor corriendo, accede a:

```
http://localhost:8000/docs
```

---

## Gestión de operadores

### Añadir un operador

```bash
POST /operators/
{
  "name": "Nombre Operador",
  "platform": "incomeaccess",
  "url": "https://partners.operador.com",
  "credentials": { "api_key": "..." }
}
```

### Listar operadores activos

```bash
GET /operators/
```

### Activar / desactivar un operador

```bash
PATCH /operators/{id}
{ "active": false }
```

---

## Lanzar colección de datos

```bash
POST /collect/

# Mes completo
{ "operators": ["YO Group"], "month": "2026-04" }

# Rango libre
{ "from_to": ["2026-04-01", "2026-04-30"] }

# Últimos N días
{ "last": 30 }

# Todos los operadores activos
{ "month": "2026-04" }
```

La respuesta incluye las filas recogidas (`DataRow`), un resumen por canal/campaña y el número total de filas CPA.

---

## Plataformas soportadas

### MyAffiliates
Usada por: **Betsson Group**, **Betify**, **Maxibet**

- **Auth**: HTTP Basic (`user` / `pass`)
- **Formato**: CSV multi-sección (un bloque de cabecera por grupo de clientes)
- **Credenciales**:
  ```json
  { "user": "...", "pass": "..." }
  ```
- **Opción `hybrid_groups`**: lista de IDs de Customer Group a procesar en modo Hybrid (secciones con columna `Qualified NDCs`). Sin este campo, se recogen **todas** las secciones del CSV.
  ```json
  { "user": "...", "pass": "...", "hybrid_groups": [4, 17] }
  ```

| Campo CSV | Campo interno |
|---|---|
| Campaign | `affiliate_name` |
| NRC / Signups | `nrc` |
| NDC / Deposits | `ndc` |
| FTD / FTD Count | `ftd` |
| Qualified NDCs | `qftd` |
| Income Revshare | `income_revshare` |
| Income CPA | `income_cpa` |
| Income CPL | `income_cpl` |

---

### Superpartners
Usada por: **Betway**, **Betway RS**

- **Auth**: API key + username en query params
- **Endpoint**: `/api/feed/hybrid/traffic` (datos diarios por campaña y brand)
- **Credenciales**:
  ```json
  { "username": "...", "api_key": "..." }
  ```

| Atributo XML | Campo interno |
|---|---|
| brand | `channel` |
| campaign | `affiliate_name` |
| visits | `clicks` |
| newOpens | `nrc` |
| newActivePurchasing | `ftd` / `ndc` |
| qualifieds | `qftd` |
| deposits | `total_deposits` |
| netRevenue | `revenue_total` |
| revShareEarnings | `income_revshare` |
| cpaEarnings | `income_cpa` |
| totalEarnings | `income_total` |

---

### Affilka (by SOFTSWISS)
Usada por: **BCGame**

- **Auth**: Bearer token en cabecera
- **Endpoint**: `/api/customer/v1/partner/report` (agrupado por día + campaña)
- **Credenciales**:
  ```json
  { "api_key": "..." }
  ```

> **Nota**: En Affilka, todo FTD se considera cualificado (cumple el requisito de depósito), por lo que `qftd = ftd`.

| Campo JSON | Campo interno |
|---|---|
| campaign_id | `affiliate_name` (resuelto via `/partner/campaigns`) |
| visits_count | `clicks` |
| registrations_count | `nrc` |
| first_deposits_count | `ftd` / `ndc` / `qftd` |
| deposits_sum | `total_deposits` |
| first_deposits_sum | `first_deposit` |
| ngr | `revenue_total` |
| partner_income | `income_total` |

---

### Income Access
Usada por: **YO Group**

- **Auth**: API key en query param (`key=...`)
- **Endpoint**: `/api/affreporting.asp?reportname=EarningsReport&reportdisplayby=site`
- **Formato**: XML — una fila por afiliado (site) con totales del período completo
- **Credenciales**:
  ```json
  { "api_key": "..." }
  ```
  Opcionalmente `merchant_id` (por defecto `"0"` = todos los merchants):
  ```json
  { "api_key": "...", "merchant_id": "9" }
  ```

| Campo XML | Campo interno |
|---|---|
| sitename | `affiliate_name` |
| clicks | `clicks` |
| downloads | `nrc` |
| cpacommissioncount | `qftd` / `ftd` / `ndc` |
| Deposits | `total_deposits` |
| Netrevenue | `revenue_total` |
| stake | `turnover_total` |
| Commission | `income_revshare` |
| CPACommission | `income_cpa` |
| totalcommission | `income_total` |

> **Nota**: Income Access no ofrece desglose diario por afiliado. Cada fila representa el total del período solicitado. El campo `date` se fija al primer día del rango.

---

### NetRefer *(pendiente)*
Usada por: **Hell Partners**

- **Auth**: OAuth 2.0 vía Azure AD (password grant)
- **API**: ASR 1.0 — en *limited launch*, requiere credenciales de onboarding específicas
- **Credenciales necesarias** (solicitadas al operador):
  ```json
  { "client_id": "...", "client_secret": "...", "username": "...", "password": "..." }
  ```

---

## Campos del DataRow (formato unificado)

| Campo | Tipo | Descripción |
|---|---|---|
| `operator` | str | Nombre del operador |
| `platform` | str | Plataforma origen |
| `date` | str (ISO) | Fecha del registro |
| `channel` | str? | Brand o canal (cuando aplica) |
| `affiliate_name` | str? | Nombre de la campaña o afiliado |
| `customer_group` | str? | Grupo de clientes (MyAffiliates) |
| `pay_period` | str? | Período de pago (YYYY-MM-DD) |
| `clicks` | int | Clicks / visitas |
| `nrc` | int | Nuevos registros |
| `ndc` | int | Nuevos depositantes |
| `ftd` | int | First time depositors |
| `qftd` | int | Qualified FTDs (elegibles CPA) |
| `first_deposit` | float | Importe primer depósito |
| `total_deposits` | float | Importe total depósitos |
| `turnover_total` | float | Volumen de apuestas |
| `revenue_total` | float | NGR / Net Revenue |
| `income_revshare` | float? | Comisión RevShare |
| `income_cpa` | float? | Comisión CPA |
| `income_cpl` | float? | Comisión CPL |
| `income_total` | float? | Comisión total |

---

## Archivos raw

Los datos originales se guardan en `backend/data/raw/` con el nombre `{operador}_{from}_{to}.{ext}` para trazabilidad. Esta carpeta está excluida del repositorio (`.gitignore`).
