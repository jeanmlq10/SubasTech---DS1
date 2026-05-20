"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Calendar, ClipboardList, LayoutDashboard, LogOut, MessageCircle, Settings, User } from "lucide-react";

import { API_URL, Auction, Category, Zone } from "@/lib/api";
import { clearStoredAuth, restoreSession, roleHome } from "@/lib/auth";
import { MobileRoleNav } from "@/components/mobile-role-nav";
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

const surfaceClass = "rounded-2xl border border-white/10 bg-white/5 shadow-2xl backdrop-blur-md";
const fieldClass = "border-white/20 bg-white/10 text-white placeholder:text-white/50";
const selectClass = "h-10 w-full rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white";

export function ClientDashboard() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [token, setToken] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [auctions, setAuctions] = useState<Auction[]>([]);
  const [message, setMessage] = useState("Cargando dashboard...");
  const [isBooting, setIsBooting] = useState(true);
  const [auctionForm, setAuctionForm] = useState({
    category: "",
    zone: "",
    title: "",
    description: "",
    location: "",
    budgetMax: "",
  });

  useEffect(() => {
    let mounted = true;

    void (async () => {
      const session = await restoreSession();
      if (!mounted) {
        return;
      }
      if (!session) {
        router.replace("/login");
        return;
      }
      if (session.user.role !== "client") {
        router.replace(roleHome(session.user.role));
        return;
      }
      setUsername(session.user.username);
      setToken(session.accessToken);
      await loadClientData(session.accessToken);
      setIsBooting(false);
    })();

    return () => {
      mounted = false;
    };
  }, [router]);

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
        const payload = (await response.json().catch(() => null)) as { detail?: string; scheduled_start?: string[] } | null;
        throw new Error(payload?.detail || payload?.scheduled_start?.join(", ") || "No se pudo adjudicar la oferta.");
      }
      await loadClientData(token);
      setMessage("Oferta adjudicada. El tecnico recibira el lead.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo adjudicar la oferta.");
    }
  }

  function logout() {
    clearStoredAuth();
    router.replace("/login");
  }

  const openAuctions = auctions.filter((auction) => auction.status === "open");
  const awardedAuctions = auctions.filter((auction) => auction.status === "awarded");
  const receivedBids = auctions.reduce((total, auction) => total + auction.bids.length, 0);
  const closedAuctions = auctions.filter((auction) => ["cancelled", "expired"].includes(auction.status)).length;
  const statCards = [
    { title: "Solicitudes activas", value: String(openAuctions.length), detail: `${auctions.length} solicitudes totales` },
    { title: "Citas adjudicadas", value: String(awardedAuctions.length), detail: "ofertas ganadoras" },
    { title: "Ofertas recibidas", value: String(receivedBids), detail: "de tecnicos verificados" },
    { title: "Cerradas/canceladas", value: String(closedAuctions), detail: "fuera del flujo activo" },
  ];

  if (isBooting) {
    return <div className="min-h-screen bg-gradient-to-b from-slate-900 via-purple-900 to-slate-950" />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-purple-900 to-slate-950 text-white">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-10 h-72 w-72 -translate-x-1/2 rounded-full bg-rose-500/20 blur-3xl" />
        <div className="absolute bottom-20 right-10 h-80 w-80 rounded-full bg-orange-400/10 blur-3xl" />
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col gap-6 p-4 pb-28 md:flex-row md:p-6 md:pb-10">
        <aside className={`${surfaceClass} w-full shrink-0 p-4 md:w-64`}>
          <div className="mb-6">
            <p className="text-xs font-medium uppercase tracking-wide text-purple-200">SubasTech</p>
            <h1 className="text-lg font-semibold text-white">Mi dashboard</h1>
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
                    active ? "bg-gradient-to-r from-orange-400 to-rose-500 text-white" : "text-purple-100 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <Icon className="size-4" />
                  {link.label}
                </Link>
              );
            })}
          </nav>
          <Separator className="my-4 bg-white/10" />
          <Button variant="ghost" className="w-full justify-start border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white" onClick={logout}>
            <LogOut className="mr-2 size-4" />
            Cerrar sesion
          </Button>
        </aside>

        <main className="flex-1 space-y-6">
          <section className={`${surfaceClass} p-6 md:p-8`}>
            <Badge className="mb-3 border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">Bienvenido</Badge>
            <h2 className="text-2xl font-bold text-white sm:text-3xl">Hola{username ? `, ${username}` : ""} - tu espacio en SubasTech</h2>
            <p className="mt-2 max-w-2xl text-sm text-purple-100 sm:text-base">
              Gestiona tus solicitudes, compara ofertas y adjudica tecnicos verificados desde un solo lugar.
            </p>
          </section>

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {statCards.map((card) => (
              <Card key={card.title} className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
                <CardHeader className="pb-2">
                  <CardDescription className="text-purple-200">{card.title}</CardDescription>
                  <CardTitle className="text-3xl">{card.value}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-purple-200">{card.detail}</p>
                </CardContent>
              </Card>
            ))}
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
              <CardHeader>
                <CardTitle className="text-white">Nueva subasta</CardTitle>
                <CardDescription className="text-purple-200">Publica una solicitud para recibir ofertas de tecnicos.</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="space-y-3" onSubmit={createAuction}>
                  <select
                    value={auctionForm.category}
                    onChange={(event) => setAuctionForm((current) => ({ ...current, category: event.target.value }))}
                    className={selectClass}
                    required
                  >
                    <option value="" className="text-slate-900">
                      Categoria
                    </option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id} className="text-slate-900">
                        {category.name}
                      </option>
                    ))}
                  </select>
                  <select
                    value={auctionForm.zone}
                    onChange={(event) => setAuctionForm((current) => ({ ...current, zone: event.target.value }))}
                    className={selectClass}
                  >
                    <option value="" className="text-slate-900">
                      Zona opcional
                    </option>
                    {zones.slice(0, 80).map((zone) => (
                      <option key={zone.id} value={zone.id} className="text-slate-900">
                        {zone.name}, {zone.city}
                      </option>
                    ))}
                  </select>
                  <input
                    value={auctionForm.title}
                    onChange={(event) => setAuctionForm((current) => ({ ...current, title: event.target.value }))}
                    className={`h-10 w-full rounded-md px-3 text-sm ${fieldClass}`}
                    placeholder="Titulo de la solicitud"
                    required
                  />
                  <textarea
                    value={auctionForm.description}
                    onChange={(event) => setAuctionForm((current) => ({ ...current, description: event.target.value }))}
                    className={`min-h-24 w-full rounded-md px-3 py-2 text-sm ${fieldClass}`}
                    placeholder="Describe el problema y condiciones."
                    required
                  />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      value={auctionForm.location}
                      onChange={(event) => setAuctionForm((current) => ({ ...current, location: event.target.value }))}
                      className={`h-10 w-full rounded-md px-3 text-sm ${fieldClass}`}
                      placeholder="Direccion o barrio"
                    />
                    <input
                      value={auctionForm.budgetMax}
                      onChange={(event) => setAuctionForm((current) => ({ ...current, budgetMax: event.target.value }))}
                      className={`h-10 w-full rounded-md px-3 text-sm ${fieldClass}`}
                      placeholder="Presupuesto maximo"
                      type="number"
                      min="0"
                    />
                  </div>
                  <Button className="w-full bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600" type="submit">
                    Crear subasta
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
              <CardHeader>
                <CardTitle className="text-white">Mis subastas</CardTitle>
                <CardDescription className="text-purple-200">Revisa ofertas y adjudica el tecnico ganador.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className={`text-sm ${message.includes("No se") || message.includes("Only") ? "text-rose-200" : "text-purple-100"}`}>{message}</p>
                {auctions.length === 0 ? (
                  <p className="text-sm text-purple-200">Aun no tienes subastas creadas.</p>
                ) : (
                  auctions.map((auction) => (
                    <div key={auction.id} className="rounded-xl border border-white/10 bg-white/[0.07] p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium text-white">{auction.title}</p>
                          <p className="text-sm text-purple-200">
                            {auction.category_name} - {auction.location || auction.zone_name || "Sin zona"}
                          </p>
                        </div>
                        <Badge className="border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">{auction.status}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-purple-100">{auction.description}</p>
                      <div className="mt-3 space-y-2">
                        {auction.bids.length === 0 ? (
                          <p className="text-sm text-purple-200">Sin ofertas todavia.</p>
                        ) : (
                          auction.bids.map((bid) => (
                            <div key={bid.id} className="flex flex-col gap-2 rounded-lg bg-slate-950/20 p-3 sm:flex-row sm:items-center sm:justify-between">
                              <div>
                                <p className="text-sm font-medium text-white">
                                  {bid.technician_name} - ${Number(bid.amount).toLocaleString("es-CO")}
                                </p>
                                <p className="text-xs text-purple-200">
                                  {bid.message || "Sin mensaje"} | {bid.estimated_minutes} min
                                </p>
                              </div>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white"
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
            <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
              <CardHeader>
                <CardTitle className="text-white">Actividad reciente</CardTitle>
                <CardDescription className="text-purple-200">Resumen de tus ultimas interacciones</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-purple-100">
                  {auctions.length === 0 ? "Aun no hay actividad registrada." : `Tienes ${auctions.length} solicitudes y ${receivedBids} ofertas recibidas.`}
                </p>
              </CardContent>
            </Card>
            <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
              <CardHeader>
                <CardTitle className="text-white">Proximos pasos</CardTitle>
                <CardDescription className="text-purple-200">Comienza a usar la plataforma</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-purple-100">
                <p>1. Completa tu perfil con telefono y direccion.</p>
                <p>2. Solicita un servicio tecnico desde Telegram o la web.</p>
                <p>3. Revisa ofertas y adjudica la mejor opcion.</p>
              </CardContent>
            </Card>
          </section>
        </main>
      </div>
      <MobileRoleNav />
    </div>
  );
}
