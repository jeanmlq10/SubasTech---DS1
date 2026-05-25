"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Calendar, ClipboardList, LayoutDashboard, LogOut, MessageCircle, Settings, User } from "lucide-react";

import { API_URL, Appointment, Auction, Category, Dispute, Rating, Zone } from "@/lib/api";
import { clearStoredAuth, restoreSession, roleHome } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";

const sidebarLinks = [
  { href: "#overview", label: "Resumen", icon: LayoutDashboard },
  { href: "#requests", label: "Solicitudes", icon: ClipboardList },
  { href: "#appointments", label: "Citas", icon: Calendar },
  { href: "#activity", label: "Mensajes", icon: MessageCircle },
  { href: "#profile", label: "Perfil", icon: User },
  { href: "#settings", label: "Ajustes", icon: Settings },
];

const surfaceClass = "rounded-2xl border border-white/10 bg-white/5 shadow-2xl backdrop-blur-md";
const fieldClass = "border-white/20 bg-white/10 text-white placeholder:text-white/50";
const selectClass = "h-10 w-full rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white";
const disputeStatusLabel: Record<Dispute["status"], string> = {
  open: "Abierta",
  in_review: "En revision",
  resolved: "Resuelta",
  rejected: "Rechazada",
};

const disputeDecisionLabel: Record<Dispute["decision"], string> = {
  pending: "Pendiente",
  favor_client: "A favor del cliente",
  favor_technician: "A favor del tecnico",
  partial: "Resolucion parcial",
};

