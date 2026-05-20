# SubasTech

SubasTech is an AI-powered, Telegram-first platform for home technical services.

The current MVP direction is not a real-time auction system. The client experience starts in Telegram/chatbot, where an AI-assisted intake flow extracts category, urgency and location. Django then applies deterministic business logic to filter and rank technicians, propose real appointment slots and create bookings.

## Product direction

- Clients use Telegram/chatbot.
- Technicians use a responsive web dashboard.
- Administrators use a responsive web dashboard.
- Arbiters use a responsive web dashboard with human-in-the-loop moderation.
- AI helps with controlled tasks such as category extraction, urgency detection, location extraction and dispute summaries.
- Recommendation scores are calculated in backend business logic, not by the AI model.


## Mobile-first UX

SubasTech is mobile-first through a conversational architecture, not a native app requirement. The client experience is Telegram-first, while technicians, administrators and arbiters use responsive web dashboards.

Current mobile UX support includes:

- fixed bottom navigation on small screens
- touch-sized dashboard actions
- card-based mobile lists for technician services, admin technician moderation and arbiter dispute queue
- desktop tables preserved for wider screens
- responsive forms and dashboard layouts

## Repository structure

```txt
frontend/   Next.js 15, TypeScript, Tailwind CSS, shadcn/ui
backend/    Django, Django REST Framework, JWT auth, recommendation modules
```

## Technology Stack

| Category | Technologies |
| --- | --- |
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn/ui (`@base-ui/react`), Lucide icons |
| **Backend framework** | Django |
| **API layer** | Django REST Framework (ViewSets, routers, serializers) |
| **Authentication** | `djangorestframework-simplejwt` (JWT access/refresh), custom `accounts.User` with role-based access |
| **Database** | SQLite (default local), PostgreSQL via `psycopg2-binary` (optional `POSTGRES_*` env or Docker Compose) |
| **ORM** | Django ORM |
| **Testing** | Django `manage.py test` (backend), Playwright (frontend E2E), ESLint (`next lint`) |
| **Architecture style** | Monorepo with modular Django apps, service-layer business logic, REST API + responsive Next.js dashboards |
| **Conversational channel** | Telegram (`python-telegram-bot` webhook and chatbot flow) |
| **LLM integration** | Google Gemini (`google-genai`) with deterministic rule-based fallback in `llm` |
| **Notifications** | `notifications` app (in-app records; channels include dashboard, Telegram, email, WhatsApp enum) |
| **WhatsApp integration** | Legacy identifiers and channel enums (`whatsapp_id`, lead `source=whatsapp`); no WhatsApp Business API client in the MVP—client intake is Telegram-first |
| **Media** | Pillow (service photos and uploads) |
| **Containerization** | Docker Compose (`postgres`, `backend`, `frontend`), per-service Dockerfiles |
| **Deployment / infrastructure** | GitHub Actions workflow on `staging` (backend tests, frontend lint/build, Playwright E2E); `gunicorn` listed for production-style serving |
| **Development tools** | `python-dotenv`, `python-decouple`, `django-cors-headers`, `requests`, project scripts under `scripts/` |

### Backend Architecture Highlights

- **Service-layer architecture** — domain rules live in `*/services.py` modules (appointments, reputation, disputes, audit, recommendations, LLM, notifications, auctions); views stay thin.
- **DRF ViewSets** — catalog, appointments, leads, disputes, reputation, notifications, and audit exposed through registered routers in `config/urls.py`.
- **JWT authentication** — global `JWTAuthentication` with token and refresh endpoints; role-aware permission classes in `accounts.permissions`.
- **Audit logging** — `audit` app records operational events via `audit.services.log_audit_event`.
- **Role-based permissions** — clients, technicians, administrators, and arbiters enforced in view/queryset layers and custom DRF permissions.
- **Transactional business logic** — appointment and conversational flows use `transaction.atomic()` and `select_for_update` where scheduling conflicts matter.
- **Appointment scheduling** — dedicated `appointments` models and services for slot calculation, booking, cancellation, rescheduling, and completion with lead and notification side effects.

## Backend modules

- `accounts`: users, roles and JWT-ready auth endpoints.
- `catalog`: categories, zones, technician profiles, services, photos and availability.
- `recommendations`: deterministic technician ranking engine.
- `telegram_bot`: webhook entry point, chatbot session flow and Telegram delivery.
- `llm`: encapsulated message interpretation with provider + fallback rules.
- `reputation`: ratings and penalties.
- `disputes`: dispute records, evidence, arbiter queue and human-in-the-loop decisions.
- `notifications`: dashboard/Telegram/email notification records plus reusable templates.
- `leads`: conversational service requests assigned to technicians.
- `appointments`: real scheduling, cancellation and rescheduling.
- `adminpanel`: administrator summary metrics for dashboard monitoring.

## Local development

### One-command setup

```bash
scripts/setup-dev.sh
```

The setup script installs the required Ubuntu packages when `apt-get` is available:

- Node.js/npm already provided by the environment
- Python 3.12 virtualenv support (`python3.12-venv`)
- PostgreSQL client and build libraries (`postgresql-client`, `libpq-dev`)
- backend dependencies into `backend/.venv`
- frontend dependencies into `frontend/node_modules`

### PostgreSQL

SQLite is used by default for quick local development. To run PostgreSQL locally:

```bash
docker compose up -d postgres
cp backend/.env.example backend/.env
```

Then keep the PostgreSQL variables enabled in `backend/.env`.

If you already have a PostgreSQL database, set these values in `backend/.env`:

```env
POSTGRES_DB=your_database
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=your_host
POSTGRES_PORT=5432
```

Then run:

```bash
cd backend
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_initial_data
```

### Frontend

```bash
scripts/run-frontend.sh
```

