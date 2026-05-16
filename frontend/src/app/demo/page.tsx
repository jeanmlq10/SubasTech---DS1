import Link from "next/link";
import { CheckCircle2, HeartPulse, MessageCircle, MonitorSmartphone, PlayCircle, ShieldCheck, UserCheck } from "lucide-react";

import { MobileRoleNav } from "@/components/mobile-role-nav";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const demoUsers = [
  { username: "demo_admin", role: "Administrador", route: "/admin", description: "Ver metricas, verificar tecnicos y crear categorias/zonas." },
  { username: "tech_carlos", role: "Tecnico", route: "/technician", description: "Gestionar perfil, servicios y leads recibidos desde WhatsApp." },
  { username: "demo_arbiter", role: "Arbitro", route: "/arbiter", description: "Revisar disputas con asistencia IA y registrar decision humana." },
];

const flow = [
  { title: "1. Login por rol", icon: UserCheck, text: "Entra por /login con usuarios demo. Todos usan Subastech123!." },
  { title: "2. Admin prepara la plataforma", icon: ShieldCheck, text: "Revisa metricas, verifica tecnicos y confirma categorias/zonas." },
  { title: "3. Cliente conversa por WhatsApp", icon: MessageCircle, text: "El webhook extrae categoria, urgencia y ubicacion; luego recomienda tecnicos." },
  { title: "4. Cliente elige opcion", icon: PlayCircle, text: "Si responde 1, 2 o 3, SubasTech crea un lead para el tecnico seleccionado." },
  { title: "5. Tecnico gestiona lead", icon: MonitorSmartphone, text: "En /technician el tecnico marca el lead como contactado, aceptado o cerrado." },
  { title: "6. Arbitro modera disputas", icon: HeartPulse, text: "La IA resume y clasifica, pero la decision final la registra un humano." },
];

export default function DemoPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 pb-28 pt-5 sm:px-8 md:pb-10 lg:px-12">
      <section className="rounded-3xl border bg-card p-6 shadow-sm">
        <Badge variant="secondary">Guia de presentacion</Badge>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-5xl">Demo guiada de SubasTech</h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-muted-foreground sm:text-base">
          Usa esta ruta para presentar el proyecto completo: WhatsApp-first para clientes, dashboards responsive para roles internos, recomendaciones deterministicas y moderacion human-in-the-loop.
        </p>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <Link className="inline-flex h-10 items-center justify-center rounded-lg bg-emerald-600 px-4 text-sm font-medium text-white hover:bg-emerald-700" href="/login">
            Ir al login
          </Link>
          <Link className="inline-flex h-10 items-center justify-center rounded-lg border px-4 text-sm font-medium hover:bg-muted" href="/">
            Volver al inicio
          </Link>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {demoUsers.map((user) => (
          <Card key={user.username}>
            <CardHeader>
              <CardTitle>{user.role}</CardTitle>
              <CardDescription>{user.username}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm leading-6 text-muted-foreground">{user.description}</p>
              <div className="rounded-2xl bg-muted p-3 text-sm">
                <p><strong>Usuario:</strong> {user.username}</p>
                <p><strong>Clave:</strong> Subastech123!</p>
              </div>
              <Link className="inline-flex h-9 w-full items-center justify-center rounded-lg border text-sm font-medium hover:bg-muted" href="/login">
                Entrar como {user.role.toLowerCase()}
              </Link>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {flow.map((step) => {
          const Icon = step.icon;
          return (
            <Card key={step.title}>
              <CardHeader>
                <div className="mb-2 flex size-11 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200">
                  <Icon className="size-5" />
                </div>
                <CardTitle className="text-lg">{step.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-6 text-muted-foreground">{step.text}</p>
              </CardContent>
            </Card>
          );
        })}
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Comandos utiles para la demo</CardTitle>
          <CardDescription>Ejecutalos desde la carpeta del proyecto si necesitas preparar datos.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <pre className="overflow-x-auto rounded-2xl bg-muted p-4">{`cd backend\n.venv/bin/python manage.py migrate\n.venv/bin/python manage.py seed_demo_data`}</pre>
          <pre className="overflow-x-auto rounded-2xl bg-muted p-4">{`curl -X POST http://localhost:8000/api/whatsapp/webhook/ \\\n  -H "Content-Type: application/json" \\\n  -d '{"from":"573001112233","message":"Necesito un electricista urgente en Riomar"}'`}</pre>
          <div className="flex items-center gap-2 text-emerald-700">
            <CheckCircle2 className="size-4" />
            <span>Luego envia otro POST con {`{"from":"573001112233","message":"1"}`} para crear el lead.</span>
          </div>
        </CardContent>
      </Card>
      <MobileRoleNav />
    </main>
  );
}