export function ClientDashboard() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [token, setToken] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [auctions, setAuctions] = useState<Auction[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [ratings, setRatings] = useState<Rating[]>([]);
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
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [evidenceModalDisputeId, setEvidenceModalDisputeId] = useState<number | null>(null);
  const [evidenceModalNote, setEvidenceModalNote] = useState("");
  const [disputeModalOpen, setDisputeModalOpen] = useState(false);
  const [disputeModalAppointment, setDisputeModalAppointment] = useState<Appointment | null>(null);
  const [disputeModalReason, setDisputeModalReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  useEffect(() => {
    if (!token) return;
    const interval = setInterval(() => void loadClientData(token), 30_000);
    return () => clearInterval(interval);
  }, [token]);

  useEffect(() => {
    if (isBooting || appointments.length === 0) return;
    const params = new URLSearchParams(window.location.search);
    const rateId = params.get("rate");
    if (!rateId) return;
    const appointment = appointments.find(
      (a) => a.id === parseInt(rateId, 10) && a.status === "completed",
    );
    if (appointment) {
      void rateAppointment(appointment);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isBooting, appointments]);

  async function loadClientData(accessToken: string) {
    try {
      const [categoryResponse, zoneResponse, auctionResponse, appointmentResponse, disputeResponse, ratingResponse] = await Promise.all([
        fetch(`${API_URL}/categories/`),
        fetch(`${API_URL}/zones/`),
        fetch(`${API_URL}/auctions/`, { headers: { Authorization: `Bearer ${accessToken}` } }),
        fetch(`${API_URL}/appointments/`, { headers: { Authorization: `Bearer ${accessToken}` } }),
        fetch(`${API_URL}/disputes/`, { headers: { Authorization: `Bearer ${accessToken}` } }),
        fetch(`${API_URL}/ratings/`, { headers: { Authorization: `Bearer ${accessToken}` } }),
      ]);
      if (!categoryResponse.ok || !zoneResponse.ok || !auctionResponse.ok || !appointmentResponse.ok || !disputeResponse.ok || !ratingResponse.ok) {
        throw new Error("Client data request failed");
      }
      setCategories((await categoryResponse.json()) as Category[]);
      setZones((await zoneResponse.json()) as Zone[]);
      const allAuctions = (await auctionResponse.json()) as Auction[];
      setAuctions(allAuctions.filter(a => !a.expires_at || new Date(a.expires_at) > new Date()));
      setAppointments((await appointmentResponse.json()) as Appointment[]);
      setDisputes((await disputeResponse.json()) as Dispute[]);
      setRatings((await ratingResponse.json()) as Rating[]);
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

  async function cancelAuction(auctionId: number) {
    if (!token) {
      setMessage("Inicia sesion antes de cancelar.");
      return;
    }
    if (!window.confirm("¿Cancelar esta subasta? Se rechazaran todas las ofertas pendientes.")) return;
    try {
      const response = await fetch(`${API_URL}/auctions/${auctionId}/cancel/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) throw new Error("No se pudo cancelar la subasta.");
      await loadClientData(token);
      setMessage("Subasta cancelada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo cancelar la subasta.");
    }
  }

  async function cancelAppointment(appointmentId: number) {
    if (!token) {
      setMessage("Inicia sesion antes de cancelar.");
      return;
    }
    const reason = window.prompt("Motivo de cancelacion (opcional):", "") ?? "";
    try {
      const response = await fetch(`${API_URL}/appointments/${appointmentId}/cancel/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ cancellation_reason: reason }),
      });
      if (!response.ok) throw new Error("No se pudo cancelar la cita.");
      await loadClientData(token);
      setMessage("Cita cancelada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo cancelar la cita.");
    }
  }

  async function confirmAppointmentComplete(appointmentId: number) {
    if (!token) {
      setMessage("Inicia sesion antes de confirmar una cita.");
      return;
    }

    try {
      const response = await fetch(`${API_URL}/appointments/${appointmentId}/confirm_complete/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        throw new Error("No se pudo confirmar la cita.");
      }
      await loadClientData(token);
      setMessage("Cita confirmada como completada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo confirmar la cita.");
    }
  }

  function openAppointmentDispute(appointment: Appointment) {
    if (!token) {
      setMessage("Inicia sesion antes de abrir una disputa.");
      return;
    }
    setDisputeModalAppointment(appointment);
    setDisputeModalReason("");
    setDisputeModalOpen(true);
  }

  async function submitAppointmentDispute() {
    if (!disputeModalReason.trim()) {
      setMessage("Describe el problema con la cita.");
      return;
    }

    if (!disputeModalAppointment || !token) {
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/disputes/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          technician: disputeModalAppointment.technician,
          service: disputeModalAppointment.service,
          title: `Disputa por cita #${disputeModalAppointment.id}`,
          description: disputeModalReason.trim(),
          priority: "normal",
        }),
      });
      if (!response.ok) {
        throw new Error("No se pudo abrir la disputa.");
      }
      await loadClientData(token);
      setMessage("Disputa abierta. Un arbitro revisara el caso.");
      setDisputeModalOpen(false);
      setDisputeModalAppointment(null);
      setDisputeModalReason("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo abrir la disputa.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function addDisputeEvidence(disputeId: number) {
    if (!token) {
      setMessage("Inicia sesion antes de aportar evidencia.");
      return;
    }
    setEvidenceModalDisputeId(disputeId);
    setEvidenceModalNote("");
    setEvidenceModalOpen(true);
  }

  async function submitDisputeEvidence() {
    if (!evidenceModalNote.trim()) {
      setMessage("La evidencia no puede estar vacía.");
      return;
    }

    if (evidenceModalDisputeId === null || !token) {
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_URL}/disputes/${evidenceModalDisputeId}/evidence/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ note: evidenceModalNote.trim() }),
      });
      if (!response.ok) {
        throw new Error("No se pudo agregar la evidencia.");
      }
      await loadClientData(token);
      setMessage("Evidencia agregada a la disputa.");
      setEvidenceModalOpen(false);
      setEvidenceModalDisputeId(null);
      setEvidenceModalNote("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo agregar la evidencia.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function rateAppointment(appointment: Appointment) {
    if (!token) {
      setMessage("Inicia sesion antes de calificar.");
      return;
    }

    const scoreValue = window.prompt("Califica el servicio de 1 a 5.", "5");
    const score = Number(scoreValue);
    if (!Number.isInteger(score) || score < 1 || score > 5) {
      setMessage("La calificacion debe ser un numero entre 1 y 5.");
      return;
    }
    const comment = window.prompt("Comentario opcional para el tecnico.", "") ?? "";

    try {
      const response = await fetch(`${API_URL}/ratings/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          target_role: "technician",
          technician: appointment.technician,
          service: appointment.service,
          lead: appointment.lead,
          score,
          comment,
        }),
      });
      if (!response.ok) {
        throw new Error("No se pudo guardar la calificacion.");
      }
      await loadClientData(token);
      setMessage("Calificacion registrada.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo guardar la calificacion.");
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
  const activeAppointments = appointments.filter((appointment) => ["pending", "confirmed", "rescheduled"].includes(appointment.status));
  const completedAppointments = appointments.filter((appointment) => appointment.status === "completed");
  const ratedLeadIds = new Set(ratings.filter((rating) => rating.target_role === "technician" && rating.lead).map((rating) => rating.lead));
  const ratedServiceIds = new Set(ratings.filter((rating) => rating.target_role === "technician" && !rating.lead && rating.service).map((rating) => rating.service));
  const statCards = [
    { title: "Solicitudes activas", value: String(openAuctions.length), detail: `${auctions.length} solicitudes totales` },
    { title: "Citas activas", value: String(activeAppointments.length), detail: `${completedAppointments.length} completadas` },
    { title: "Ofertas recibidas", value: String(receivedBids), detail: "de tecnicos verificados" },
    { title: "Disputas abiertas", value: String(disputes.filter((dispute) => dispute.status !== "resolved").length), detail: `${closedAuctions + awardedAuctions.length} solicitudes cerradas/adjudicadas` },
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
              const active = link.href === "#overview";
              return (
                <a
                  key={link.label}
                  href={link.href}
                  className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors ${
                    active ? "bg-gradient-to-r from-orange-400 to-rose-500 text-white" : "text-purple-100 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  <Icon className="size-4" />
                  {link.label}
                </a>
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
          <section id="overview" className={`${surfaceClass} scroll-mt-6 p-6 md:p-8`}>
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

          <section id="requests" className="grid scroll-mt-6 gap-4 lg:grid-cols-2">
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
                                Aceptar
                              </Button>
                            </div>
                          ))
                        )}
                      </div>
                      {auction.status === "open" ? (
                        <div className="mt-3">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="border border-rose-500/30 text-rose-300 hover:bg-rose-500/10 hover:text-rose-200"
                            onClick={() => void cancelAuction(auction.id)}
                          >
                            Cancelar subasta
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </section>

          <Card id="appointments" className={`${surfaceClass} scroll-mt-6 border-white/10 bg-white/5 text-white`}>
            <CardHeader>
              <CardTitle className="text-white">Mis citas</CardTitle>
              <CardDescription className="text-purple-200">Confirma servicios completados o abre una disputa si algo salio mal.</CardDescription>
            </CardHeader>
            <CardContent>
              <Separator className="mb-4 bg-white/10" />
              <div className="grid gap-3">
                {appointments.length === 0 ? (
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-purple-200">Aun no tienes citas creadas.</div>
                ) : (
                  appointments.map((appointment) => (
                    <div key={appointment.id} className="rounded-2xl border border-white/10 bg-white/[0.07] p-4">
                      {(() => {
                        const alreadyRated = appointment.lead
                          ? ratedLeadIds.has(appointment.lead)
                          : appointment.service
                            ? ratedServiceIds.has(appointment.service)
                            : false;
                        return (
                          <>
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <p className="text-xs uppercase tracking-[0.24em] text-orange-200">Cita #{appointment.id}</p>
                          <h3 className="mt-2 font-semibold text-white">{appointment.service_title || "Servicio tecnico"}</h3>
                          <p className="mt-1 text-sm text-purple-200">Tecnico: {appointment.technician_name}</p>
                          <p className="mt-1 text-sm text-purple-200">
                            {new Date(appointment.scheduled_start).toLocaleString("es-CO")} - {new Date(appointment.scheduled_end).toLocaleTimeString("es-CO", { hour: "numeric", minute: "2-digit" })}
                          </p>
                        </div>
                        <Badge className="border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">{appointment.status}</Badge>
                      </div>
                      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                        <Button
                          size="sm"
                          className="bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600"
                          disabled={!["pending", "confirmed", "rescheduled"].includes(appointment.status)}
                          onClick={() => void confirmAppointmentComplete(appointment.id)}
                        >
                          Confirmar completado
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white"
                          disabled={appointment.status === "cancelled" || appointment.status === "no_show"}
                          onClick={() => void openAppointmentDispute(appointment)}
                        >
                          Abrir disputa
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white"
                          disabled={appointment.status !== "completed" || alreadyRated}
                          onClick={() => void rateAppointment(appointment)}
                        >
                          {alreadyRated ? "Calificado" : "Calificar"}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="border border-rose-500/30 text-rose-300 hover:bg-rose-500/10 hover:text-rose-200"
                          disabled={!["pending", "confirmed", "rescheduled"].includes(appointment.status)}
                          onClick={() => void cancelAppointment(appointment.id)}
                        >
                          Cancelar
                        </Button>
                      </div>
                          </>
                        );
                      })()}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
            <CardHeader>
              <CardTitle className="text-white">Mis disputas</CardTitle>
              <CardDescription className="text-purple-200">Consulta el estado del caso y agrega notas para el arbitro.</CardDescription>
            </CardHeader>
            <CardContent>
              <Separator className="mb-4 bg-white/10" />
              <div className="grid gap-3">
                {disputes.length === 0 ? (
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-purple-200">Aun no tienes disputas abiertas.</div>
                ) : (
                  disputes.map((dispute) => (
                    <div key={dispute.id} className="rounded-2xl border border-white/10 bg-white/[0.07] p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <p className="text-xs uppercase tracking-[0.24em] text-orange-200">Disputa #{dispute.id}</p>
                          <h3 className="mt-2 font-semibold text-white">{dispute.title}</h3>
                          <p className="mt-1 text-sm text-purple-100">{dispute.description}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge className="border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">
                            {disputeStatusLabel[dispute.status]}
                          </Badge>
                          <Badge className="border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">
                            {disputeDecisionLabel[dispute.decision]}
                          </Badge>
                        </div>
                      </div>
                      {dispute.ai_summary ? <p className="mt-3 text-sm text-purple-200">Resumen IA: {dispute.ai_summary}</p> : null}
                      {dispute.arbiter_notes ? <p className="mt-3 text-sm text-orange-100">Decision arbitro: {dispute.arbiter_notes}</p> : null}
                      <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/20 p-3">
                        <p className="text-sm font-medium text-white">Evidencia registrada</p>
                        {dispute.evidence.length === 0 ? (
                          <p className="mt-2 text-sm text-purple-200">Sin evidencia adicional.</p>
                        ) : (
                          <div className="mt-2 grid gap-2">
                            {dispute.evidence.map((item) => (
                              <p key={item.id} className="rounded-lg bg-white/5 p-2 text-sm text-purple-100">
                                {item.note || "Archivo adjunto"}
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="mt-4 border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white"
                        disabled={dispute.status === "resolved"}
                        onClick={() => void addDisputeEvidence(dispute.id)}
                      >
                        Agregar evidencia
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <section className="grid gap-4 lg:grid-cols-2">
            <Card id="activity" className={`${surfaceClass} scroll-mt-6 border-white/10 bg-white/5 text-white`}>
              <CardHeader>
                <CardTitle className="text-white">Mensajes y actividad</CardTitle>
                <CardDescription className="text-purple-200">Resumen de tus ultimas interacciones</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-purple-100">
                  {auctions.length === 0 ? "Aun no hay actividad registrada." : `Tienes ${auctions.length} solicitudes y ${receivedBids} ofertas recibidas.`}
                </p>
              </CardContent>
            </Card>
            <Card id="profile" className={`${surfaceClass} scroll-mt-6 border-white/10 bg-white/5 text-white`}>
              <CardHeader>
                <CardTitle className="text-white">Perfil</CardTitle>
                <CardDescription className="text-purple-200">Datos basicos de tu cuenta cliente</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-purple-100">
                <p>Usuario: {username || "Cliente"}</p>
                <p>Desde aqui centralizas tus solicitudes creadas por Telegram y dashboard.</p>
              </CardContent>
            </Card>
            <Card id="settings" className={`${surfaceClass} scroll-mt-6 border-white/10 bg-white/5 text-white`}>
              <CardHeader>
                <CardTitle className="text-white">Ajustes</CardTitle>
                <CardDescription className="text-purple-200">Acciones rapidas de la sesion</CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="ghost" className="border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white" onClick={logout}>
                  <LogOut className="mr-2 size-4" />
                  Cerrar sesion
                </Button>
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

        {/* Evidence Modal */}
        {evidenceModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div
              className={`${surfaceClass} w-full max-w-md transform transition-all duration-200 ${
                evidenceModalOpen ? "scale-100 opacity-100" : "scale-95 opacity-0"
              }`}
            >
              <div className="space-y-4 p-6">
                <h2 className="text-lg font-bold text-white">Agregar evidencia</h2>
                <p className="text-sm text-purple-100">
                  Escribe una nota o evidencia textual para el árbitro.
                </p>
                <Textarea
                  value={evidenceModalNote}
                  onChange={(e) => setEvidenceModalNote(e.target.value)}
                  placeholder="Describe los detalles de tu evidencia..."
                  className={fieldClass}
                  rows={5}
                />
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setEvidenceModalOpen(false);
                      setEvidenceModalDisputeId(null);
                      setEvidenceModalNote("");
                    }}
                    className="flex-1 border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white"
                  >
                    Cancelar
                  </Button>
                  <Button
                    onClick={() => void submitDisputeEvidence()}
                    disabled={isSubmitting || !evidenceModalNote.trim()}
                    className="flex-1 bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600"
                  >
                    Enviar evidencia
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Dispute Modal */}
        {disputeModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div
              className={`${surfaceClass} w-full max-w-md transform transition-all duration-200 ${
                disputeModalOpen ? "scale-100 opacity-100" : "scale-95 opacity-0"
              }`}
            >
              <div className="space-y-4 p-6">
                <h2 className="text-lg font-bold text-white">Abrir disputa</h2>
                <p className="text-sm text-purple-100">
                  {disputeModalAppointment
                    ? `Describe brevemente el problema con la cita #${disputeModalAppointment.id}.`
                    : "Describe brevemente el problema con esta cita."}
                </p>
                <Textarea
                  value={disputeModalReason}
                  onChange={(e) => setDisputeModalReason(e.target.value)}
                  placeholder="Explica qué ocurrió con el servicio..."
                  className={fieldClass}
                  rows={5}
                />
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setDisputeModalOpen(false);
                      setDisputeModalAppointment(null);
                      setDisputeModalReason("");
                    }}
                    className="flex-1 border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white"
                  >
                    Cancelar
                  </Button>
                  <Button
                    onClick={() => void submitAppointmentDispute()}
                    disabled={isSubmitting || !disputeModalReason.trim()}
                    className="flex-1 bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600"
                  >
                    Abrir disputa
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
        </main>
      </div>
    </div>
  );
}
