def appointment_reminder(context: dict) -> dict:
    technician_name = context.get("technician_name", "tu tecnico")
    scheduled_for = context.get("scheduled_for", "tu horario programado")
    return {
        "title": "Recordatorio de cita",
        "message": f"Recuerda tu cita con {technician_name} para {scheduled_for}.",
    }


def technician_assigned(context: dict) -> dict:
    technician_name = context.get("technician_name", "un tecnico")
    service_title = context.get("service_title", "tu servicio")
    return {
        "title": "Tecnico asignado",
        "message": f"{technician_name} fue asignado para atender {service_title}.",
    }


def lead_received(context: dict) -> dict:
    client_name = context.get("client_name", "un cliente")
    category = context.get("category", "un servicio")
    return {
        "title": "Nueva solicitud",
        "message": f"{client_name} envio una nueva solicitud para {category}.",
    }


MESSAGE_TEMPLATES = {
    "appointment_reminder": appointment_reminder,
    "technician_assigned": technician_assigned,
    "lead_received": lead_received,
}
