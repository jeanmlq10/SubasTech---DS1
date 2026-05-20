"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Calendar,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Settings,
  User,
} from "lucide-react";

import { clearStoredAuth, getStoredAuth } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const sidebarLinks = [
  { href: "/dashboard", label: "Resumen", icon: LayoutDashboard },
  { href: "#", label: "Solicitudes", icon: ClipboardList },
  { href: "#", label: "Citas", icon: Calendar },
  { href: "#", label: "Mensajes", icon: MessageCircle },
  { href: "#", label: "Perfil", icon: User },
  { href: "#", label: "Ajustes", icon: Settings },
];

const statCards = [
  { title: "Solicitudes activas", value: "—", detail: "Próximamente" },
  { title: "Citas agendadas", value: "—", detail: "Próximamente" },
  { title: "Técnicos favoritos", value: "—", detail: "Próximamente" },
  { title: "Servicios completados", value: "—", detail: "Próximamente" },
];

export function ClientDashboard() {
  const router = useRouter();
  const [username, setUsername] = useState("");

  useEffect(() => {
    const session = getStoredAuth();
    if (session) {
      setUsername(session.user.username);
    }
  }, []);

  function logout() {
    clearStoredAuth();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 p-4 pb-8 md:flex-row md:p-6">
        <aside className="w-full shrink-0 rounded-2xl border bg-background p-4 shadow-sm md:w-64">
          <div className="mb-6">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">SubasTech</p>
            <h1 className="text-lg font-semibold">Mi dashboard</h1>
          </div>
          <nav className="space-y-1">
            {sidebarLinks.map((link) => {
              const Icon = link.icon;
              const active = link.href === "/dashboard";
              return (
                <Link
                  key={link.label}
                  href={link.href}
                  className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
                    active ? "bg-emerald-600 text-white" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <Icon className="size-4" />
                  {link.label}
                </Link>
              );
            })}
          </nav>
          <Separator className="my-4" />
          <Button variant="outline" className="w-full justify-start" onClick={logout}>
            <LogOut className="mr-2 size-4" />
            Cerrar sesión
          </Button>
        </aside>

        <main className="flex-1 space-y-6">
          <section className="rounded-2xl border bg-gradient-to-br from-emerald-600 to-teal-700 p-6 text-white shadow-sm">
            <Badge variant="secondary" className="mb-3 bg-white/20 text-white hover:bg-white/20">
              Bienvenido
            </Badge>
            <h2 className="text-2xl font-semibold sm:text-3xl">
              Hola{username ? `, ${username}` : ""} — tu espacio en SubasTech
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-emerald-50 sm:text-base">
              Desde aquí podrás gestionar solicitudes, citas y el seguimiento de tus servicios técnicos.
            </p>
          </section>

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {statCards.map((card) => (
              <Card key={card.title}>
                <CardHeader className="pb-2">
                  <CardDescription>{card.title}</CardDescription>
                  <CardTitle className="text-3xl">{card.value}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground">{card.detail}</p>
                </CardContent>
              </Card>
            ))}
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Actividad reciente</CardTitle>
                <CardDescription>Resumen de tus últimas interacciones</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Aún no hay actividad registrada. Cuando solicites un servicio, aparecerá aquí.
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Próximos pasos</CardTitle>
                <CardDescription>Comienza a usar la plataforma</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <p>1. Completa tu perfil con teléfono y dirección.</p>
                <p>2. Solicita un servicio técnico desde Telegram o la web.</p>
                <p>3. Revisa el estado de tus citas en este panel.</p>
              </CardContent>
            </Card>
          </section>
        </main>
      </div>
    </div>
  );
}
