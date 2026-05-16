"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Bot, CheckCircle2, ClipboardCheck, Loader2, RefreshCw, Scale } from "lucide-react";

import { clearStoredAuth, getStoredAuth } from "@/lib/auth";
import { API_URL, ArbiterDispute, ArbiterQueue } from "@/lib/api";
import { MobileRoleNav } from "@/components/mobile-role-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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

export function ArbiterDashboard() {
  const [token, setToken] = useState("");
  const [queue, setQueue] = useState<ArbiterQueue>(emptyQueue);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [decision, setDecision] = useState("favor_client");
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState<ApiState>("idle");
  const [message, setMessage] = useState("Login in /login or use an arbiter JWT token to load disputes.");

  useEffect(() => {
    const session = getStoredAuth();
    if (session) {
      setToken(session.accessToken);
      setMessage(`Sesion activa como ${session.user.username} (${session.user.role}). Puedes sincronizar el panel.`);
    }
  }, []);

  function logout() {
    clearStoredAuth();
    setToken("");
    setMessage("Sesion cerrada. Inicia sesion en /login o pega un token arbitro manual.");
  }

  const selectedDispute = useMemo(
    () => queue.disputes.find((dispute) => dispute.id === selectedId) ?? queue.disputes[0] ?? null,
    [queue.disputes, selectedId],
  );

  async function loadQueue() {
    if (!token) {
      setMessage("Add an arbiter JWT token before loading disputes.");
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/arbiter/queue/`, {
        headers: { Authorization: `Bearer ${token}` },
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
    <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 pb-28 pt-5 sm:px-8 md:pb-8 lg:px-12">
      <header className="flex flex-col gap-4 rounded-3xl border bg-card p-5 shadow-sm md:flex-row md:items-center md:justify-between">
        <div>
          <Badge variant="secondary">Human-in-the-loop moderation</Badge>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Panel de arbitraje</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            La IA organiza y resume la disputa, pero la decision final queda en manos del arbitro humano.
          </p>
        </div>
        <Button onClick={loadQueue} disabled={isLoading} className="bg-emerald-600 hover:bg-emerald-700">
          {isLoading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
          Sync disputes
        </Button>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Conexion segura</CardTitle>
          <CardDescription>Usa un access token de un usuario con rol arbiter, admin o staff.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1fr_auto_auto]">
          <Input value={token} onChange={(event) => setToken(event.target.value)} placeholder="Arbiter JWT access token" type="password" />
          <Button variant="outline" onClick={loadQueue} disabled={isLoading}>
            Load queue
          </Button>
          <Button variant="ghost" onClick={logout} disabled={isLoading}>
            Cerrar sesion
          </Button>
          <p className={`text-sm ${status === "error" ? "text-destructive" : "text-muted-foreground"}`}>{message}</p>
        </CardContent>
      </Card>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard title="Abiertas" value={queue.metrics.open} icon="alert" />
        <MetricCard title="En revision" value={queue.metrics.in_review} icon="scale" />
        <MetricCard title="Alta prioridad" value={queue.metrics.high_priority} icon="alert" />
        <MetricCard title="Resueltas por mi" value={queue.metrics.resolved_by_me} icon="check" />
      </section>

      <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <CardHeader>
            <CardTitle>Cola de disputas</CardTitle>
            <CardDescription>Selecciona un caso para revisar evidencia y asistencia IA.</CardDescription>
          </CardHeader>
          <CardContent>
            <Separator className="mb-4" />
            <div className="grid gap-3 md:hidden">
              {queue.disputes.length === 0 ? (
                <div className="rounded-2xl border p-4 text-center text-sm text-muted-foreground">No hay disputas pendientes.</div>
              ) : (
                queue.disputes.map((dispute) => (
                  <button
                    key={dispute.id}
                    type="button"
                    onClick={() => setSelectedId(dispute.id)}
                    className={`rounded-2xl border p-4 text-left shadow-sm transition-colors ${selectedDispute?.id === dispute.id ? "bg-muted" : "bg-card"}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{dispute.title}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{dispute.client_name} vs {dispute.technician_name}</p>
                      </div>
                      <Badge variant={dispute.status === "open" ? "destructive" : "secondary"}>{dispute.status}</Badge>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Badge variant="secondary">{dispute.priority}</Badge>
                      <Badge variant="secondary">{dispute.assistant.classification}</Badge>
                    </div>
                  </button>
                ))
              )}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Caso</TableHead>
                    <TableHead>Prioridad</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead className="text-right">Accion</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {queue.disputes.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-muted-foreground">
                        No hay disputas pendientes.
                      </TableCell>
                    </TableRow>
                  ) : (
                    queue.disputes.map((dispute) => (
                      <TableRow key={dispute.id} className={selectedDispute?.id === dispute.id ? "bg-muted/50" : ""}>
                        <TableCell>
                          <p className="font-medium">{dispute.title}</p>
                          <p className="text-sm text-muted-foreground">{dispute.client_name} vs {dispute.technician_name}</p>
                        </TableCell>
                        <TableCell>{dispute.priority}</TableCell>
                        <TableCell>
                          <Badge variant={dispute.status === "open" ? "destructive" : "secondary"}>{dispute.status}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" onClick={() => setSelectedId(dispute.id)}>
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
      <MobileRoleNav />
    </div>
  );
}

function MetricCard({ title, value, icon }: { title: string; value: number; icon: "alert" | "scale" | "check" }) {
  const Icon = icon === "check" ? CheckCircle2 : icon === "scale" ? Scale : AlertTriangle;
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold">{value}</div>
      </CardContent>
    </Card>
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
      <Card>
        <CardHeader>
          <CardTitle>Revision del caso</CardTitle>
          <CardDescription>No hay caso seleccionado.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>{dispute.title}</CardTitle>
            <CardDescription>
              Servicio: {dispute.service_title ?? "Sin servicio"} - Tecnico: {dispute.technician_name}
            </CardDescription>
          </div>
          <Badge variant={dispute.priority === "high" ? "destructive" : "secondary"}>{dispute.priority}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-2xl border p-4">
          <div className="mb-2 flex items-center gap-2 font-medium">
            <Bot className="size-4 text-emerald-600" />
            Asistencia IA controlada
          </div>
          <p className="text-sm leading-6 text-muted-foreground">{dispute.assistant.summary}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge variant="secondary">Tipo: {dispute.assistant.classification}</Badge>
            <Badge variant="secondary">Prioridad sugerida: {dispute.assistant.suggested_priority}</Badge>
          </div>
        </div>

        <div>
          <h3 className="font-medium">Descripcion del cliente</h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{dispute.description}</p>
        </div>

        <div>
          <h3 className="font-medium">Pasos recomendados</h3>
          <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-muted-foreground">
            {dispute.assistant.recommended_review_steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="font-medium">Evidencia</h3>
          {dispute.evidence.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">No hay evidencia adjunta todavia.</p>
          ) : (
            <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
              {dispute.evidence.map((item) => (
                <li key={item.id} className="rounded-xl border p-3">{item.note || "Archivo adjunto"}</li>
              ))}
            </ul>
          )}
        </div>

        <Separator />

        <div className="grid gap-4 sm:grid-cols-2">
          <Button variant="outline" disabled={isLoading || dispute.status === "in_review"} onClick={() => void onClaim(dispute.id)}>
            <ClipboardCheck className="mr-2 size-4" />
            Tomar caso
          </Button>
          <div className="space-y-2">
            <Label htmlFor="decision">Decision final</Label>
            <select
              id="decision"
              value={decision}
              onChange={(event) => onDecisionChange(event.target.value)}
              className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            >
              <option value="favor_client">Favor cliente</option>
              <option value="favor_technician">Favor tecnico</option>
              <option value="partial">Resolucion parcial</option>
            </select>
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="notes">Nota del arbitro</Label>
          <Textarea
            id="notes"
            value={notes}
            onChange={(event) => onNotesChange(event.target.value)}
            placeholder="Explica brevemente la razon humana de la decision."
          />
        </div>
        <Button disabled={isLoading} className="w-full bg-emerald-600 hover:bg-emerald-700" onClick={() => void onSubmitDecision(dispute.id)}>
          Registrar decision humana
        </Button>
      </CardContent>
    </Card>
  );
}
