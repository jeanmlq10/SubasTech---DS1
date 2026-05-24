"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Bot, CheckCircle2, ClipboardCheck, LogOut, Scale } from "lucide-react";

import { clearStoredAuth, restoreSession } from "@/lib/auth";
import { API_URL, ArbiterDispute, ArbiterQueue } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

type ApiState = "idle" | "loading" | "success" | "error";

const emptyQueue: ArbiterQueue = {
  metrics: { open: 0, in_review: 0, resolved_by_me: 0, high_priority: 0 },
  by_status: {},
  disputes: [],
};

const surfaceClass = "rounded-2xl border border-white/10 bg-white/5 shadow-2xl backdrop-blur-md";
const fieldClass = "border-white/20 bg-white/10 text-white placeholder:text-white/50";
const selectClass = "h-10 w-full rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white";
const badgeClass = "border-white/10 bg-white/10 text-purple-100 hover:bg-white/10";
const ghostButtonClass = "border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white";
const primaryButtonClass = "bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600";
const disputeStatusLabel: Record<string, string> = {
  open: "Abierta",
  in_review: "En revisión",
  resolved: "Resuelta",
  rejected: "Rechazada",
};

export function ArbiterDashboard() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [queue, setQueue] = useState<ArbiterQueue>(emptyQueue);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [decision, setDecision] = useState("favor_client");
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState<ApiState>("loading");
  const [message, setMessage] = useState("Cargando panel de arbitraje...");

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
      const validRoles = ["arbiter", "admin", "staff"];
      if (!validRoles.includes(session.user.role)) {
        router.replace("/login");
        return;
      }
      setToken(session.accessToken);
      setMessage(`Sesion activa como ${session.user.username} (${session.user.role}).`);
      await loadQueue(session.accessToken);
    })();

    return () => {
      mounted = false;
    };
  }, [router]);

  useEffect(() => {
    if (!token) return;
    const interval = setInterval(() => void loadQueue(), 30_000);
    return () => clearInterval(interval);
  }, [token]);

  function logout() {
    clearStoredAuth();
    setToken("");
    router.replace("/login");
  }

  const selectedDispute = useMemo(
    () => queue.disputes.find((dispute) => dispute.id === selectedId) ?? queue.disputes[0] ?? null,
    [queue.disputes, selectedId],
  );

  async function loadQueue(accessToken?: string) {
    const tokenToUse = accessToken || token;
    if (!tokenToUse) {
      setMessage("No token available. Please log in again.");
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/arbiter/queue/`, {
        headers: { Authorization: `Bearer ${tokenToUse}` },
      });
      if (!response.ok) {
        throw new Error("Arbiter queue request failed");
      }
      const data = (await response.json()) as ArbiterQueue;
      setQueue(data);
      setSelectedId((current) => current ?? data.disputes[0]?.id ?? null);
      setStatus("success");
      setMessage("Arbiter queue loaded.");
    } catch {
      setStatus("error");
      setMessage("Could not load arbiter queue. Check that the token belongs to an arbiter or admin.");
    }
  }

  async function claimDispute(disputeId: number) {
    await mutateDispute(`${API_URL}/arbiter/disputes/${disputeId}/claim/`, {});
  }

  async function submitDecision(disputeId: number) {
    await mutateDispute(`${API_URL}/arbiter/disputes/${disputeId}/decision/`, { decision, notes });
    setNotes("");
  }

  async function mutateDispute(url: string, payload: Record<string, string>) {
    if (!token) {
      setMessage("Add an arbiter JWT token first.");
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error("Mutation failed");
      }
      await loadQueue();
      setStatus("success");
      setMessage("Dispute updated.");
    } catch {
      setStatus("error");
      setMessage("Could not update dispute.");
    }
  }

  const isLoading = status === "loading";

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
              <Badge className={badgeClass}>Human-in-the-loop moderation</Badge>
              <h1 className="mt-4 text-3xl font-bold tracking-tight text-white sm:text-4xl">Panel de arbitraje</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-purple-100">
                La IA organiza y resume la disputa, pero la decision final queda en manos del arbitro humano.
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button variant="ghost" onClick={logout} disabled={isLoading} className={ghostButtonClass}>
                <LogOut className="mr-2 size-4" />
                Cerrar sesion
              </Button>
            </div>
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-4">
          <MetricCard title="Abiertas" value={queue.metrics.open} icon="alert" />
          <MetricCard title="En revision" value={queue.metrics.in_review} icon="scale" />
          <MetricCard title="Alta prioridad" value={queue.metrics.high_priority} icon="alert" />
          <MetricCard title="Resueltas por mi" value={queue.metrics.resolved_by_me} icon="check" />
        </section>

        <p className={`text-sm ${status === "error" ? "text-rose-200" : "text-purple-100"}`}>{message}</p>

        <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
          <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
            <CardHeader>
              <CardTitle className="flex items-center gap-3 text-white">
                <span className="rounded-xl bg-white/10 p-2 text-orange-200">
                  <ClipboardCheck className="size-5" />
                </span>
                Cola de disputas
              </CardTitle>
              <CardDescription className="text-purple-200">Selecciona un caso para revisar evidencia y asistencia IA.</CardDescription>
            </CardHeader>
            <CardContent>
              <Separator className="mb-5 bg-white/10" />
              <div className="grid gap-3 md:hidden">
                {queue.disputes.length === 0 ? (
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-center text-sm text-purple-100">
                    No hay disputas pendientes.
                  </div>
                ) : (
                  queue.disputes.map((dispute) => (
                    <button
                      key={dispute.id}
                      type="button"
                      onClick={() => setSelectedId(dispute.id)}
                      className={`rounded-2xl border p-4 text-left shadow-sm transition-colors ${
                        selectedDispute?.id === dispute.id ? "border-orange-200/40 bg-white/10" : "border-white/10 bg-white/[0.07]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium text-white">{dispute.title}</p>
                          <p className="mt-1 text-sm text-purple-200">
                            {dispute.client_name} vs {dispute.technician_name}
                          </p>
                        </div>
                        <Badge className={badgeClass}>{disputeStatusLabel[dispute.status] ?? dispute.status}</Badge>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Badge className={badgeClass}>{dispute.priority}</Badge>
                        <Badge className={badgeClass}>{dispute.assistant.classification}</Badge>
                      </div>
                    </button>
                  ))
                )}
              </div>
              <div className="hidden overflow-x-auto md:block">
                <Table>
                  <TableHeader>
                    <TableRow className="border-white/10 hover:bg-white/5">
                      <TableHead className="text-purple-100">Caso</TableHead>
                      <TableHead className="text-purple-100">Prioridad</TableHead>
                      <TableHead className="text-purple-100">Estado</TableHead>
                      <TableHead className="text-right text-purple-100">Accion</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {queue.disputes.length === 0 ? (
                      <TableRow className="border-white/10 hover:bg-white/5">
                        <TableCell colSpan={4} className="text-center text-purple-100">
                          No hay disputas pendientes.
                        </TableCell>
                      </TableRow>
                    ) : (
                      queue.disputes.map((dispute) => (
                        <TableRow
                          key={dispute.id}
                          className={`border-white/10 hover:bg-white/5 ${selectedDispute?.id === dispute.id ? "bg-white/10" : ""}`}
                        >
                          <TableCell>
                            <p className="font-medium text-white">{dispute.title}</p>
                            <p className="text-sm text-purple-200">{dispute.client_name} vs {dispute.technician_name}</p>
                          </TableCell>
                          <TableCell className="text-purple-100">{dispute.priority}</TableCell>
                          <TableCell>
                            <Badge className={badgeClass}>{disputeStatusLabel[dispute.status] ?? dispute.status}</Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-purple-100 hover:bg-white/10 hover:text-white"
                              onClick={() => setSelectedId(dispute.id)}
                            >
                              Revisar
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

          <CaseReviewCard
            dispute={selectedDispute}
            decision={decision}
            notes={notes}
            isLoading={isLoading}
            onDecisionChange={setDecision}
            onNotesChange={setNotes}
            onClaim={claimDispute}
            onSubmitDecision={submitDecision}
          />
        </div>
      </main>
    </div>
  );
}

function MetricCard({ title, value, icon }: { title: string; value: number; icon: "alert" | "scale" | "check" }) {
  const Icon = icon === "check" ? CheckCircle2 : icon === "scale" ? Scale : AlertTriangle;
  return (
    <div className={`${surfaceClass} p-5`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-purple-200">{title}</p>
        <Icon className="size-4 text-purple-200" />
      </div>
      <p className="mt-2 text-3xl font-bold text-white">{value}</p>
    </div>
  );
}

function CaseReviewCard({
  dispute,
  decision,
  notes,
  isLoading,
  onDecisionChange,
  onNotesChange,
  onClaim,
  onSubmitDecision,
}: {
  dispute: ArbiterDispute | null;
  decision: string;
  notes: string;
  isLoading: boolean;
  onDecisionChange: (value: string) => void;
  onNotesChange: (value: string) => void;
  onClaim: (id: number) => Promise<void>;
  onSubmitDecision: (id: number) => Promise<void>;
}) {
  if (!dispute) {
    return (
      <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
        <CardHeader>
          <CardTitle className="text-white">Revision del caso</CardTitle>
          <CardDescription className="text-purple-200">No hay caso seleccionado.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className={`${surfaceClass} border-white/10 bg-white/5 text-white`}>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="text-white">{dispute.title}</CardTitle>
            <CardDescription className="text-purple-200">
              Servicio: {dispute.service_title ?? "Sin servicio"} - Tecnico: {dispute.technician_name}
            </CardDescription>
          </div>
          <Badge className={badgeClass}>{dispute.priority}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-2xl border border-white/10 bg-white/[0.07] p-4">
          <div className="mb-2 flex items-center gap-2 font-medium text-white">
            <Bot className="size-4 text-orange-200" />
            Asistencia IA controlada
          </div>
          <p className="text-sm leading-6 text-purple-100">{dispute.assistant.summary}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge className={badgeClass}>Tipo: {dispute.assistant.classification}</Badge>
            <Badge className={badgeClass}>Prioridad sugerida: {dispute.assistant.suggested_priority}</Badge>
          </div>
        </div>

        <div>
          <h3 className="font-medium text-white">Descripcion del cliente</h3>
          <p className="mt-2 text-sm leading-6 text-purple-100">{dispute.description}</p>
        </div>

        <div>
          <h3 className="font-medium text-white">Pasos recomendados</h3>
          <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-purple-100">
            {dispute.assistant.recommended_review_steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="font-medium text-white">Evidencia</h3>
          {dispute.evidence.length === 0 ? (
            <p className="mt-2 text-sm text-purple-200">No hay evidencia adjunta todavia.</p>
          ) : (
            <ul className="mt-2 space-y-2 text-sm text-purple-100">
              {dispute.evidence.map((item) => (
                <li key={item.id} className="rounded-xl border border-white/10 bg-slate-950/20 p-3">
                  {item.note || "Archivo adjunto"}
                </li>
              ))}
            </ul>
          )}
        </div>

        <Separator className="bg-white/10" />

        <div className="grid gap-4 sm:grid-cols-2">
          <Button
            variant="ghost"
            className={ghostButtonClass}
            disabled={isLoading || dispute.status === "in_review"}
            onClick={() => void onClaim(dispute.id)}
          >
            <ClipboardCheck className="mr-2 size-4" />
            Tomar caso
          </Button>
          <div className="space-y-2">
            <Label htmlFor="decision" className="text-white">Decision final</Label>
            <select
              id="decision"
              value={decision}
              onChange={(event) => onDecisionChange(event.target.value)}
              className={selectClass}
            >
              <option value="favor_client" className="text-slate-900">Favor cliente</option>
              <option value="favor_technician" className="text-slate-900">Favor tecnico</option>
              <option value="partial" className="text-slate-900">Resolucion parcial</option>
            </select>
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="notes" className="text-white">Nota del arbitro</Label>
          <Textarea
            id="notes"
            value={notes}
            onChange={(event) => onNotesChange(event.target.value)}
            placeholder="Explica brevemente la razon humana de la decision."
            className={fieldClass}
          />
        </div>
        <Button disabled={isLoading} className={`w-full ${primaryButtonClass}`} onClick={() => void onSubmitDecision(dispute.id)}>
          Registrar decision humana
        </Button>
      </CardContent>
    </Card>
  );
}
