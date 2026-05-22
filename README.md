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
docs/       Project scope, architecture, API overview, testing guide
scripts/    setup-dev, run-backend, run-frontend
```

## Documentation

- [Project scope](docs/project-scope.md) — MVP focus (conversational booking; auctions out of scope)
- [Architecture](docs/architecture.md)
- [API overview](docs/api-overview.md)
- [Testing](docs/testing.md)

## Technology Stack

| Category | Technologies |
| --- | --- |
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn/ui (`@base-ui/react`), Lucide icons |
| **Backend framework** | Django |
| **API layer** | Django REST Framework (ViewSets, routers, serializers) |
| **Authentication** | `djangorestframework-simplejwt` (JWT access/refresh), custom `accounts.User` with role-based access |
| **Database** | SQLite (default local), PostgreSQL via `psycopg2-binary` (optional `POSTGRES_*` env or Docker Compose) |
| **ORM** | Django ORM |
| **Testing** | Django `manage.py test` (backend), Playwright E2E (`frontend/e2e`), ESLint (`npm run lint`) |
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
- **Modular monolith (backend)** — one Django deployable with domain apps; modules communicate via Python service imports and shared ORM models, not internal HTTP or message queues.

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
- `auctions`: secondary auction flow (Telegram and web); documented as outside core MVP in `docs/project-scope.md`.

## Frontend routes

| Route | Purpose | Auth |
| --- | --- | --- |
| `/` | Landing and login | Public |
| `/login` | Same login experience as `/` | Public |
| `/register` | Client or technician registration | Public |
| `/dashboard` | Client dashboard (appointments, disputes, ratings) | JWT required (`RequireAuth`) |
| `/technician` | Technician onboarding, services and leads | Session recommended |
| `/admin` | Administrator metrics and moderation | Session recommended |
| `/arbiter` | Dispute queue and decisions | Session recommended |

After login or registration, the app redirects by role (`roleHome`):

- `client` → `/dashboard`
- `technician` → `/technician`
- `admin` → `/admin`
- `arbiter` → `/arbiter`

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

| User | Role | Dashboard |
| --- | --- | --- |
| `demo_admin` | Administrator | `/admin` |
| `demo_arbiter` | Arbiter | `/arbiter` |
| `demo_client` | Client | Use with chatbot/ratings flows |
| `tech_carlos` | Technician | `/technician` |
| `tech_laura` | Technician | `/technician` |
| `tech_miguel` | Technician | `/technician` |

## Demo guide (10-minute presentation)

1. Open `http://localhost:3000/login` (or `/`).
2. **Register a client** at `http://localhost:3000/register` — choose **Cliente**, fill email and password; you are redirected to `/dashboard`.
3. **Staff dashboards:** log in as `demo_admin` → `/admin`; `tech_carlos` → `/technician`; `demo_arbiter` → `/arbiter`.
4. **Conversational booking:** with a JWT from a client user, call `POST /api/chatbot/message/` (see [Telegram bot flow](#telegram-bot-flow)) to simulate intake, recommendations and slot booking.
5. **Dispute moderation:** as `demo_arbiter`, claim and resolve the seeded open dispute.

For a full test checklist and E2E commands, see [docs/testing.md](docs/testing.md).

## Frontend authentication

Authentication uses the Django JWT API (`POST /api/auth/token/`). The frontend stores `access` and `refresh` tokens in `localStorage` (`subastech.auth`) and hydrates the user via `GET /api/auth/me/`.

- **Login:** `http://localhost:3000/login` or `/` — email or username + password.
- **Register:** `http://localhost:3000/register` — role **Cliente** (email required) or **Técnico** (phone, address, trade). Successful registration logs you in and redirects to `roleHome`.
- **Protected route:** `/dashboard` requires a stored session (`RequireAuth`); unauthenticated users are sent to `/login`.
- **Other dashboards** (`/admin`, `/technician`, `/arbiter`) load data when a session exists; some views still support pasting a JWT access token for local debugging.

Link Telegram after web login when the URL includes `?telegram_chat_id=<id>` (handled on the login form).

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

Visit `http://localhost:3000/arbiter` to test human-in-the-loop dispute moderation. Sign in as `demo_arbiter` (after `seed_demo_data`) or paste a JWT access token for a user with `role=arbiter`, `role=admin`, or Django staff permissions.

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

Visit `http://localhost:3000/admin` to load the administrator dashboard. Sign in as `demo_admin` or paste a JWT access token for either:

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

## Testing and CI

SubasTech uses a layered test setup documented in [docs/testing.md](docs/testing.md). GitHub Actions runs on pull requests and pushes to the `staging` branch (`.github/workflows/staging-tests.yml`).

### CI jobs

| Job | Command | What it validates |
| --- | --- | --- |
| **backend** | `python manage.py test` | Django tests across all apps (SQLite on the runner when `POSTGRES_DB` is unset) |
| **frontend** | `npm run lint` then `npm run build` | ESLint (Next.js rules) and production compile |
| **e2e** | `npm run e2e` (after backend + frontend jobs) | Playwright Chromium against live backend and Next dev server |

The **e2e** job installs Playwright with system deps, runs `scripts/run-e2e-backend.sh` (migrate + `seed_demo_data` + `runserver`), and starts Next with `NEXT_PUBLIC_API_URL` pointing at the API.

### Run tests locally

```bash
# Backend (requires scripts/setup-dev.sh first)
scripts/run-backend-tests.sh

# Frontend static checks
cd frontend && npm install && npm run lint && npm run build

# End-to-end (Playwright starts both servers automatically)
cd frontend && npm run e2e
```

Optional: `cd frontend && npm run e2e:ui` for the Playwright UI runner.

### Backend coverage (by app)

| App | Typical coverage |
| --- | --- |
| `accounts` | Public registration, JWT login, `/api/auth/me/` |
| `catalog` | Technician onboarding, services, documents, seeds |
| `recommendations` | Deterministic ranking and filters |
| `appointments` | Booking, cancel, reschedule, conflicts, audit side effects |
| `telegram_bot` | Chatbot API, webhook, conversational booking (Gemini disabled in tests) |
| `llm` | Rule-based intent and fallback |
| `disputes` / `reputation` | Arbiter workflow, ratings, penalties |
| `adminpanel` | Admin summary, verify/suspend, health endpoint |
| `notifications` / `audit` / `leads` / `auctions` | Templates, events, leads, secondary auction flow |

### Playwright E2E (`frontend/e2e`)

- **smoke.spec.ts** — `GET /api/health/`, public `/`, `/login`, `/register`
- **login.spec.ts** — demo user login redirects (`demo_admin`, `tech_carlos`, `demo_arbiter`) and invalid credentials

E2E relies on demo users from `seed_demo_data` (password `Subastech123!`). Config: `frontend/playwright.config.ts` (30s test timeout, 2 retries in CI, single worker in CI).

## MVP build order

1. Run `seed_initial_data` to create categories and zones.
2. Run `seed_demo_data` for presentation users and sample disputes.
3. Use `/technician` to complete technician onboarding and manage services with JWT auth.
4. Configure Telegram bot credentials and expose `/api/telegram/webhook/` publicly.
5. Validate end-to-end conversational booking, cancel and reschedule flows (API chatbot or real Telegram bot).
6. Harden frontend role guards on all dashboards and tighten public API permissions.
7. Expand dispute moderation, reputation effects and delivery artifacts (documento final, video demo, evidencia Jira).

## Team (Entrega Final)

| Member | Role |
| --- | --- |
| Jean Pierre | Product Owner |
| Daniel Mendez | Scrum Master |
| Juan Diego | Developer |
| Juan Camilo | Developer |

Task assignments for the MVP backlog are tracked in the team Jira board.
