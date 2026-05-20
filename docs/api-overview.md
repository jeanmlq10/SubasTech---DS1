# API Overview

Resumen de los endpoints MVP que ya existen en el backend de SubasTech.

## Estado actual

El foco actual del MVP es:

- intake por Telegram/chatbot
- matching de tecnicos por reglas
- interpretacion encapsulada por `llm`
- agenda real de citas
- gestion de servicios y leads para tecnicos
- moderacion administrativa
- disputa con arbitro humano
- reputacion, penalizaciones y auditoria operativa

Los modulos `appointments`, `telegram_bot` y `llm` ya hacen parte de la API activa de este repositorio.

## Autenticacion

### `POST /api/auth/register/`

Registro publico.

- roles permitidos: `client`, `technician`
- roles bloqueados desde registro publico: `admin`, `arbiter`

### `POST /api/auth/token/`

Obtiene par `access` + `refresh` JWT.

### `POST /api/auth/token/refresh/`

Renueva el token de acceso.

### `GET /api/auth/me/`

Devuelve el usuario autenticado actual.

## Salud del sistema

### `GET /api/health/`

Endpoint publico de healthcheck con estado de base de datos y conteos basicos.

## Catalogo publico y administracion base

### `GET /api/categories/`

Lista categorias.

### `POST|PATCH|DELETE /api/categories/`

Solo administradores.

### `GET /api/zones/`

Lista zonas.

### `POST|PATCH|DELETE /api/zones/`

Solo administradores.

### `GET /api/services/`

Lista servicios publicos.

### `POST|PATCH|DELETE /api/services/`

Solo administradores.

### `GET /api/technicians/`

Lista perfiles tecnicos.

### `POST /api/technicians/`

Solo usuarios autenticados con rol `technician`.

### `PATCH|DELETE /api/technicians/<id>/`

Solo el tecnico propietario del perfil o un admin.

## Flujo tecnico

### `GET|POST|PATCH /api/technician/onboarding/`

Completa o consulta onboarding del tecnico autenticado.

### `GET|POST|PATCH|DELETE /api/technician/services/`

CRUD de servicios del tecnico autenticado.

### `GET|POST|DELETE /api/technician/service-photos/`

Gestion de fotos de servicios del tecnico autenticado.

### `GET /api/technician/leads/`

Lista solo los leads del tecnico autenticado.

### `POST /api/technician/leads/<id>/status/`

Actualiza estado del lead del tecnico autenticado.

Estados actuales:

- `new`
- `contacted`
- `accepted`
- `closed`

## Recomendaciones

### `POST /api/recommendations/`

Calcula recomendaciones de tecnicos usando:

- categoria
- ubicacion
- urgencia
- verificacion
- rating
- tiempo de respuesta
- reputacion/penalizaciones

## Agenda y disponibilidad

### `GET /api/appointments/`

Lista citas segun el actor autenticado:

- cliente: solo las suyas
- tecnico: solo las asociadas a su perfil
- admin: todas

### `POST /api/appointments/`

Crea cita real validando:

- disponibilidad semanal del tecnico
- conflictos con otras citas activas
- relacion tecnico/servicio/lead

### `POST /api/appointments/<id>/cancel/`

Cancela una cita visible para el actor.

### `POST /api/appointments/<id>/reschedule/`

Reagenda una cita visible para el actor.

### `POST /api/appointments/<id>/complete/`

Marca la cita como completada.

### `POST /api/appointments/<id>/no_show/`

Marca la cita como `no_show`.

### `GET /api/technicians/<id>/available-slots/`

Consulta slots disponibles del tecnico.

Admite filtros opcionales:

- `start_date`
- `days`
- `slot_minutes`
- `service_id`
- `category_id`
- `zone_id`

## Chatbot y Telegram

### `POST /api/chatbot/message/`

Endpoint interno para probar el flujo conversacional autenticado.

### `GET /api/chatbot/history/<chat_id>/`

