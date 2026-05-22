# Testing strategy

This repo uses a layered testing setup for the `staging` branch and a split GitHub Actions pipeline.

## Backend

Run the full Django test suite:

```bash
scripts/run-backend-tests.sh
```

Run one app in isolation:

```bash
cd backend
USE_SQLITE_FOR_TESTS=true python manage.py test accounts
```

Coverage priorities:

- authentication and role permissions
- recommendation scoring and filtering
- technician onboarding, services and leads
- admin moderation and metrics
- arbiter dispute claim and decision flows
- notification ownership and visibility

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

## End-to-end

Playwright lives in `frontend/e2e`.

```bash
cd frontend
npm run e2e
```

The Playwright config starts both services:

- Django backend on `127.0.0.1:8000`
- Next frontend on `127.0.0.1:3000`

The backend server script runs migrations and loads demo data before serving.

Current e2e coverage:

- public smoke test for `/`, `/login`, `/demo` and `/api/health/`
- login redirect tests for admin, technician and arbiter demo users
- invalid login error handling

## CI

GitHub Actions now uses three workflows:

- `ci-pipeline.yml`: main entrypoint for pushes and pull requests to `staging`
- `individual-backend-tests.yml`: reusable/manual workflow that runs one Django app per matrix job
- `e2e-tests.yml`: reusable/manual Playwright workflow with uploaded reports and traces

The main CI pipeline runs:

- backend Django tests split by app
- frontend lint and build
- Playwright e2e tests with Chromium after backend and frontend succeed

Next recommended additions:

- API integration tests for admin, technician and arbiter permissions
- Playwright tests for technician lead status changes
- Playwright tests for arbiter claim and decision flows
- component tests for login and dashboard data states
