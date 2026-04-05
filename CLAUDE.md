# Toko Web Jaya — Developer Guide

## Stack
- **Backend**: FastAPI (Python 3.13) + SQLAlchemy + PostgreSQL
- **Frontend**: Jinja2 templates + Tailwind CSS + Alpine.js + HTMX
- **Background jobs**: Celery + Redis
- **Payments**: Duitku Pop API (primary), Mayar.id (secondary)
- **Email**: SMTP via Sumopod (port 465 SSL)
- **PDF**: WeasyPrint
- **Auth**: Google OAuth 2.0 + Email/Password (bcrypt + OTP)
- **Infra**: Docker Compose

---

## Running Locally

```bash
# Start all containers
docker compose up -d

# Rebuild after code changes
docker compose up -d --build web

# View logs
docker logs twj_web -f

# Run DB migration SQL
docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_xxx.sql
```

App runs on **port 7777** (not 8000).  
Database accessible at `localhost:5433` (DBeaver etc).

---

## Project Structure

```
app/
├── main.py              # FastAPI app, middleware, error handlers, sitemap
├── core/
│   ├── config.py        # Pydantic settings (reads .env)
│   ├── auth.py          # get_current_user, require_login, require_admin
│   ├── security.py      # Session tokens (itsdangerous), bcrypt password hash
│   ├── database.py      # SQLAlchemy engine + get_db() dependency
│   ├── middleware.py    # SecurityHeadersMiddleware, RateLimitMiddleware (Redis)
│   ├── i18n.py          # t(locale, key) translation function
│   └── currency.py      # IDR/USD conversion, VAT, price formatting
├── models/              # SQLAlchemy ORM models
├── routers/             # FastAPI route handlers
├── services/            # Business logic (email, OTP, payment, invoice, notification)
├── schemas/             # Pydantic request/response schemas
└── tasks/               # Celery async tasks (billing, invoice)

static/
├── css/
│   ├── input.css        # Tailwind source — edit this
│   └── main.css         # Compiled output — do not edit directly
├── js/
│   ├── main.js          # Scroll reveal, tilt, counter, toast, video lazy-load
│   └── hero-particles.js # Canvas particle animation (hero section only)
└── uploads/             # User-uploaded product images/videos/files

scripts/
├── migrate_*.sql        # Manual DB migration scripts
└── seed_*.sql           # Seed data scripts
```

---

## Environment Variables (.env)

| Key | Description |
|-----|-------------|
| `APP_ENV` | `development` or `production` |
| `SECRET_KEY` | Session signing key — change in production |
| `BASE_URL` | Public URL (used in emails, sitemap, OAuth callback) |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection (used for rate limiting, OTP, Celery) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth credentials |
| `GOOGLE_REDIRECT_URI` | Must match Google Console exactly |
| `SMTP_HOST/PORT/USER/PASSWORD` | Sumopod SMTP (port 465 = SSL) |
| `SMTP_FROM` | Sender address — must be verified domain |
| `EMAIL_FROM` | Display name + address: `Name <addr>` |
| `DUITKU_MERCHANT_CODE` / `DUITKU_API_KEY` | Duitku credentials |
| `DUITKU_CALLBACK_URL` | Public URL for Duitku webhook |
| `DUITKU_BASE_URL` | Sandbox: `https://api-sandbox.duitku.com` |

---

## Authentication

Two methods are supported:

### Google OAuth
- Flow: `/auth/google/login` → Google → `/auth/google/callback`
- Creates or updates User on first login
- Sets HTTP-only `session` cookie (7 days)

### Email + Password
- Register: `POST /auth/register` → sends 6-digit OTP to email
- Verify: `POST /auth/verify-email` → marks `email_verified=True`, logs in
- Login: `POST /auth/login-email`
- Forgot: `POST /auth/forgot-password` → sends OTP
- Reset: `POST /auth/reset-password` → verifies OTP, sets new password

OTP details:
- 6-digit numeric, stored in Redis
- TTL: 10 minutes
- Max 5 attempts before lockout
- Namespaces: `verify_email`, `reset_password`

Password hashing: SHA-256 → base64 → bcrypt (avoids 72-byte bcrypt limit).