Open `http://localhost:3000`.

### Backend

```bash
scripts/run-backend.sh
```

Open `http://localhost:8000/api/`.

### Seed initial data

```bash
cd backend
.venv/bin/python manage.py seed_initial_data
```

This creates the initial service categories and Barranquilla/Soledad coverage zones used by onboarding, recommendations and conversational matching.


## Demo guide

Visit `http://localhost:3000/demo` for an in-app presentation guide with demo users and route order.

## Demo data

Run this after migrations to create demo users, verified technicians, services, leads, ratings and a dispute:

```bash
cd backend
.venv/bin/python manage.py seed_demo_data
```

All demo users use this password:

```txt
Subastech123!
```

Demo users:

- `demo_admin` -> administrator dashboard `/admin`
- `demo_arbiter` -> arbiter dashboard `/arbiter`
- `demo_client` -> client identity for ratings/disputes
- `tech_carlos` -> technician dashboard `/technician`
- `tech_laura` -> technician dashboard `/technician`
- `tech_miguel` -> technician dashboard `/technician`

Suggested demo flow:

1. Login as `demo_admin` and review metrics, categories, zones and technician moderation.
2. Login as `tech_carlos` and review services/leads.
3. Use `/api/chatbot/message/` to simulate a Telegram conversation and create a booking.
4. Login as `demo_arbiter` and review the open dispute.

## Frontend authentication

Visit `http://localhost:3000/login` to authenticate with the Django JWT backend. After login, the frontend stores the session locally and redirects by role:

- `technician` -> `/technician`
- `admin` -> `/admin`
- `arbiter` -> `/arbiter`
- `client` -> `/`

Dashboards still allow manual tokens for testing, but they now automatically reuse the saved session.

## First API endpoints

- `POST /api/auth/register/`
- `POST /api/auth/token/`
- `GET /api/health/`
- `GET /api/auth/me/`
- `GET /api/categories/`
- `GET /api/zones/`
- `GET /api/services/`
- `GET|POST|PATCH /api/technician/onboarding/`
- `GET|POST|PATCH|DELETE /api/technician/services/`
- `GET|POST|DELETE /api/technician/service-photos/`
- `GET /api/technician/leads/`
- `POST /api/technician/leads/<id>/status/`
- `GET /api/admin/summary/`
- `GET /api/arbiter/queue/`
- `POST /api/arbiter/disputes/<id>/claim/`
- `POST /api/arbiter/disputes/<id>/decision/`
- `POST /api/recommendations/`
- `GET /api/appointments/`
- `POST /api/appointments/`
- `GET /api/technicians/<id>/available-slots/`
- `POST /api/chatbot/message/`
- `GET /api/chatbot/history/<chat_id>/`
- `GET|POST /api/telegram/webhook/`
- `POST /api/llm/interpret/`

Example recommendation request:

```json
{
  "category": "electrician",
  "location": "Riomar",
  "urgency": "high",
  "limit": 5
}
```



## Arbiter dashboard

Visit `http://localhost:3000/arbiter` to test human-in-the-loop dispute moderation. Paste a JWT access token for a user with `role=arbiter`, `role=admin`, or Django staff permissions.

The arbiter flow is intentionally not autonomous:

1. The system lists open and in-review disputes.
2. Controlled AI helpers summarize the complaint, classify the dispute type and suggest priority.
3. The human arbiter claims the case.
4. The human arbiter records the final decision:
   - favor client
   - favor technician
   - partial resolution
5. The backend stores the decision, arbiter and arbiter notes.

## Admin dashboard

Visit `http://localhost:3000/admin` to load the administrator dashboard. Paste a JWT access token for either:

- a Django staff/superuser, or
- a SubasTech user with `role=admin`.

The dashboard consumes `GET /api/admin/summary/` and shows platform metrics, recent technicians, services, disputes, role distribution and operational alerts.

Administrative actions available:

- verify/unverify technicians
- suspend/reactivate technician users
- create service categories
- create coverage zones

Related endpoints:

- `POST /api/admin/technicians/<id>/verify/`
- `POST /api/admin/technicians/<id>/unverify/`
- `POST /api/admin/technicians/<id>/suspend/`
- `POST /api/admin/technicians/<id>/activate/`
- `POST /api/categories/` with admin token
- `POST /api/zones/` with admin token


## Telegram lead flow

After SubasTech sends recommended technicians by Telegram/chatbot, the client can reply with the option number, choose a real slot and create both a `ServiceLead` and an `Appointment`. The technician can see and update that lead from `/technician`.

Lead statuses:

- new
- contacted
- accepted
- closed

## Telegram bot flow

The webhook lives at:

```txt
GET|POST /api/telegram/webhook/
```

For local development it runs in dry-run mode by default. The backend still parses the incoming Telegram payload, extracts intent, chooses technicians, proposes slots and builds the outbound message, but it does not call Telegram until `TELEGRAM_DRY_RUN=False` and credentials are configured.

Required environment variables for real delivery:

```env
TELEGRAM_DRY_RUN=False
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

Example local chatbot payload:

```bash
curl -X POST http://localhost:8000/api/chatbot/message/ -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"chat_id":101,"text":"Necesito un electricista urgente en Riomar"}'
```

The response includes the extracted intent, ranked recommendations or slot options, and the chatbot reply text.

## MVP build order

1. Run `seed_initial_data` to create categories and zones.
2. Use `/technician` to complete technician onboarding and manage services with JWT auth.
3. Configure Telegram bot credentials and expose `/api/telegram/webhook/` publicly.
4. Validate end-to-end conversational booking, cancel and reschedule flows against a real Telegram bot.
5. Add administrator and arbiter dashboard pages.
6. Expand dispute moderation and reputation effects.
