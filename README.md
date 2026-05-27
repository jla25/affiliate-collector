# Affiliate Collector

API REST (FastAPI) que descarga y normaliza datos de afiliados desde múltiples plataformas. Centraliza métricas de clicks, registros, depósitos e ingresos en un formato unificado.

## Instalación

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Documentación interactiva disponible en `http://localhost:8000/docs`.

---

## Plataformas soportadas

### MyAffiliates
Plataforma usada por: **Betsson Group**, **Betify**, **Maxibet**

- **Auth**: HTTP Basic (user/pass) o OAuth 2.0 (client_id/client_secret)
- **Formato**: CSV multi-sección (un bloque de cabecera por grupo de clientes)
- **Credenciales**:
  ```json
  { "user": "...", "pass": "..." }
  ```
  o con OAuth:
  ```json
  { "client_id": "...", "client_secret": "..." }
  ```
- **Opción `hybrid_groups`**: lista de IDs de Customer Group a incluir. Cuando se define, solo se procesan las secciones de tipo Hybrid (con columna `Qualified NDCs`). Sin `hybrid_groups`, se recogen todas las secciones.
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
Plataforma usada por: **Betway**, **Betway RS**

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
| nevRevenue | `revenue_total` |
| revShareEarnings | `income_revshare` |
| cpaEarnings | `income_cpa` |
| totalEarnings | `income_total` |

---

### Affilka
Plataforma usada por: **BCGame**

- **Auth**: Bearer token en cabecera
- **Endpoint**: `/api/customer/v1/partner/report` (agrupado por día + campaña)
- **Credenciales**:
  ```json
  { "api_key": "..." }
  ```

| Campo JSON | Campo interno |
|---|---|
| campaign_id | `affiliate_name` (resuelto via `/partner/campaigns`) |
| visits_count | `clicks` |
| registrations_count | `nrc` |
| first_deposits_count | `ftd` / `ndc` |
| qualified_players_count | `qftd` |
| deposits_sum | `total_deposits` |
| first_deposits_sum | `first_deposit` |
| ngr | `revenue_total` |
| partner_income | `income_total` |

---

### Income Access
Plataforma usada por: **YO Group**

- **Auth**: API key en query param (`key=...`)
- **Endpoint**: `/api/affreporting.asp?reportname=EarningsReport&reportdisplayby=site`
- **Formato**: XML SOAP — una fila por afiliado (site) con totales del período
- **Credenciales**:
  ```json
  { "api_key": "..." }
  ```
  Opcionalmente `merchant_id` (por defecto `"0"` = todos):
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

> **Nota**: Income Access no ofrece desglose diario por afiliado. Cada row representa el total del período completo solicitado. La `date` se fija al primer día del rango.

---

### NetRefer (pendiente)
Plataforma usada por: **Hell Partners**

- **Auth**: OAuth 2.0 vía Azure AD (password grant)
- **API**: ASR 1.0 — en *limited launch*, requiere credenciales específicas de onboarding
- **Credenciales necesarias** (solicitadas al operador):
  ```json
  { "client_id": "...", "client_secret": "...", "username": "...", "password": "..." }
  ```

---

## Añadir un operador

```bash
POST /operators/
{
  "name": "Nombre Operador",
  "platform": "incomeaccess",
  "url": "https://partners.operador.com",
  "credentials": { "api_key": "..." }
}
```

## Lanzar colección

```bash
POST /collect/
{ "operators": ["YO Group"], "month": "2026-04" }

# Rango libre
{ "from_to": ["2026-04-01", "2026-04-30"] }

# Últimos N días
{ "last": 30 }

# Todos los operadores activos
{ "month": "2026-04" }
```

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

## Archivos raw

Los datos originales se guardan en `backend/data/raw/` con el nombre `{operador}_{from}_{to}.{ext}` para trazabilidad.
