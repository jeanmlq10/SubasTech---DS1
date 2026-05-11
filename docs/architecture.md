# Arquitectura de SubasTech

SubasTech usa una arquitectura separada entre frontend y backend. El frontend en Next.js servira como interfaz administrativa y de soporte. El backend en Django + Django REST Framework expondra la API REST, recibira webhooks de WhatsApp, consultara PostgreSQL y se integrara con Ollama para interpretar mensajes.

## Flujo Textual

```text
Usuario WhatsApp -> Meta Cloud API -> Webhook Django -> Chatbot -> LLM Ollama -> PostgreSQL -> Respuesta WhatsApp
```

## Responsabilidad de Cada Modulo

- `users`: administrar usuarios internos, roles y permisos futuros.
- `technicians`: gestionar tecnicos, especialidades, zonas de cobertura y disponibilidad.
- `appointments`: manejar citas, estados, cancelaciones y reagendamientos.
- `chatbot`: coordinar el flujo conversacional, estados de conversacion e intenciones.
- `whatsapp`: recibir eventos por webhook y enviar respuestas mediante Meta WhatsApp Cloud API.
- `llm`: comunicarse por HTTP con Ollama y Llama 3.1 8B para interpretar mensajes.

## Decisiones Tecnicas Iniciales

- Separar frontend y backend para permitir despliegues independientes.
- Usar Django REST Framework para exponer endpoints claros y versionables.
- Usar PostgreSQL como base de datos principal por su confiabilidad y capacidad relacional.
- Ejecutar el LLM localmente con Ollama para mantener control sobre costos, privacidad y experimentacion.
- Encapsular WhatsApp y Ollama en modulos separados para evitar acoplar integraciones externas con la logica de negocio.
- Mantener el MVP enfocado en agendamiento conversacional antes de incorporar pagos, disputas o subastas.