### Session verification
```python
from app.core.auth import get_current_user, require_login, require_admin

# Optional auth (returns None if not logged in)
user = get_current_user(request, db)

# Required auth (redirects to login if not authenticated)
user = require_login(request, db)

# Admin only (raises 403 if not admin)
user = require_admin(request, db)
```

---

## Localization

All public routes use `/{locale}/` prefix (`id` or `en`).

```python
# In templates
{{ t(locale, 'nav_home') }}

# Add new key in app/core/i18n.py
TRANSLATIONS = {
    "id": { "my_key": "Teks Indonesia" },
    "en": { "my_key": "English text" },
}
```

---

## Payment Flow

```
User clicks "Pay Now"
  → POST /checkout/{id}/create-payment  (AJAX)
    → creates Order (status=pending)
    → calls Duitku API → returns payment_url + reference
  → Duitku Pop.js opens payment modal
  → User completes payment
  → Duitku calls POST /checkout/callback/duitku  (webhook)
    → verifies signature
    → sets order.status = paid
    → triggers: invoice generation, notification, email
  → User redirected to /checkout/return/{order_id}
```

### Adding a new payment gateway
1. Add client class in `app/services/payment.py`
2. Add enum value in `app/models/order.py` `PaymentGateway`
3. Add callback route in `app/routers/checkout.py`
4. Add env vars to `.env` and `app/core/config.py`

---

## Product Pricing Models

| `pricing_model` | Fields used | Checkout type |
|-----------------|-------------|---------------|
| `one_time` | `price_otf` | `?type=one_time` |
| `subscription` | `price_monthly`, `price_yearly` | `?type=subscription&cycle=monthly` |
| `both` | All three | User toggles in UI |

---

## Background Jobs (Celery)

```bash
# Start worker (inside container)
celery -A app.tasks.celery_app:celery worker --loglevel=info

# Start beat scheduler
celery -A app.tasks.celery_app:celery beat --loglevel=info
```

Scheduled tasks (defined in `app/tasks/celery_app.py`):
- `process_due_subscriptions` — daily 08:00 UTC (charge renewals)
- `retry_past_due` — Mon/Thu 10:00 UTC (retry failed payments)
- `mark_overdue_invoices` — daily 01:00 UTC

---

## Rate Limiting

Redis sliding-window, per IP per endpoint category:

| Path prefix | Limit |
|-------------|-------|
| `/auth/` | 20 req / 60s |
| `/checkout/` | 30 req / 60s |
| `/api/` | 60 req / 60s |
| Everything else | 200 req / 60s |

Falls back to **allow** if Redis is unavailable.

---

## Security Headers (production only: HSTS)

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Strict-Transport-Security` — production only

---

## API v1 (B2B)

Base path: `/api/v1/`  
Auth: `Authorization: Bearer <api_key>`

| Method | Path | Scope | Description |
|--------|------|-------|-------------|
| GET | `/api/v1/products` | read | List active products |
| GET | `/api/v1/products/{id}` | read | Product detail |
| GET | `/api/v1/orders` | read | Your orders |
| POST | `/api/v1/orders` | write | Create order |
| GET | `/api/v1/subscriptions` | read | Your subscriptions |
| POST | `/api/v1/keys` | — | Create API key (session auth) |
| DELETE | `/api/v1/keys/{id}` | — | Revoke API key |

---

## CSS / Frontend

Tailwind source: `static/css/input.css`

To recompile CSS (run locally, not in Docker):
```bash
npx tailwindcss -i static/css/input.css -o static/css/main.css --watch
```

Key custom classes:
- `.btn-primary` — neon yellow button
- `.btn-secondary` — bordered white button
- `.card` — dark bordered card
- `.heading-xl/lg/md/sm` — responsive headings
- `.badge`, `.badge-neon`, `.badge-gray` — status badges
- `.container-main` — max-width container with padding
- `.reveal` — scroll-triggered fade-in animation

Design tokens:
- Primary color: `#CAFF00` (neon yellow) → Tailwind: `bg-neon`, `text-neon`
- Background: `#0A0A0A` (black)
- Font: Lexend (Google Fonts)

---

