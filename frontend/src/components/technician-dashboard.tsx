"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CalendarClock,
  ClipboardList,
  Clock,
  Loader2,
  LogOut,
  MapPin,
  MessageCircle,
  Phone,
  Plus,
  RefreshCw,
  Scale,
  Trash2,
  UserRound,
  Wrench,
} from "lucide-react";

import { API_URL, Auction, Category, Dispute, OnboardingResponse, Rating, TechnicianLead, TechnicianService } from "@/lib/api";

type AuctionWithExpiry = Auction & { expires_at?: string | null };

function formatAuctionCountdown(remainingMs: number): string {
  const totalSeconds = Math.max(0, Math.floor(remainingMs / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function isAuctionVisible(auction: AuctionWithExpiry, nowMs: number): boolean {
  if (auction.status !== "open") {
    return false;
  }
  if (!auction.expires_at) {
    return true;
  }
  return new Date(auction.expires_at).getTime() > nowMs;
}

function AuctionCountdown({ expiresAt, nowMs }: { expiresAt: string; nowMs: number }) {
  const remainingMs = new Date(expiresAt).getTime() - nowMs;
  if (remainingMs <= 0) {
    return null;
  }
  return (
    <Badge className="border-orange-400/30 bg-orange-500/20 text-orange-100 hover:bg-orange-500/20">
      <Clock className="mr-1 size-3" />
      {formatAuctionCountdown(remainingMs)}
    </Badge>
  );
}
import { clearStoredAuth, restoreSession } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

type ApiState = "idle" | "loading" | "success" | "error";
type AppointmentStatus = NonNullable<TechnicianLead["appointment"]>["status"];

type ServiceForm = {
  categoryId: string;
  title: string;
  description: string;
  basePrice: string;
  isActive: boolean;
};

type BidDraft = {
  amount: string;
  message: string;
  serviceId: string;
  estimatedMinutes: string;
};

const emptyServiceForm: ServiceForm = {
  categoryId: "",
  title: "",
  description: "",
  basePrice: "",
  isActive: true,
};

const surfaceClass = "rounded-2xl border border-white/10 bg-white/5 shadow-2xl backdrop-blur-md";
const fieldClass = "border-white/20 bg-white/10 text-white placeholder:text-white/50";
const selectClass = "h-10 w-full rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white";

const leadStatusLabel: Record<TechnicianLead["status"], string> = {
  new: "Nuevo",
  contacted: "Contactado",
  accepted: "Aceptado",
  closed: "Cerrado",
};

const appointmentStatusLabel: Record<AppointmentStatus, string> = {
  pending: "Pendiente",
  confirmed: "Confirmada",
  cancelled: "Cancelada",
  rescheduled: "Reagendada",
  completed: "Completada",
  no_show: "No asistio",
};

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

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatTimeRange(start: string, end: string) {
  const formatter = new Intl.DateTimeFormat("es-CO", {
    hour: "numeric",
    minute: "2-digit",
  });
  return `${formatter.format(new Date(start))} - ${formatter.format(new Date(end))}`;
}

export function TechnicianDashboard() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [services, setServices] = useState<TechnicianService[]>([]);
  const [leads, setLeads] = useState<TechnicianLead[]>([]);
  const [auctions, setAuctions] = useState<Auction[]>([]);
  const [ratings, setRatings] = useState<Rating[]>([]);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [bidDrafts, setBidDrafts] = useState<Record<number, BidDraft>>({});
  const [serviceForm, setServiceForm] = useState<ServiceForm>(emptyServiceForm);
  const [status, setStatus] = useState<ApiState>("loading");
  const [message, setMessage] = useState("Cargando tu workspace tecnico...");
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [evidenceModalDisputeId, setEvidenceModalDisputeId] = useState<number | null>(null);
  const [evidenceModalNote, setEvidenceModalNote] = useState("");
  const [nowMs, setNowMs] = useState(() => Date.now());

  const authHeaders = useMemo(
    () => ({
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    }),
    [token],
  );

  function logout() {
    clearStoredAuth();
    router.replace("/login");
  }

  const loadWorkspace = useCallback(
    async (accessToken: string) => {
      if (!accessToken) {
        setMessage("Inicia sesion para cargar el workspace.");
        return;
      }

      setStatus("loading");
      try {
        const requestHeaders = {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        };
        const [onboardingResponse, categoryResponse, servicesResponse, leadsResponse, auctionsResponse, ratingsResponse, disputesResponse] = await Promise.all([
          fetch(`${API_URL}/technician/onboarding/`, { headers: requestHeaders, cache: "no-store" }),
          fetch(`${API_URL}/categories/`, { cache: "no-store" }),
          fetch(`${API_URL}/technician/services/`, { headers: requestHeaders, cache: "no-store" }),
          fetch(`${API_URL}/technician/leads/`, { headers: requestHeaders, cache: "no-store" }),
          fetch(`${API_URL}/auctions/`, { headers: requestHeaders, cache: "no-store" }),
          fetch(`${API_URL}/ratings/`, { headers: requestHeaders, cache: "no-store" }),
          fetch(`${API_URL}/disputes/`, { headers: requestHeaders, cache: "no-store" }),
        ]);

        if (
          !onboardingResponse.ok ||
          !categoryResponse.ok ||
          !servicesResponse.ok ||
          !leadsResponse.ok ||
          !auctionsResponse.ok ||
          !ratingsResponse.ok ||
          !disputesResponse.ok
        ) {
          throw new Error("Workspace request failed");
        }

        const onboarding = (await onboardingResponse.json()) as OnboardingResponse;
        if (!onboarding.onboarding_complete) {
          router.replace("/technician");
          return;
        }

        setCategories((await categoryResponse.json()) as Category[]);
        setServices((await servicesResponse.json()) as TechnicianService[]);
        setLeads((await leadsResponse.json()) as TechnicianLead[]);
        setAuctions((await auctionsResponse.json()) as Auction[]);
        setRatings((await ratingsResponse.json()) as Rating[]);
        setDisputes((await disputesResponse.json()) as Dispute[]);
        setStatus("success");
        setMessage("Workspace sincronizado.");
      } catch {
        setStatus("error");
        setMessage("No se pudo cargar el workspace tecnico.");
      }
    },
    [router],
  );

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
      if (session.user.role !== "technician") {
        router.replace("/dashboard");
        return;
      }
      setToken(session.accessToken);
      await loadWorkspace(session.accessToken);
    })();

    return () => {
      mounted = false;
    };
  }, [loadWorkspace, router]);

  useEffect(() => {
    if (!token) return;
    const interval = setInterval(() => void loadWorkspace(token), 30_000);
    return () => clearInterval(interval);
  }, [token, loadWorkspace]);

  useEffect(() => {
    const interval = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  async function submitService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      setMessage("Inicia sesion antes de crear servicios.");
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/technician/services/`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          category_id: Number(serviceForm.categoryId),
          title: serviceForm.title,
          description: serviceForm.description,
          base_price: serviceForm.basePrice,
          is_active: serviceForm.isActive,
        }),
      });
      if (!response.ok) {
        throw new Error("Service request failed");
      }
      setServiceForm(emptyServiceForm);
      await loadWorkspace(token);
      setStatus("success");
      setMessage("Servicio creado.");
    } catch {
      setStatus("error");
      setMessage("No se pudo crear el servicio.");
    }
  }

  // Lead status actions removed from the technician dashboard UI.

  async function notifyOnTheWay(appointmentId: number) {
    if (!token) return;
    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/appointments/${appointmentId}/on_the_way/`, {
        method: "POST",
        headers: authHeaders,
        cache: "no-store",
        body: JSON.stringify({}),
      });
      if (!response.ok) throw new Error("Request failed");
      await loadWorkspace(token);
      setStatus("success");
      setMessage("Cliente notificado: en camino.");
    } catch {
      setStatus("error");
      setMessage("No se pudo enviar la notificacion.");
    }
  }

  async function notifyArrived(appointmentId: number) {
    if (!token) return;
    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/appointments/${appointmentId}/arrived/`, {
        method: "POST",
        headers: authHeaders,
        cache: "no-store",
        body: JSON.stringify({}),
      });
      if (!response.ok) throw new Error("Request failed");
      await loadWorkspace(token);
      setStatus("success");
      setMessage("Cliente notificado: has llegado.");
    } catch {
      setStatus("error");
      setMessage("No se pudo enviar la notificacion.");
    }
  }

  async function completeAppointment(appointmentId: number) {
    if (!token) {
      setMessage("Inicia sesion antes de completar citas.");
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/appointments/${appointmentId}/complete/`, {
        method: "POST",
        headers: authHeaders,
        cache: "no-store",
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        throw new Error("Appointment complete request failed");
      }
      await loadWorkspace(token);
      setStatus("success");
      setMessage("Cita marcada como completada.");
    } catch {
      setStatus("error");
      setMessage("No se pudo completar la cita.");
    }
  }

  async function addDisputeEvidence(disputeId: number) {
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

    if (evidenceModalDisputeId === null) {
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/disputes/${evidenceModalDisputeId}/evidence/`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ note: evidenceModalNote.trim() }),
      });
      if (!response.ok) {
        throw new Error("Dispute evidence request failed");
      }
      await loadWorkspace(token);
      setStatus("success");
      setMessage("Evidencia agregada a la disputa.");
      setEvidenceModalOpen(false);
      setEvidenceModalDisputeId(null);
      setEvidenceModalNote("");
    } catch {
      setStatus("error");
      setMessage("No se pudo agregar la evidencia.");
    }
  }

  async function submitBid(auctionId: number) {
    if (!token) {
      setMessage("Inicia sesion antes de ofertar.");
      return;
    }
    const draft = bidDrafts[auctionId];
    if (!draft?.amount) {
      setMessage("Ingresa el valor de tu oferta.");
      return;
    }
    const minutes = Number(draft.estimatedMinutes);
    if (!Number.isFinite(minutes) || minutes < 1 || minutes > 480) {
      setMessage("Los minutos para llegar deben estar entre 1 y 480.");
      return;
    }
    const availableFrom = new Date(Date.now() + minutes * 60 * 1000).toISOString();

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/auction-bids/`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          auction: auctionId,
          service: draft.serviceId ? Number(draft.serviceId) : null,
          amount: draft.amount,
          message: draft.message,
          estimated_minutes: minutes,
          available_from: availableFrom,
        }),
      });
      if (!response.ok) {
        throw new Error("Bid request failed");
      }
      setBidDrafts((current) => ({ ...current, [auctionId]: { amount: "", message: "", serviceId: "", estimatedMinutes: "" } }));
      await loadWorkspace(token);
      setStatus("success");
      setMessage("Oferta enviada.");
    } catch {
      setStatus("error");
      setMessage("No se pudo enviar la oferta.");
    }
  }

  async function deleteService(serviceId: number) {
    if (!token) {
      setMessage("Inicia sesion antes de eliminar servicios.");
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/technician/services/${serviceId}/`, {
        method: "DELETE",
        headers: authHeaders,
      });
      if (!response.ok) {
        throw new Error("Delete request failed");
      }
      setServices((current) => current.filter((service) => service.id !== serviceId));
      setStatus("success");
      setMessage("Servicio eliminado.");
    } catch {
      setStatus("error");
      setMessage("No se pudo eliminar el servicio.");
    }
  }

  const isLoading = status === "loading";
  const scheduledLeads = leads.filter((lead) => lead.appointment !== null).length;
  const openAuctions = (auctions as AuctionWithExpiry[]).filter((auction) => isAuctionVisible(auction, nowMs));
  const activeDisputes = disputes.filter((dispute) => dispute.status !== "resolved");
  const receivedRatings = ratings.filter((rating) => rating.target_role === "technician");
  const averageRating = receivedRatings.length
    ? (receivedRatings.reduce((total, rating) => total + rating.score, 0) / receivedRatings.length).toFixed(1)
    : "0.0";

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-purple-900 to-slate-950 text-white">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-10 h-72 w-72 -translate-x-1/2 rounded-full bg-rose-500/20 blur-3xl" />
        <div className="absolute bottom-20 right-10 h-80 w-80 rounded-full bg-orange-400/10 blur-3xl" />
      </div>

      <main className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 pb-28 pt-6 sm:px-8 md:pb-10 lg:px-12">
        <header className={`${surfaceClass} p-6 md:p-8`}>
          <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
            <div>
              <Badge className="border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">Technician workspace</Badge>
              <h1 className="mt-4 text-3xl font-bold tracking-tight text-white sm:text-4xl">Dashboard tecnico</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-purple-100">
                Administra tus citas, leads y servicios desde el mismo espacio operativo.
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button
                variant="ghost"
                onClick={logout}
                disabled={isLoading}
                className="border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white"
              >
                <LogOut className="mr-2 size-4" />
                Cerrar sesion
              </Button>
            </div>
          </div>
        </header>

        <div className="grid gap-4 md:grid-cols-4">
          <div className={`${surfaceClass} p-5`}>
            <p className="text-sm text-purple-200">Citas asignadas</p>
            <p className="mt-2 text-3xl font-bold">{scheduledLeads}</p>
          </div>
          <div className={`${surfaceClass} p-5`}>
            <p className="text-sm text-purple-200">Leads recibidos</p>
            <p className="mt-2 text-3xl font-bold">{leads.length}</p>
          </div>
          <div className={`${surfaceClass} p-5`}>
            <p className="text-sm text-purple-200">Rating promedio</p>
            <p className="mt-2 text-3xl font-bold">{averageRating}</p>
            <p className="text-xs text-purple-200">{receivedRatings.length} reseñas</p>
          </div>
          <div className={`${surfaceClass} p-5`}>
            <p className="text-sm text-purple-200">Disputas abiertas</p>
            <p className="mt-2 text-3xl font-bold">{activeDisputes.length}</p>
          </div>
        </div>

        <p className={`text-sm ${status === "error" ? "text-rose-200" : "text-purple-100"}`}>{message}</p>

        <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
          <CardHeader>
            <CardTitle className="flex items-center gap-3 text-white">
              <span className="rounded-xl bg-white/10 p-2 text-orange-200">
                <ClipboardList className="size-5" />
              </span>
              Subastas abiertas
            </CardTitle>
            <CardDescription className="text-purple-200">
              Solicitudes de clientes donde puedes competir con una oferta.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Separator className="mb-5 bg-white/10" />
            <div className="grid gap-4">
              {openAuctions.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-5 text-center text-sm text-purple-100">
                  No hay subastas abiertas por ahora.
                </div>
              ) : (
                openAuctions.map((auction) => {
                  const draft = bidDrafts[auction.id] ?? { amount: "", message: "", serviceId: "", estimatedMinutes: "" };
                  const ownBid = auction.bids[0];
                  return (
                    <div key={auction.id} className="rounded-2xl border border-white/10 bg-white/[0.07] p-5 shadow-lg">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <p className="text-xs uppercase tracking-[0.24em] text-orange-200">Subasta #{auction.id}</p>
                          <h3 className="mt-2 text-xl font-semibold text-white">{auction.title}</h3>
                          <p className="mt-2 text-sm leading-6 text-purple-100">{auction.description}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge className="border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">{auction.category_name}</Badge>
                          <Badge className="border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">{auction.location || auction.zone_name || "Sin zona"}</Badge>
                          {(auction as AuctionWithExpiry).expires_at ? (
                            <AuctionCountdown expiresAt={(auction as AuctionWithExpiry).expires_at!} nowMs={nowMs} />
                          ) : null}
                        </div>
                      </div>

                      <div className="mt-4 grid gap-3 md:grid-cols-3">
                        <div className="space-y-2">
                          <Label htmlFor={`bid-amount-${auction.id}`} className="text-xs font-medium text-purple-100">
                            Valor de tu oferta
                          </Label>
                          <Input
                            id={`bid-amount-${auction.id}`}
                            type="number"
                            min="0"
                            step="1000"
                            value={draft.amount}
                            onChange={(event) =>
                              setBidDrafts((current) => ({ ...current, [auction.id]: { ...draft, amount: event.target.value } }))
                            }
                            placeholder="Valor oferta"
                            className={fieldClass}
                            disabled={Boolean(ownBid)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor={`bid-service-${auction.id}`} className="text-xs font-medium text-purple-100">
                            Servicio
                          </Label>
                          <select
                            id={`bid-service-${auction.id}`}
                            value={draft.serviceId}
                            onChange={(event) =>
                              setBidDrafts((current) => ({ ...current, [auction.id]: { ...draft, serviceId: event.target.value } }))
                            }
                            className={selectClass}
                            disabled={Boolean(ownBid)}
                          >
                            <option value="" className="text-slate-900">
                              Servicio opcional
                            </option>
                            {services.map((service) => (
                              <option key={service.id} value={service.id} className="text-slate-900">
                                {service.title}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs font-medium text-purple-100">
                            Minutos para llegar
                          </Label>
                          <Input
                            id={`arrival-minutes-${auction.id}`}
                            type="number"
                            min="1"
                            max="480"
                            value={draft.estimatedMinutes}
                            onChange={(event) =>
                              setBidDrafts((current) => ({ ...current, [auction.id]: { ...draft, estimatedMinutes: event.target.value } }))
                            }
                            placeholder="Minutos para llegar"
                            className={fieldClass}
                            disabled={Boolean(ownBid)}
                          />
                        </div>
                      </div>
                      <Textarea
                        value={draft.message}
                        onChange={(event) =>
                          setBidDrafts((current) => ({ ...current, [auction.id]: { ...draft, message: event.target.value } }))
                        }
                        className="mt-3 border-white/20 bg-white/10 text-white placeholder:text-white/50"
                        placeholder="Mensaje para el cliente."
                        disabled={Boolean(ownBid)}
                      />
                      <Button
                        className="mt-3 bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600"
                        onClick={() => void submitBid(auction.id)}
                        disabled={isLoading || Boolean(ownBid)}
                      >
                        {ownBid ? "Oferta enviada" : "Enviar oferta"}
                      </Button>
                    </div>
                  );
                })
              )}
            </div>
          </CardContent>
        </Card>

        <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
          <CardHeader>
            <CardTitle className="flex items-center gap-3 text-white">
              <span className="rounded-xl bg-gradient-to-br from-orange-400 to-rose-500 p-2 text-white">
                <ClipboardList className="size-5" />
              </span>
              Leads recibidos
            </CardTitle>
            <CardDescription className="text-purple-200">
              Cuando un cliente te escoge en el chatbot y agenda, aqui veras la card de la cita.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Separator className="mb-5 bg-white/10" />
            <div className="grid gap-4">
              {leads.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-5 text-center text-sm text-purple-100">
                  Aun no tienes leads asignados.
                </div>
              ) : (
                leads.map((lead) => {
                  const appointment = lead.appointment;
                  return (
                    <div key={lead.id} className="rounded-2xl border border-white/10 bg-white/[0.07] p-5 shadow-lg">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <p className="text-xs uppercase tracking-[0.24em] text-orange-200">
                            {appointment ? `Cita #${appointment.id}` : `Lead #${lead.id}`}
                          </p>
                          <h3 className="mt-2 text-xl font-semibold text-white">
                            {appointment?.service_title || lead.service_title || "Servicio tecnico"}
                          </h3>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge className="border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">
                            {leadStatusLabel[lead.status]}
                          </Badge>
                          {appointment ? (
                            <Badge className="bg-gradient-to-r from-orange-400 to-rose-500 text-white hover:from-orange-400 hover:to-rose-500">
                              {appointmentStatusLabel[appointment.status]}
                            </Badge>
                          ) : null}
                        </div>
                      </div>

                      <div className="mt-5 grid gap-3 md:grid-cols-2">
                        {appointment ? (
                          <div className="rounded-xl border border-white/10 bg-slate-950/20 p-4">
                            <div className="flex items-center gap-2 text-sm text-orange-100">
                              <CalendarClock className="size-4" />
                              Horario
                            </div>
                            <p className="mt-2 font-semibold text-white">{formatDateTime(appointment.scheduled_start)}</p>
                            <p className="text-sm text-purple-200">
                              {formatTimeRange(appointment.scheduled_start, appointment.scheduled_end)}
                            </p>
                          </div>
                        ) : null}

                        <div className="rounded-xl border border-white/10 bg-slate-950/20 p-4">
                          <div className="flex items-center gap-2 text-sm text-orange-100">
                            <UserRound className="size-4" />
                            Cliente
                          </div>
                          <p className="mt-2 font-semibold text-white">
                            {lead.client_name || appointment?.client_username || "Cliente sin nombre"}
                          </p>
                          <p className="text-sm text-purple-200">{lead.client_phone}</p>
                        </div>

                        <div className="rounded-xl border border-white/10 bg-slate-950/20 p-4">
                          <div className="flex items-center gap-2 text-sm text-orange-100">
                            <MapPin className="size-4" />
                            Direccion / zona
                          </div>
                          <p className="mt-2 text-sm text-purple-100">
                            {appointment?.client_address || appointment?.location || lead.location || "Sin direccion registrada"}
                          </p>
                        </div>

                        <div className="rounded-xl border border-white/10 bg-slate-950/20 p-4">
                          <div className="flex items-center gap-2 text-sm text-orange-100">
                            <Phone className="size-4" />
                            Contacto
                          </div>
                          <p className="mt-2 text-sm text-purple-100">{lead.source} | Urgencia: {lead.urgency || "normal"}</p>
                        </div>
                      </div>

                      <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/20 p-4">
                        <div className="flex items-center gap-2 text-sm text-orange-100">
                          <MessageCircle className="size-4" />
                          Solicitud del cliente
                        </div>
                        <p className="mt-2 text-sm leading-6 text-purple-100">{appointment?.request_text || lead.message}</p>
                      </div>

                      {appointment && ["pending", "confirmed", "rescheduled"].includes(appointment.status) ? (
                        <div className="mt-4 flex justify-end gap-2">
                          {appointment.technician_status !== "on_the_way" && appointment.technician_status !== "arrived" ? (
                            <Button
                              size="sm"
                              className="bg-gradient-to-r from-blue-500 to-indigo-600 font-semibold text-white hover:from-blue-600 hover:to-indigo-700"
                              onClick={() => void notifyOnTheWay(appointment.id)}
                              disabled={isLoading}
                            >
                              En camino
                            </Button>
                          ) : null}
                          {appointment.technician_status === "on_the_way" ? (
                            <Button
                              size="sm"
                              className="bg-gradient-to-r from-violet-500 to-purple-600 font-semibold text-white hover:from-violet-600 hover:to-purple-700"
                              onClick={() => void notifyArrived(appointment.id)}
                              disabled={isLoading}
                            >
                              He llegado
                            </Button>
                          ) : null}
                          {appointment ? (
                            <Button
                              size="sm"
                              className="bg-gradient-to-r from-emerald-400 to-teal-500 font-semibold text-white hover:from-emerald-500 hover:to-teal-600"
                              onClick={() => void completeAppointment(appointment.id)}
                              disabled={isLoading || appointment.status === "completed"}
                            >
                              Completar cita
                            </Button>
                          ) : null}
                        </div>
                      ) : null}

                    </div>
                  );
                })
              )}
            </div>
          </CardContent>
        </Card>

        <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
          <CardHeader>
            <CardTitle className="flex items-center gap-3 text-white">
              <span className="rounded-xl bg-white/10 p-2 text-amber-300">
                <Scale className="size-5" />
              </span>
              Disputas activas
            </CardTitle>
            <CardDescription className="text-purple-200">
              Reporte de disputas abiertas o en revisión.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Separator className="mb-5 bg-white/10" />
            <div className="grid gap-4">
              {activeDisputes.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-5 text-center text-sm text-purple-100">
                  No tienes disputas activas.
                </div>
              ) : (
                activeDisputes.map((dispute) => (
                  <div key={dispute.id} className="rounded-2xl border border-white/10 bg-white/[0.07] p-5 shadow-lg">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-xs uppercase tracking-[0.24em] text-orange-200">Disputa #{dispute.id}</p>
                        {dispute.description && (
                          <h3 className="mt-2 text-xl font-semibold text-white">{dispute.description}</h3>
                        )}
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
                    <div className="mt-4 flex justify-end">
                      <Button
                        size="sm"
                        className="bg-gradient-to-r from-amber-500 to-orange-500 font-semibold text-white hover:from-amber-600 hover:to-orange-600"
                        onClick={() => void addDisputeEvidence(dispute.id)}
                      >
                        <MessageCircle className="mr-2 size-4" />
                        Agregar evidencia
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-white/10 p-2 text-orange-200">
                <Wrench className="size-5" />
              </div>
              <div>
                <CardTitle className="text-white">Nuevo servicio</CardTitle>
                <CardDescription className="text-purple-200">Estos servicios aparecen en las recomendaciones.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={submitService}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="category" className="text-white">
                    Categoria
                  </Label>
                  <select
                    id="category"
                    value={serviceForm.categoryId}
                    onChange={(event) => setServiceForm((current) => ({ ...current, categoryId: event.target.value }))}
                    className={selectClass}
                    required
                  >
                    <option value="" className="text-slate-900">
                      Selecciona categoria
                    </option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id} className="text-slate-900">
                        {category.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="price" className="text-white">
                    Precio base
                  </Label>
                  <Input
                    id="price"
                    min="0"
                    step="1000"
                    type="number"
                    value={serviceForm.basePrice}
                    onChange={(event) => setServiceForm((current) => ({ ...current, basePrice: event.target.value }))}
                    placeholder="80000"
                    className={fieldClass}
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="title" className="text-white">
                  Titulo
                </Label>
                <Input
                  id="title"
                  value={serviceForm.title}
                  onChange={(event) => setServiceForm((current) => ({ ...current, title: event.target.value }))}
                  placeholder="Instalacion electrica residencial"
                  className={fieldClass}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description" className="text-white">
                  Descripcion
                </Label>
                <Textarea
                  id="description"
                  value={serviceForm.description}
                  onChange={(event) => setServiceForm((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Describe alcance, condiciones y tipo de trabajos."
                  className={fieldClass}
                  required
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-purple-100">
                <input
                  checked={serviceForm.isActive}
                  onChange={(event) => setServiceForm((current) => ({ ...current, isActive: event.target.checked }))}
                  type="checkbox"
                  className="accent-rose-500"
                />
                Servicio activo
              </label>
              <Button
                type="submit"
                disabled={isLoading}
                className="w-full bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600"
              >
                <Plus className="mr-2 size-4" />
                Crear servicio
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
          <CardHeader>
            <CardTitle className="text-white">Servicios publicados</CardTitle>
            <CardDescription className="text-purple-200">Catalogo del tecnico autenticado.</CardDescription>
          </CardHeader>
          <CardContent>
            <Separator className="mb-4 bg-white/10" />
            <div className="grid gap-3 md:hidden">
              {services.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-center text-sm text-purple-100">
                  Todavia no hay servicios cargados.
                </div>
              ) : (
                services.map((service) => (
                  <div key={service.id} className="rounded-2xl border border-white/10 bg-white/[0.07] p-4 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium text-white">{service.title}</p>
                        <p className="mt-1 text-sm text-purple-200">{service.category.name}</p>
                      </div>
                      <Badge className="border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">
                        {service.is_active ? "Activo" : "Inactivo"}
                      </Badge>
                    </div>
                    <p className="mt-3 line-clamp-2 text-sm text-purple-100">{service.description}</p>
                    <div className="mt-4 flex items-center justify-between gap-3">
                      <span className="text-sm font-semibold text-white">${Number(service.base_price).toLocaleString("es-CO")}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white"
                        onClick={() => void deleteService(service.id)}
                      >
                        <Trash2 className="mr-2 size-4" />
                        Eliminar
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <Table>
                <TableHeader>
                  <TableRow className="border-white/10 hover:bg-white/5">
                    <TableHead className="text-purple-100">Servicio</TableHead>
                    <TableHead className="text-purple-100">Categoria</TableHead>
                    <TableHead className="text-purple-100">Precio base</TableHead>
                    <TableHead className="text-purple-100">Estado</TableHead>
                    <TableHead className="text-right text-purple-100">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {services.length === 0 ? (
                    <TableRow className="border-white/10 hover:bg-white/5">
                      <TableCell colSpan={5} className="text-center text-purple-100">
                        Todavia no hay servicios cargados.
                      </TableCell>
                    </TableRow>
                  ) : (
                    services.map((service) => (
                      <TableRow key={service.id} className="border-white/10 hover:bg-white/5">
                        <TableCell>
                          <p className="font-medium text-white">{service.title}</p>
                          <p className="line-clamp-1 text-sm text-purple-200">{service.description}</p>
                        </TableCell>
                        <TableCell className="text-purple-100">{service.category.name}</TableCell>
                        <TableCell className="text-purple-100">${Number(service.base_price).toLocaleString("es-CO")}</TableCell>
                        <TableCell>
                          <Badge className="border-white/10 bg-white/10 text-purple-100 hover:bg-white/10">
                            {service.is_active ? "Activo" : "Inactivo"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-purple-100 hover:bg-white/10 hover:text-white"
                            onClick={() => void deleteService(service.id)}
                          >
                            <Trash2 className="size-4" />
                            <span className="sr-only">Eliminar</span>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

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
                    disabled={isLoading || !evidenceModalNote.trim()}
                    className="flex-1 bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600"
                  >
                    Enviar evidencia
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
