import Link from "next/link";
import { Bot, Gauge, MessageCircle, ShieldCheck, Star, Wrench } from "lucide-react";

import { MobileRoleNav } from "@/components/mobile-role-nav";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const modules = [
  {
    title: "WhatsApp AI intake",
    description: "El cliente explica el problema por WhatsApp y el sistema extrae categoria, urgencia y zona.",
    icon: MessageCircle,
  },
  {
    title: "Motor de recomendacion",
    description: "Django filtra tecnicos y calcula un puntaje por reputacion, disponibilidad, zona y respuesta.",
    icon: Gauge,
  },
  {
    title: "Panel de tecnicos",
    description: "Los tecnicos gestionan servicios, fotos, cobertura, disponibilidad, leads y reputacion.",
    icon: Wrench,
  },
  {
    title: "Moderacion humana",
    description: "La IA resume disputas, pero un arbitro humano toma la decision final.",
    icon: ShieldCheck,
  },
];

const recommendations = [
  { name: "Carlos Mendoza", trade: "Electricista", score: 94, zone: "Riomar", status: "Disponible" },
  { name: "Laura Perez", trade: "Tecnica de aires", score: 89, zone: "Norte Centro", status: "Disponible" },
  { name: "Miguel Rojas", trade: "Plomero", score: 84, zone: "Alto Prado", status: "Ocupado" },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-10 px-5 py-8 sm:px-8 lg:px-12">
        <nav className="flex items-center justify-between rounded-full border bg-card/80 px-4 py-3 shadow-sm backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-full bg-emerald-500 text-white">
              <Bot className="size-5" />
            </div>
            <div>
              <p className="text-sm font-semibold leading-none">SubasTech</p>
              <p className="text-xs text-muted-foreground">WhatsApp-first services</p>
            </div>
          </div>
          <Badge variant="secondary" className="hidden sm:inline-flex">
            Academic MVP
          </Badge>
        </nav>

        <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <div className="space-y-7">
            <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100 dark:bg-emerald-950 dark:text-emerald-200">
              Conversational mobile-first architecture
            </Badge>
            <div className="space-y-5">
              <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl lg:text-6xl">
                Encuentra tecnicos confiables desde WhatsApp, con recomendaciones asistidas por IA.
              </h1>
              <p className="max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
                SubasTech reemplaza las subastas en tiempo real por un flujo conversacional: el cliente escribe,
                la IA clasifica la solicitud y el backend recomienda las mejores opciones con reglas controladas.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                href="/login"
                className="inline-flex h-9 items-center justify-center rounded-lg bg-emerald-600 px-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
              >
                Entrar al proyecto
              </Link>
              <div className="flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/demo"
                  className="inline-flex h-9 items-center justify-center rounded-lg border px-2.5 text-sm font-medium transition-colors hover:bg-muted"
                >
                  Ver demo guiada
                </Link>
                <Link
                  href="/technician"
                  className="inline-flex h-9 items-center justify-center rounded-lg border px-2.5 text-sm font-medium transition-colors hover:bg-muted"
                >
                  Dashboard tecnico
                </Link>
                <Link
                  href="/admin"
                  className="inline-flex h-9 items-center justify-center rounded-lg border px-2.5 text-sm font-medium transition-colors hover:bg-muted"
                >
                  Dashboard admin
                </Link>
                <Link
                  href="/arbiter"
                  className="inline-flex h-9 items-center justify-center rounded-lg border px-2.5 text-sm font-medium transition-colors hover:bg-muted"
                >
                  Dashboard arbitro
                </Link>
              </div>
            </div>
          </div>

          <Card className="overflow-hidden border-emerald-100 shadow-xl dark:border-emerald-950">
            <CardHeader className="bg-muted/50">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <CardTitle>Solicitud por WhatsApp</CardTitle>
                  <CardDescription>&quot;Necesito un electricista urgente en Riomar&quot;</CardDescription>
                </div>
                <Badge>Alta urgencia</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-5 p-5">
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div className="rounded-xl border p-3">
                  <p className="text-muted-foreground">Categoria</p>
                  <p className="font-medium">Electricista</p>
                </div>
                <div className="rounded-xl border p-3">
                  <p className="text-muted-foreground">Zona</p>
                  <p className="font-medium">Riomar</p>
                </div>
                <div className="rounded-xl border p-3">
                  <p className="text-muted-foreground">Canal</p>
                  <p className="font-medium">WhatsApp</p>
                </div>
              </div>
              <Separator />
              <div className="space-y-3">
                {recommendations.map((item) => (
                  <div key={item.name} className="flex items-center justify-between rounded-2xl border p-4">
                    <div>
                      <p className="font-medium">{item.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {item.trade} - {item.zone} - {item.status}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 rounded-full bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-900 dark:bg-amber-950 dark:text-amber-200">
                      <Star className="size-4 fill-current" />
                      {item.score}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {modules.map((module) => {
            const Icon = module.icon;
            return (
              <Card key={module.title}>
                <CardHeader>
                  <div className="mb-2 flex size-11 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200">
                    <Icon className="size-5" />
                  </div>
                  <CardTitle className="text-lg">{module.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-6 text-muted-foreground">{module.description}</p>
                </CardContent>
              </Card>
            );
          })}
        </section>
      </section>
      <MobileRoleNav />
    </main>
  );
}