## Adding a New Page

1. Create template in `app/templates/<section>/page.html`
2. Add GET route in the appropriate router
3. Pass `locale`, `current_user`, `active_page` to template context
4. Add SEO blocks if public page:
```html
{% block og_title %}Page Title — Toko Web Jaya{% endblock %}
{% block og_description %}Page description{% endblock %}
```

---

## Notifications

Two channels run in parallel for every event:

```python
# 1. In-app (stored in DB, shown in bell icon)
from app.services.notification import notify_order_paid
notify_order_paid(db, order)

# 2. Email
from app.services.email import send_order_confirmation
send_order_confirmation(order, locale="id")
```

Available notify functions: `notify_order_paid`, `notify_order_failed`,
`notify_invoice_created`, `notify_subscription_new`,
`notify_subscription_renewal`, `notify_subscription_expiring`,
`notify_subscription_cancelled`.

---

## Email Domain Setup (Sumopod)

**Status: ACTIVE** — domain `dev-tokowebjaya.roc.web.id` sudah fully configured.

### Current `.env` (already set)
```
SMTP_HOST=smtp.sumopod.com
SMTP_PORT=465
SMTP_USER=cmnl0wdvz4w5hpb08tbe45t7b        # credentials untuk custom domain
SMTP_PASSWORD=zlvx36ZxvoKFSXavYqDlXlbH8u9AStHz
SMTP_FROM=no-reply@dev-tokowebjaya.roc.web.id
EMAIL_FROM=Toko Web Jaya <no-reply@dev-tokowebjaya.roc.web.id>
```

### DNS Records yang sudah dikonfigurasi
| Type | Name | Value | Status |
|------|------|-------|--------|
| TXT (DKIM) | `*._domainkey.dev-tokowebjaya.roc.web.id` | _(dari Sumopod)_ | ✅ Verified |
| TXT (SPF) | `dev-tokowebjaya.roc.web.id` | `v=spf1 mx include:spf.kirim.email ~all` | ✅ Verified |
| MX | `dev-tokowebjaya.roc.web.id` | `mx.kirimemail.com` (priority 10) | ✅ Verified |
| TXT (verify) | `dev-tokowebjaya.roc.web.id` | `sumo-verification=4bbf317a-aa72-4d4a-a4f7-c1ac3a4f1297` | ✅ Verified |
| TXT (DMARC) | `_dmarc.dev-tokowebjaya.roc.web.id` | `v=DMARC1; p=none; adkim=r; aspf=r` | ✅ Added |

### Catatan
- Sumopod berbasis **kirim.email** di backend — MX record yang benar adalah `mx.kirimemail.com` (bukan `mail.sumopod.com`)
- Email baru dari domain baru akan masuk **junk/spam** selama beberapa minggu sampai reputasi domain terbentuk — ini normal
- Untuk mempercepat: klik "It's not junk" di Outlook, tambahkan sender ke kontak
- SMTP credentials lama (`cmnkhwt334d46pb08t4bxxoem`) adalah akun default Sumopod — **jangan dipakai**, gunakan credentials domain kustom di atas

---

## Health Check

```
GET /health
→ {"status": "ok", "app": "Toko Web Jaya", "env": "development", "db": "ok"}
```

---

## Common Issues

| Error | Cause | Fix |
|-------|-------|-----|
| Settings not updating | `lru_cache` on Settings | `--build` on docker compose |
| `unhashable type: 'dict'` | Jinja2 cache bug | Already fixed via `_render_error` helper |
| `passlib bcrypt` error | Incompatibility with Python 3.13 | Already fixed — using `bcrypt` directly |
| Port 5432 conflict | Local PG running | DB mapped to `5433:5432` |
| Email "relay failed: missing auth credentials" | SMTP credentials tidak terhubung ke custom domain | Buat credentials baru di Sumopod → Credentials → Create Credential untuk domain kustom |
| Email "550 No valid MX" | MX record salah/tidak ada | Tambahkan MX `mx.kirimemail.com` (Sumopod berbasis kirim.email) |
| Email masuk junk | Domain baru, reputasi nol | Klik "Not junk", tambahkan DMARC record, tunggu beberapa minggu |
