# SubasTech

SubasTech is an AI-powered, WhatsApp-first platform for home technical services.

The current MVP direction is not a real-time auction system. The client experience starts in WhatsApp, where an AI-assisted intake flow extracts category, urgency and location. Django then applies deterministic business logic to filter and rank technicians.

## Product direction

- Clients use WhatsApp only.
- Technicians use a responsive web dashboard.
- Administrators use a responsive web dashboard.
- Arbiters use a responsive web dashboard with human-in-the-loop moderation.
- AI helps with controlled tasks such as category extraction, urgency detection, location extraction and dispute summaries.
- Recommendation scores are calculated in backend business logic, not by the AI model.


## Mobile-first UX

SubasTech is mobile-first through a conversational architecture, not a native app requirement. The client experience is WhatsApp-first, while technicians, administrators and arbiters use responsive web dashboards.

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

## Backend modules

- `accounts`: users, roles and JWT-ready auth endpoints.
- `catalog`: categories, zones, technician profiles, services, photos and availability.
- `recommendations`: deterministic technician ranking engine.
- `whatsapp`: webhook entry point and controlled intent extraction placeholder.
- `reputation`: ratings and penalties.
- `disputes`: dispute records, evidence, arbiter queue and human-in-the-loop decisions.
- `notifications`: dashboard/WhatsApp/email notification records.
- `leads`: WhatsApp-created service requests assigned to technicians.
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

This creates the initial service categories and Barranquilla/Soledad coverage zones used by onboarding, recommendations and WhatsApp matching.


## Demo guide

Visit `http://localhost:3000/demo` for an in-app presentation guide with demo users, route order and WhatsApp dry-run commands.

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
3. Send a dry-run WhatsApp request to `/api/whatsapp/webhook/` and reply with `1` to create a lead.
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
- `GET|POST /api/whatsapp/webhook/`

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


## WhatsApp lead flow

After SubasTech sends recommended technicians by WhatsApp, the client can reply with the option number, for example `1`. The backend uses the latest WhatsApp conversation state to create a `ServiceLead` assigned to the selected technician. The technician can see and update that lead from `/technician`.

Lead statuses:

- new
- contacted
- accepted
- closed

## WhatsApp Cloud API flow

The webhook lives at:

```txt
GET|POST /api/whatsapp/webhook/
```

For local development it runs in dry-run mode by default. The backend still parses the incoming WhatsApp payload, extracts intent and builds the outbound message, but it does not call Meta until `WHATSAPP_DRY_RUN=False` and credentials are configured.

Required environment variables for real delivery:

```env
WHATSAPP_VERIFY_TOKEN=subastech-dev-token
WHATSAPP_DRY_RUN=False
WHATSAPP_API_VERSION=v20.0
WHATSAPP_PHONE_NUMBER_ID=your_meta_phone_number_id
WHATSAPP_ACCESS_TOKEN=your_meta_access_token
```

Example local dry-run payload:

```bash
curl -X POST http://localhost:8000/api/whatsapp/webhook/   -H "Content-Type: application/json"   -d '{"from":"573001112233","message":"Necesito un electricista urgente en Riomar"}'
```

The response includes the extracted intent, ranked recommendations, the WhatsApp reply text and the outbound payload that would be sent to Meta.

## MVP build order

1. Run `seed_initial_data` to create categories and zones.
2. Use `/technician` to complete technician onboarding and manage services with JWT auth.
3. Configure Meta WhatsApp Cloud API credentials and expose `/api/whatsapp/webhook/` publicly.
4. Improve intent extraction with Gemini Flash or OpenRouter.
5. Add administrator and arbiter dashboard pages.
6. Expand dispute moderation and reputation effects.
