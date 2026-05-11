# SubasTech

SubasTech es una plataforma conversacional inteligente para agendar servicios tecnicos del hogar mediante WhatsApp. El sistema permite que una persona solicite servicios como plomeria, electricidad, cerrajeria, pintura o reparacion de electrodomesticos desde una conversacion natural.

## Objetivo

El objetivo del sistema es interpretar solicitudes recibidas por WhatsApp, apoyarse en un LLM local ejecutado con Ollama, consultar una base de datos PostgreSQL con tecnicos, disponibilidad y citas, y permitir crear, consultar, cancelar o reagendar servicios tecnicos de forma conversacional.

## Stack Tecnologico

- Frontend: Next.js
- Backend: Django + Django REST Framework
- Base de datos: PostgreSQL
- IA: Ollama con Llama 3.1 8B
- WhatsApp: Meta WhatsApp Cloud API
- Arquitectura: frontend separado del backend, API REST, webhooks para WhatsApp y cliente HTTP para Ollama.

## Arquitectura General

El proyecto esta dividido en dos aplicaciones principales:

- `frontend/`: aplicacion administrativa o de soporte construida con Next.js.
- `backend/`: API REST y servicios de integracion construidos con Django y Django REST Framework.

El backend se comunica con PostgreSQL para persistencia, con Ollama para interpretacion de mensajes y con Meta WhatsApp Cloud API para recibir y responder conversaciones.

## Modulos Principales

- `users`: gestion de usuarios, autenticacion futura y roles.
- `technicians`: tecnicos, especialidades, zonas de cobertura y disponibilidad.
- `appointments`: citas, estados, cancelaciones y reagendamientos.
- `chatbot`: flujo conversacional e interpretacion funcional del mensaje.
- `whatsapp`: webhooks e integracion con Meta WhatsApp Cloud API.
- `llm`: cliente HTTP para Ollama y Llama 3.1 8B.

## Flujo General del Sistema

1. El usuario escribe por WhatsApp solicitando un servicio.
2. Meta WhatsApp Cloud API envia el evento al webhook del backend.
3. Django recibe el mensaje y lo entrega al modulo `chatbot`.
4. El chatbot consulta el modulo `llm` para interpretar intencion, servicio, fecha, zona u otros datos.
5. El backend consulta PostgreSQL para buscar tecnicos y horarios disponibles.
6. El sistema propone horarios, agenda, cancela o reagenda segun la intencion.
7. El backend envia la respuesta a WhatsApp mediante Meta Cloud API.

## Variables de Entorno Esperadas

Ver `.env.example` para la lista base:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DATABASE_URL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `NEXT_PUBLIC_API_URL`

## Ejecucion Inicial

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Cuando exista la configuracion completa de Django:

```bash
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Estado del Proyecto

SubasTech esta en fase inicial/MVP. Esta estructura prepara el terreno para implementar posteriormente el backend, los webhooks de WhatsApp, la integracion con Ollama, la base de datos y el frontend administrativo.
