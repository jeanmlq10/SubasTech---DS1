# Testing strategy

This repo uses a layered testing setup for the `staging` branch. See also the [Testing and CI](../README.md#testing-and-ci) section in the root README.

## Backend

Run Django checks and tests:

```bash
scripts/run-backend-tests.sh
```

Or from `backend/` with the project virtualenv:

```bash
.venv/bin/python manage.py test
```

On CI (GitHub Actions), tests run with `pip install -r requirements.txt` and system Python 3.12, using SQLite when `POSTGRES_DB` is not set.

Coverage priorities:

- authentication and role permissions
- recommendation scoring and filtering
- technician onboarding, services and leads
- admin moderation and metrics
- arbiter dispute claim and decision flows
- telegram chatbot booking, cancel and reschedule
- notification ownership and audit events

## Frontend

Install dependencies from `frontend/`:

```bash
npm install
```

Run static checks:

```bash
npm run lint
npm run build
```

`lint` runs ESLint with Next.js core-web-vitals and TypeScript rules (`eslint.config.mjs`).

## End-to-end

Playwright lives in `frontend/e2e`.

```bash
cd frontend
npm run e2e
```

The Playwright config (`playwright.config.ts`) starts both services:

- Django backend on `127.0.0.1:8000` via `scripts/run-e2e-backend.sh` (migrate, `seed_demo_data`, `runserver`)
- Next.js dev server on `127.0.0.1:3000` with `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api`

Current e2e coverage:

- public smoke test for `/`, `/login`, `/register` and `GET /api/health/`
- login redirect tests for `demo_admin`, `tech_carlos` and `demo_arbiter` (password `Subastech123!`)
- invalid login error handling

In CI: 2 retries, 1 worker, Chromium only.

## CI

GitHub Actions workflow: `.github/workflows/staging-tests.yml`

Runs on pull requests and pushes to `staging`:

1. **backend** — `python manage.py test`
2. **frontend** — `npm run lint` and `npm run build`
3. **e2e** — `npm run e2e` (depends on jobs 1 and 2)

Next recommended additions:

- Playwright: client registration and `/dashboard` access
- Playwright: technician lead status changes
- Playwright: arbiter claim and decision flows
- API integration tests for additional permission edge cases
