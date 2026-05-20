"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
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
import { API_URL, Auction, Category, Zone } from "@/lib/api";
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
  const [token, setToken] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [auctions, setAuctions] = useState<Auction[]>([]);
  const [message, setMessage] = useState("Cargando dashboard...");
  const [auctionForm, setAuctionForm] = useState({
    category: "",
    zone: "",
    title: "",
    description: "",
    location: "",
    budgetMax: "",
  });

  useEffect(() => {
    const session = getStoredAuth();
    if (session) {
      setUsername(session.user.username);
      setToken(session.accessToken);
      void loadClientData(session.accessToken);
    } else {
      setMessage("Inicia sesion para crear subastas.");
    }
  }, []);

  async function loadClientData(accessToken: string) {
    try {
      const [categoryResponse, zoneResponse, auctionResponse] = await Promise.all([
        fetch(`${API_URL}/categories/`),
        fetch(`${API_URL}/zones/`),
        fetch(`${API_URL}/auctions/`, { headers: { Authorization: `Bearer ${accessToken}` } }),
      ]);
      if (!categoryResponse.ok || !zoneResponse.ok || !auctionResponse.ok) {
        throw new Error("Client data request failed");
      }
      setCategories((await categoryResponse.json()) as Category[]);
      setZones((await zoneResponse.json()) as Zone[]);
      setAuctions((await auctionResponse.json()) as Auction[]);
      setMessage("Dashboard actualizado.");
    } catch {
      setMessage("No se pudo cargar la informacion de subastas.");
    }
  }

  async function createAuction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      setMessage("Inicia sesion antes de crear subastas.");
      return;
    }

    try {
      const response = await fetch(`${API_URL}/auctions/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          category: Number(auctionForm.category),
          zone: auctionForm.zone ? Number(auctionForm.zone) : null,
          title: auctionForm.title,
          description: auctionForm.description,
          location: auctionForm.location,
          budget_max: auctionForm.budgetMax || null,
        }),
      });
      if (!response.ok) {
        throw new Error("Auction create failed");
      }
      setAuctionForm({ category: "", zone: "", title: "", description: "", location: "", budgetMax: "" });
      await loadClientData(token);
      setMessage("Subasta creada.");
    } catch {
      setMessage("No se pudo crear la subasta.");
    }
  }

  async function awardBid(auctionId: number, bidId: number) {
    if (!token) {
      setMessage("Inicia sesion antes de adjudicar.");
      return;
    }

    try {
      const response = await fetch(`${API_URL}/auctions/${auctionId}/award/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ bid_id: bidId }),
      });
      if (!response.ok) {
        throw new Error("Award request failed");
      }
      await loadClientData(token);
      setMessage("Oferta adjudicada. El tecnico recibira el lead.");
    } catch {
      setMessage("No se pudo adjudicar la oferta.");
    }
  }

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
                <CardTitle>Nueva subasta</CardTitle>
                <CardDescription>Publica una solicitud para recibir ofertas de tecnicos.</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="space-y-3" onSubmit={createAuction}>
                  <select
                    value={auctionForm.category}
                    onChange={(event) => setAuctionForm((current) => ({ ...current, category: event.target.value }))}
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                    required
                  >
                    <option value="">Categoria</option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                  <select
                    value={auctionForm.zone}
                    onChange={(event) => setAuctionForm((current) => ({ ...current, zone: event.target.value }))}
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                  >
                    <option value="">Zona opcional</option>
                    {zones.slice(0, 80).map((zone) => (
                      <option key={zone.id} value={zone.id}>
                        {zone.name}, {zone.city}
                      </option>
                    ))}
                  </select>
                  <input
                    value={auctionForm.title}
                    onChange={(event) => setAuctionForm((current) => ({ ...current, title: event.target.value }))}
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                    placeholder="Titulo de la solicitud"
                    required
                  />
                  <textarea
                    value={auctionForm.description}
                    onChange={(event) => setAuctionForm((current) => ({ ...current, description: event.target.value }))}
                    className="min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm"
                    placeholder="Describe el problema y condiciones."
                    required
                  />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      value={auctionForm.location}
                      onChange={(event) => setAuctionForm((current) => ({ ...current, location: event.target.value }))}
                      className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                      placeholder="Direccion o barrio"
                    />
                    <input
                      value={auctionForm.budgetMax}
                      onChange={(event) => setAuctionForm((current) => ({ ...current, budgetMax: event.target.value }))}
                      className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                      placeholder="Presupuesto maximo"
                      type="number"
                      min="0"
                    />
                  </div>
                  <Button className="w-full bg-emerald-600 hover:bg-emerald-700" type="submit">
                    Crear subasta
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Mis subastas</CardTitle>
                <CardDescription>Revisa ofertas y adjudica el tecnico ganador.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">{message}</p>
                {auctions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Aun no tienes subastas creadas.</p>
                ) : (
                  auctions.map((auction) => (
                    <div key={auction.id} className="rounded-xl border p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium">{auction.title}</p>
                          <p className="text-sm text-muted-foreground">
                            {auction.category_name} - {auction.location || auction.zone_name || "Sin zona"}
                          </p>
                        </div>
                        <Badge variant={auction.status === "open" ? "default" : "secondary"}>{auction.status}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">{auction.description}</p>
                      <div className="mt-3 space-y-2">
                        {auction.bids.length === 0 ? (
                          <p className="text-sm text-muted-foreground">Sin ofertas todavia.</p>
                        ) : (
                          auction.bids.map((bid) => (
                            <div key={bid.id} className="flex flex-col gap-2 rounded-lg bg-muted/50 p-3 sm:flex-row sm:items-center sm:justify-between">
                              <div>
                                <p className="text-sm font-medium">
                                  {bid.technician_name} - ${Number(bid.amount).toLocaleString("es-CO")}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {bid.message || "Sin mensaje"} | {bid.estimated_minutes} min
                                </p>
                              </div>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => void awardBid(auction.id, bid.id)}
                                disabled={auction.status !== "open" || bid.status !== "pending"}
                              >
                                Adjudicar
                              </Button>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
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
