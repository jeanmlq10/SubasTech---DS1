# Arquitectura de SubasTech

SubasTech usa una arquitectura separada entre frontend y backend. El frontend en Next.js sirve como interfaz administrativa y de soporte. El backend en Django + Django REST Framework expone la API REST, recibe webhooks de Telegram, consulta PostgreSQL o SQLite y encapsula interpretacion por LLM con fallback por reglas.

## Flujo Textual

```text
Usuario Telegram -> Telegram Bot API -> Webhook Django -> Flujo conversacional -> LLM -> PostgreSQL/SQLite -> Respuesta Telegram
```

## Responsabilidad de Cada Modulo

- `accounts`: administrar usuarios, roles y autenticacion.
- `catalog`: gestionar tecnicos, especialidades, zonas de cobertura y disponibilidad.
- `appointments`: manejar citas, estados, cancelaciones y reagendamientos.
- `telegram_bot`: coordinar el flujo conversacional, historial, webhook y canal Telegram.
- `llm`: encapsular interpretacion de mensajes via proveedor externo y fallback local.
- `notifications`: plantillas, registros y payloads enriquecidos de salida.

## Decisiones Tecnicas Iniciales

- Separar frontend y backend para permitir despliegues independientes.
- Usar Django REST Framework para exponer endpoints claros y versionables.
- Usar PostgreSQL como base de datos principal por su confiabilidad y capacidad relacional.
- Encapsular el proveedor LLM en una app separada para evitar acoplar integraciones externas con el flujo conversacional.
- Mantener el canal conversacional desacoplado de la logica de negocio de citas, reputacion y notificaciones.
- Mantener el MVP enfocado en agendamiento conversacional antes de incorporar pagos, disputas o subastas.