Devuelve historial persistido de mensajes para el chat vinculado.

### `POST /api/chatbot/link-user/`

Asocia un `chat_id` con el usuario autenticado.

### `GET|POST /api/telegram/webhook/`

Webhook del bot de Telegram.

Notas:

- en local corre por defecto en `dry-run`
- para envio real se requiere `TELEGRAM_BOT_TOKEN`
- el backend registra auditoria de:
  - webhook recibido
  - mensaje enviado
  - lead creado
  - error de integracion

Flujo activo:

- seleccion de tecnico
- seleccion de horario real
- creacion de lead
- creacion de cita
- cancelacion desde chat
- reagendamiento desde chat

## LLM

### `POST /api/llm/interpret/`

Endpoint interno para interpretar mensajes.

Respuesta minima:

- `accion`
- `categoria`
- `urgencia`
- `zona`
- `confidence`
- `provider`

## Disputas y arbitraje

### `GET /api/disputes/`

Lista disputas segun el actor autenticado:

- cliente: solo las suyas
- tecnico: solo las asociadas a su perfil
- admin/arbiter: todas

### `POST /api/disputes/`

Solo usuarios con rol `client`.

### `GET|PATCH|DELETE /api/disputes/<id>/`

Disponible segun visibilidad/permisos del actor autenticado.

### `GET /api/arbiter/queue/`

Cola de arbitraje para `arbiter` o `admin`.

### `POST /api/arbiter/disputes/<id>/claim/`

Toma una disputa para revision.

### `POST /api/arbiter/disputes/<id>/decision/`

Resuelve una disputa.

Decisiones activas:

- `favor_client`
- `favor_technician`
- `partial`

## Reputacion y penalizaciones

### `GET|POST|DELETE /api/ratings/`

Calificaciones mutuas con reglas:

- `client -> technician`
- `technician -> client`
- se bloquean duplicados por la misma interaccion
- rating a cliente requiere `lead`

### `GET /api/penalties/`

- admin: ve todas
- tecnico: ve solo las propias

### `POST|PATCH|DELETE /api/penalties/`

Solo administradores.

Penalizaciones automaticas activas:

- `no_show`
- `late_cancellation`
- `lost_dispute`
- `low_reputation`

## Notificaciones

### `GET /api/notifications/`

- admin: puede ver todas
- usuario normal: solo las propias

### `POST /api/notifications/`

Solo administradores.

### `PATCH /api/notifications/<id>/`

Marca lectura u otros cambios sobre notificaciones visibles para el usuario.

Canales activos en modelo:

- `dashboard`
- `telegram`
- `whatsapp`
- `email`

## Auditoria

### `GET /api/audit/events/`

Solo administradores.

Expone eventos operativos como:

- webhook recibido
- mensaje enviado
- lead creado
- cita creada/cancelada/reagendada/completada/no_show
- lead actualizado
- disputa creada/claim/resuelta
- accion admin
- error de integracion

## Panel admin

### `GET /api/admin/summary/`

Resumen operativo del MVP con:

- tecnicos totales, verificados, pendientes y suspendidos
- servicios activos/inactivos
- leads por estado
- disputas por estado
- rating promedio
- reputacion promedio
- errores recientes
- tecnicos/servicios/disputas recientes
- distribucion de roles
- alertas operativas

### `POST /api/admin/technicians/<id>/verify/`
### `POST /api/admin/technicians/<id>/unverify/`
### `POST /api/admin/technicians/<id>/suspend/`
### `POST /api/admin/technicians/<id>/activate/`

Acciones de moderacion administrativa sobre tecnicos.

## Pruebas backend

Para correr pruebas sin depender de PostgreSQL local, usa:

```powershell
& { $env:USE_SQLITE_FOR_TESTS='true'; python backend\manage.py test }
```

El flag `USE_SQLITE_FOR_TESTS=true` fuerza SQLite temporal para pruebas y evita usar las variables `POSTGRES_*` del entorno local.
