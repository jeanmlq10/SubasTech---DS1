"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, ShieldCheck, Star, Users, Wrench } from "lucide-react";

import { clearStoredAuth, restoreSession } from "@/lib/auth";
import { AdminSummary, API_URL, Category, TechnicianDocument, Zone } from "@/lib/api";
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

const emptySummary: AdminSummary = {
  metrics: {
    total_technicians: 0,
    verified_technicians: 0,
    pending_verification: 0,
    pending_technician_documents: 0,
    suspended_technicians: 0,
    active_services: 0,
    inactive_services: 0,
    total_leads: 0,
    new_leads: 0,
    contacted_leads: 0,
    accepted_leads: 0,
    closed_leads: 0,
    open_disputes: 0,
    in_review_disputes: 0,
    resolved_disputes: 0,
    average_rating: 0,
    average_reputation_score: 0,
    recent_integration_errors: 0,
    total_categories: 0,
    total_zones: 0,
  },
  recent_technicians: [],
  recent_services: [],
  recent_disputes: [],
  lead_status_breakdown: {},
  recent_errors: [],
  role_breakdown: {},
  alerts: [],
};

export function AdminDashboard() {
  const [token, setToken] = useState("");
  const [summary, setSummary] = useState<AdminSummary>(emptySummary);
  const [categories, setCategories] = useState<Category[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [documents, setDocuments] = useState<TechnicianDocument[]>([]);
  const [categoryForm, setCategoryForm] = useState({ name: "", description: "" });
  const [zoneForm, setZoneForm] = useState({ name: "", city: "Barranquilla" });
  const [status, setStatus] = useState<ApiState>("idle");
  const [message, setMessage] = useState("Login in /login or use an administrator JWT token to load platform metrics.");

  useEffect(() => {
    let mounted = true;

    void (async () => {
      const session = await restoreSession();
      if (mounted && session) {
        setToken(session.accessToken);
        setMessage(`Sesion activa como ${session.user.username} (${session.user.role}). Puedes sincronizar el panel.`);
      }
    })();
    void loadCatalog();

    return () => {
      mounted = false;
    };
  }, []);

  function logout() {
    clearStoredAuth();
    setToken("");
    setMessage("Sesion cerrada. Inicia sesion en /login o pega un token admin manual.");
  }

  const metricCards = useMemo(
    () => [
      { title: "Tecnicos", value: summary.metrics.total_technicians, detail: `${summary.metrics.verified_technicians} verificados`, icon: Users },
      { title: "Documentos", value: summary.metrics.pending_technician_documents, detail: "pendientes de revision", icon: ShieldCheck },
      { title: "Servicios activos", value: summary.metrics.active_services, detail: `${summary.metrics.inactive_services} inactivos`, icon: Wrench },
      { title: "Disputas abiertas", value: summary.metrics.open_disputes, detail: `${summary.metrics.in_review_disputes} en revision`, icon: AlertTriangle },
      { title: "Rating promedio", value: summary.metrics.average_rating, detail: `${summary.metrics.total_categories} categorias`, icon: Star },
      { title: "Leads", value: summary.metrics.total_leads, detail: `${summary.metrics.new_leads} nuevos`, icon: RefreshCw },
      { title: "Errores", value: summary.metrics.recent_integration_errors, detail: `${summary.metrics.suspended_technicians} tecnicos suspendidos`, icon: ShieldCheck },
    ],
    [summary],
  );

  async function loadCatalog() {
    try {
      const [categoryResponse, zoneResponse] = await Promise.all([fetch(`${API_URL}/categories/`), fetch(`${API_URL}/zones/`)]);
      if (categoryResponse.ok) setCategories((await categoryResponse.json()) as Category[]);
      if (zoneResponse.ok) setZones((await zoneResponse.json()) as Zone[]);
    } catch {
      setMessage("No se pudo cargar catalogo publico.");
    }
  }

  async function loadSummary() {
    if (!token) {
      setMessage("Add an administrator JWT token before loading metrics.");
      return;
    }

    setStatus("loading");
    try {
      const [response, documentResponse] = await Promise.all([
        fetch(`${API_URL}/admin/summary/`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_URL}/technician/documents/`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (!response.ok) throw new Error("Admin summary request failed");
      if (!documentResponse.ok) throw new Error("Technician documents request failed");
      setSummary((await response.json()) as AdminSummary);
      setDocuments((await documentResponse.json()) as TechnicianDocument[]);
      await loadCatalog();
      setStatus("success");
      setMessage("Admin summary loaded.");
    } catch {
      setStatus("error");
      setMessage("Could not load admin summary. Check that the token belongs to an admin user.");
    }
  }

  async function reviewDocument(documentId: number, reviewStatus: "approved" | "rejected") {
    if (!token) {
      setMessage("Add an administrator JWT token before reviewing documents.");
      return;
    }

    const adminNotes =
      reviewStatus === "rejected" && typeof window !== "undefined"
        ? window.prompt("Observaciones para el tecnico", "El documento no cumple los criterios de verificacion.") ?? ""
        : "";

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/technician/documents/${documentId}/`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ review_status: reviewStatus, admin_notes: adminNotes }),
      });
      if (!response.ok) throw new Error("Document review failed");
      const updatedDocument = (await response.json()) as TechnicianDocument;
      setDocuments((current) => current.map((document) => (document.id === updatedDocument.id ? updatedDocument : document)));
      await loadSummary();
      setStatus("success");
      setMessage(reviewStatus === "approved" ? "Documento aprobado." : "Documento rechazado.");
    } catch {
      setStatus("error");
      setMessage("Could not review technician document.");
    }
  }

  async function technicianAction(technicianId: number, action: "verify" | "unverify" | "suspend" | "activate") {
    if (!token) {
      setMessage("Add an administrator JWT token before moderating technicians.");
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/admin/technicians/${technicianId}/${action}/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("Technician action failed");
      await loadSummary();
      setStatus("success");
      setMessage("Technician updated.");
    } catch {
      setStatus("error");
      setMessage("Could not update technician.");
    }
  }

  async function createCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await createCatalogItem("categories", categoryForm, () => setCategoryForm({ name: "", description: "" }));
  }

  async function createZone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await createCatalogItem("zones", zoneForm, () => setZoneForm({ name: "", city: "Barranquilla" }));
  }

  async function createCatalogItem(endpoint: "categories" | "zones", payload: Record<string, string>, reset: () => void) {
    if (!token) {
      setMessage("Add an administrator JWT token before changing catalog data.");
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/${endpoint}/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, is_active: true }),
      });
      if (!response.ok) throw new Error("Catalog create failed");
      reset();
      await loadSummary();
      setStatus("success");
      setMessage(endpoint === "categories" ? "Category created." : "Zone created.");
    } catch {
      setStatus("error");
      setMessage("Could not create catalog item.");
    }
  }

  const isLoading = status === "loading";

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 pb-28 pt-5 sm:px-8 md:pb-8 lg:px-12">
      <header className="flex flex-col gap-4 rounded-3xl border bg-card p-5 shadow-sm md:flex-row md:items-center md:justify-between">
        <div>
          <Badge variant="secondary">Administrator dashboard</Badge>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Control operativo</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Monitorea y administra tecnicos, servicios, disputas, categorias y zonas para mantener la plataforma operativa.
          </p>
        </div>
        <Button onClick={loadSummary} disabled={isLoading} className="bg-emerald-600 hover:bg-emerald-700">
          {isLoading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
          Sync admin data
        </Button>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Conexion segura</CardTitle>
          <CardDescription>Usa un access token de un usuario con rol admin o permisos staff.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1fr_auto_auto]">
          <Input value={token} onChange={(event) => setToken(event.target.value)} placeholder="Admin JWT access token" type="password" />
          <Button variant="outline" onClick={loadSummary} disabled={isLoading}>Load summary</Button>
          <Button variant="ghost" onClick={logout} disabled={isLoading}>Cerrar sesion</Button>
          <p className={`text-sm ${status === "error" ? "text-destructive" : "text-muted-foreground"}`}>{message}</p>
        </CardContent>
      </Card>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {metricCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.title}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{card.title}</CardTitle>
                <Icon className="size-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-semibold">{card.value}</div>
                <p className="text-xs text-muted-foreground">{card.detail}</p>
              </CardContent>
            </Card>
          );
        })}
      </section>

      <section className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle>Alertas</CardTitle>
            <CardDescription>Prioridades para revision humana.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {summary.alerts.length === 0 ? (
              <div className="flex items-center gap-3 rounded-2xl border p-4 text-sm text-muted-foreground">
                <CheckCircle2 className="size-5 text-emerald-600" />
                No hay alertas operativas por ahora.
              </div>
            ) : (
              summary.alerts.map((alert) => (
                <div key={`${alert.type}-${alert.title}`} className="rounded-2xl border p-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="size-4 text-amber-600" />
                    <p className="font-medium">{alert.title}</p>
                    <Badge variant={alert.type === "critical" ? "destructive" : "secondary"}>{alert.type}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{alert.message}</p>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Resumen operativo</CardTitle>
            <CardDescription>Estado actual de leads, reputacion y suspension operativa.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <div className="flex items-center justify-between rounded-2xl border p-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="size-4 text-emerald-600" />
                <span>Reputacion promedio</span>
              </div>
              <span className="text-xl font-semibold">{summary.metrics.average_reputation_score}</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border p-4">
              <div className="flex items-center gap-2">
                <Users className="size-4 text-emerald-600" />
                <span>Tecnicos suspendidos</span>
              </div>
              <span className="text-xl font-semibold">{summary.metrics.suspended_technicians}</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border p-4">
              <div className="flex items-center gap-2">
                <RefreshCw className="size-4 text-emerald-600" />
                <span>Leads cerrados</span>
              </div>
              <span className="text-xl font-semibold">{summary.metrics.closed_leads}</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl border p-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="size-4 text-emerald-600" />
                <span>Errores recientes</span>
              </div>
              <span className="text-xl font-semibold">{summary.metrics.recent_integration_errors}</span>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Leads por estado</CardTitle>
            <CardDescription>Seguimiento rapido del embudo conversacional.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {Object.keys(summary.lead_status_breakdown).length === 0 ? (
              <p className="text-sm text-muted-foreground">Carga el resumen para ver el estado de leads.</p>
            ) : (
              Object.entries(summary.lead_status_breakdown).map(([statusKey, total]) => (
                <div key={statusKey} className="flex items-center justify-between rounded-2xl border p-4">
                  <div className="flex items-center gap-2">
                    <RefreshCw className="size-4 text-emerald-600" />
                    <span className="capitalize">{statusKey.replaceAll("_", " ")}</span>
                  </div>
                  <span className="text-xl font-semibold">{total}</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Distribucion de roles</CardTitle>
            <CardDescription>Usuarios registrados por rol de plataforma.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {Object.keys(summary.role_breakdown).length === 0 ? (
              <p className="text-sm text-muted-foreground">Carga el resumen para ver roles.</p>
            ) : (
              Object.entries(summary.role_breakdown).map(([role, total]) => (
                <div key={role} className="flex items-center justify-between rounded-2xl border p-4">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="size-4 text-emerald-600" />
                    <span className="capitalize">{role}</span>
                  </div>
                  <span className="text-xl font-semibold">{total}</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Tecnicos recientes</CardTitle>
          <CardDescription>Verifica, suspende o reactiva tecnicos desde el panel.</CardDescription>
        </CardHeader>
        <CardContent>
          <DataSeparator />
          <div className="grid gap-3 md:hidden">
            {summary.recent_technicians.length === 0 ? (
              <div className="rounded-2xl border p-4 text-center text-sm text-muted-foreground">No hay tecnicos para mostrar.</div>
            ) : (
              summary.recent_technicians.map((technician) => (
                <div key={technician.id} className="rounded-2xl border p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{technician.name}</p>
                      <p className="text-sm text-muted-foreground">{technician.email || "Sin email"}</p>
                    </div>
                    <Badge variant={technician.user_is_active ? "secondary" : "destructive"}>{technician.user_is_active ? "Activo" : "Suspendido"}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge variant={technician.is_verified ? "default" : "secondary"}>{technician.is_verified ? "Verificado" : "Pendiente"}</Badge>
                    <Badge variant="secondary">{technician.document_counts.pending} docs pendientes</Badge>
                    <Badge variant="secondary">{technician.service_count} servicios</Badge>
                    <Badge variant="secondary">{technician.average_rating} rating</Badge>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">{technician.zones.join(", ") || "Sin zonas"}</p>
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <Button size="sm" variant="outline" onClick={() => void technicianAction(technician.id, technician.is_verified ? "unverify" : "verify")}>{technician.is_verified ? "Quitar" : "Verificar"}</Button>
                    <Button size="sm" variant={technician.user_is_active ? "destructive" : "outline"} onClick={() => void technicianAction(technician.id, technician.user_is_active ? "suspend" : "activate")}>{technician.user_is_active ? "Suspender" : "Reactivar"}</Button>
                  </div>
                </div>
              ))
            )}
          </div>
          <div className="hidden overflow-x-auto md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Servicios</TableHead>
                  <TableHead>Zonas</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {summary.recent_technicians.length === 0 ? (
                  <EmptyRow colSpan={5} label="No hay tecnicos para mostrar." />
                ) : (
                  summary.recent_technicians.map((technician) => (
                    <TableRow key={technician.id}>
                      <TableCell>
                        <p className="font-medium">{technician.name}</p>
                        <p className="text-sm text-muted-foreground">{technician.email || "Sin email"}</p>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant={technician.is_verified ? "default" : "secondary"}>{technician.is_verified ? "Verificado" : "Pendiente"}</Badge>
                          <Badge variant={technician.user_is_active ? "secondary" : "destructive"}>{technician.user_is_active ? "Activo" : "Suspendido"}</Badge>
                          <Badge variant="secondary">{technician.document_counts.pending} docs pendientes</Badge>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">{technician.availability_status} - {technician.average_rating} rating</p>
                      </TableCell>
                      <TableCell>{technician.service_count}</TableCell>
                      <TableCell>{technician.zones.join(", ") || "Sin zonas"}</TableCell>
                      <TableCell className="min-w-56 text-right">
                        <div className="flex flex-wrap justify-end gap-2">
                          <Button size="sm" variant="outline" onClick={() => void technicianAction(technician.id, technician.is_verified ? "unverify" : "verify")}>{technician.is_verified ? "Quitar verificacion" : "Verificar"}</Button>
                          <Button size="sm" variant={technician.user_is_active ? "destructive" : "outline"} onClick={() => void technicianAction(technician.id, technician.user_is_active ? "suspend" : "activate")}>{technician.user_is_active ? "Suspender" : "Reactivar"}</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Documentos de tecnicos</CardTitle>
          <CardDescription>Aprueba o rechaza soportes subidos durante el onboarding.</CardDescription>
        </CardHeader>
        <CardContent>
          <DataSeparator />
          {documents.length === 0 ? (
            <div className="rounded-2xl border p-4 text-sm text-muted-foreground">No hay documentos para revisar.</div>
          ) : (
            <div className="grid gap-3">
              {documents.map((document) => (
                <div key={document.id} className="rounded-2xl border p-4 shadow-sm">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{document.technician_name}</p>
                        <Badge variant={document.review_status === "rejected" ? "destructive" : "secondary"}>{document.review_status}</Badge>
                        <Badge variant="outline">{document.document_type}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">{document.notes || "Sin notas del tecnico."}</p>
                      {document.admin_notes ? <p className="mt-1 text-sm text-muted-foreground">Revision admin: {document.admin_notes}</p> : null}
                      <a className="mt-2 inline-block text-sm font-medium text-primary underline-offset-4 hover:underline" href={document.file} target="_blank" rel="noreferrer">
                        Ver documento
                      </a>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" disabled={isLoading || document.review_status === "approved"} onClick={() => void reviewDocument(document.id, "approved")}>
                        Aprobar
                      </Button>
                      <Button size="sm" variant="destructive" disabled={isLoading || document.review_status === "rejected"} onClick={() => void reviewDocument(document.id, "rejected")}>
                        Rechazar
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <section className="grid gap-6 xl:grid-cols-2">
        <CatalogCard
          title="Categorias"
          description="Gestiona tipos de servicio usados por Telegram y recomendaciones."
          items={categories.map((category) => `${category.name}${category.is_active ? "" : " (inactiva)"}`)}
          onSubmit={createCategory}
        >
          <div className="space-y-2">
            <Label htmlFor="category-name">Nombre</Label>
            <Input id="category-name" value={categoryForm.name} onChange={(event) => setCategoryForm((current) => ({ ...current, name: event.target.value }))} required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="category-description">Descripcion</Label>
            <Textarea id="category-description" value={categoryForm.description} onChange={(event) => setCategoryForm((current) => ({ ...current, description: event.target.value }))} />
          </div>
        </CatalogCard>

        <CatalogCard
          title="Zonas"
          description="Gestiona cobertura usada para matching de tecnicos."
          items={zones.map((zone) => `${zone.name}, ${zone.city}${zone.is_active ? "" : " (inactiva)"}`)}
          onSubmit={createZone}
        >
          <div className="space-y-2">
            <Label htmlFor="zone-name">Nombre</Label>
            <Input id="zone-name" value={zoneForm.name} onChange={(event) => setZoneForm((current) => ({ ...current, name: event.target.value }))} required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="zone-city">Ciudad</Label>
            <Input id="zone-city" value={zoneForm.city} onChange={(event) => setZoneForm((current) => ({ ...current, city: event.target.value }))} required />
          </div>
        </CatalogCard>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Servicios recientes</CardTitle>
            <CardDescription>Catalogo que alimenta recomendaciones.</CardDescription>
          </CardHeader>
          <CardContent>
            <DataSeparator />
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Servicio</TableHead>
                    <TableHead>Tecnico</TableHead>
                    <TableHead>Precio</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summary.recent_services.length === 0 ? (
                    <EmptyRow colSpan={4} label="No hay servicios recientes." />
                  ) : (
                    summary.recent_services.map((service) => (
                      <TableRow key={service.id}>
                        <TableCell>
                          <p className="font-medium">{service.title}</p>
                          <p className="text-sm text-muted-foreground">{service.category}</p>
                        </TableCell>
                        <TableCell>{service.technician}</TableCell>
                        <TableCell>${Number(service.base_price).toLocaleString("es-CO")}</TableCell>
                        <TableCell><Badge variant={service.is_active ? "default" : "secondary"}>{service.is_active ? "Activo" : "Inactivo"}</Badge></TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Disputas recientes</CardTitle>
            <CardDescription>Casos para moderacion humana.</CardDescription>
          </CardHeader>
          <CardContent>
            <DataSeparator />
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Caso</TableHead>
                    <TableHead>Tecnico</TableHead>
                    <TableHead>Prioridad</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summary.recent_disputes.length === 0 ? (
                    <EmptyRow colSpan={4} label="No hay disputas recientes." />
                  ) : (
                    summary.recent_disputes.map((dispute) => (
                      <TableRow key={dispute.id}>
                        <TableCell>
                          <p className="font-medium">{dispute.title}</p>
                          <p className="text-sm text-muted-foreground">Cliente: {dispute.client}</p>
                        </TableCell>
                        <TableCell>{dispute.technician}</TableCell>
                        <TableCell>{dispute.priority}</TableCell>
                        <TableCell><Badge variant={dispute.status === "open" ? "destructive" : "secondary"}>{dispute.status}</Badge></TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Errores operativos recientes</CardTitle>
          <CardDescription>Eventos de auditoria marcados como error o integracion fallida.</CardDescription>
        </CardHeader>
        <CardContent>
          <DataSeparator />
          <div className="grid gap-3">
            {summary.recent_errors.length === 0 ? (
              <div className="rounded-2xl border p-4 text-sm text-muted-foreground">No hay errores recientes para mostrar.</div>
            ) : (
              summary.recent_errors.map((event) => (
                <div key={event.id} className="rounded-2xl border p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="destructive">{event.status}</Badge>
                    <Badge variant="secondary">{event.event_type}</Badge>
                    <span className="text-sm font-medium">{event.source || "sin fuente"}</span>
                  </div>
                  <p className="mt-2 text-sm">{event.message}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {event.entity_type || "evento"} {event.entity_id ? `#${event.entity_id}` : ""} · {new Date(event.created_at).toLocaleString("es-CO")}
                  </p>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
      <MobileRoleNav />
    </div>
  );
}

function CatalogCard({ title, description, items, onSubmit, children }: { title: string; description: string; items: string[]; onSubmit: (event: FormEvent<HTMLFormElement>) => void; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="space-y-4" onSubmit={onSubmit}>
          {children}
          <Button type="submit" className="w-full">Crear {title.toLowerCase()}</Button>
        </form>
        <Separator />
        <div className="grid gap-2">
          {items.length === 0 ? <p className="text-sm text-muted-foreground">No hay registros.</p> : items.slice(0, 8).map((item) => <div key={item} className="rounded-xl border px-3 py-2 text-sm">{item}</div>)}
        </div>
      </CardContent>
    </Card>
  );
}

function DataSeparator() {
  return <Separator className="mb-4" />;
}

function EmptyRow({ colSpan, label }: { colSpan: number; label: string }) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="text-center text-muted-foreground">{label}</TableCell>
    </TableRow>
  );
}
