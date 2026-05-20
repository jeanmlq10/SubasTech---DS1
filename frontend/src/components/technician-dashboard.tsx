"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Loader2, Plus, RefreshCw, Trash2, UserCheck, Wrench } from "lucide-react";

import { clearStoredAuth, restoreSession } from "@/lib/auth";
import { API_URL, Category, OnboardingResponse, TechnicianLead, TechnicianService, Zone } from "@/lib/api";
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

type ServiceForm = {
  categoryId: string;
  title: string;
  description: string;
  basePrice: string;
  isActive: boolean;
};

const emptyServiceForm: ServiceForm = {
  categoryId: "",
  title: "",
  description: "",
  basePrice: "",
  isActive: true,
};

export function TechnicianDashboard() {
  const [token, setToken] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [selectedZones, setSelectedZones] = useState<number[]>([]);
  const [bio, setBio] = useState("");
  const [availability, setAvailability] = useState("available");
  const [responseTime, setResponseTime] = useState("30");
  const [services, setServices] = useState<TechnicianService[]>([]);
  const [leads, setLeads] = useState<TechnicianLead[]>([]);
  const [serviceForm, setServiceForm] = useState<ServiceForm>(emptyServiceForm);
  const [status, setStatus] = useState<ApiState>("idle");
  const [message, setMessage] = useState("Login in /login or use a JWT token to sync your technician workspace.");

  useEffect(() => {
    let mounted = true;

    void (async () => {
      const session = await restoreSession();
      if (mounted && session) {
        setToken(session.accessToken);
        setMessage(`Sesion activa como ${session.user.username} (${session.user.role}). Puedes sincronizar el panel.`);
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  function logout() {
    clearStoredAuth();
    setToken("");
    setMessage("Sesion cerrada. Inicia sesion en /login o pega un token manual.");
  }

  const authHeaders = useMemo(
    () => ({
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    }),
    [token],
  );

  useEffect(() => {
    void loadCatalog();
  }, []);

  async function loadCatalog() {
    try {
      const [categoryResponse, zoneResponse] = await Promise.all([
        fetch(`${API_URL}/categories/`),
        fetch(`${API_URL}/zones/`),
      ]);
      if (categoryResponse.ok) {
        setCategories((await categoryResponse.json()) as Category[]);
      }
      if (zoneResponse.ok) {
        setZones((await zoneResponse.json()) as Zone[]);
      }
    } catch {
      setMessage("Could not load public catalog data yet.");
    }
  }

  async function loadWorkspace() {
    if (!token) {
      setMessage("Add a JWT token before loading the technician workspace.");
      return;
    }

    setStatus("loading");
    try {
      const [onboardingResponse, servicesResponse, leadsResponse] = await Promise.all([
        fetch(`${API_URL}/technician/onboarding/`, { headers: authHeaders }),
        fetch(`${API_URL}/technician/services/`, { headers: authHeaders }),
        fetch(`${API_URL}/technician/leads/`, { headers: authHeaders }),
      ]);

      if (!onboardingResponse.ok || !servicesResponse.ok || !leadsResponse.ok) {
        throw new Error("Workspace request failed");
      }

      const onboarding = (await onboardingResponse.json()) as OnboardingResponse;
      const technicianServices = (await servicesResponse.json()) as TechnicianService[];
      const technicianLeads = (await leadsResponse.json()) as TechnicianLead[];
      if (onboarding.profile) {
        setBio(onboarding.profile.bio ?? "");
        setAvailability(onboarding.profile.availability_status);
        setResponseTime(String(onboarding.profile.response_time_minutes));
        setSelectedZones(onboarding.profile.zones.map((zone) => zone.id));
      }
      setServices(technicianServices);
      setLeads(technicianLeads);
      setStatus("success");
      setMessage("Technician workspace loaded.");
    } catch {
      setStatus("error");
      setMessage("Could not load workspace. Check the token and backend server.");
    }
  }

  async function submitOnboarding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      setMessage("Add a JWT token before saving onboarding.");
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/technician/onboarding/`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          bio,
          availability_status: availability,
          response_time_minutes: Number(responseTime),
          zone_ids: selectedZones,
        }),
      });
      if (!response.ok) {
        throw new Error("Onboarding request failed");
      }
      await loadWorkspace();
      setStatus("success");
      setMessage("Technician profile saved.");
    } catch {
      setStatus("error");
      setMessage("Could not save onboarding information.");
    }
  }

  async function submitService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      setMessage("Add a JWT token before creating services.");
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
      await loadWorkspace();
      setStatus("success");
      setMessage("Service created.");
    } catch {
      setStatus("error");
      setMessage("Could not create service. Complete onboarding first.");
    }
  }

  async function updateLeadStatus(leadId: number, leadStatus: TechnicianLead["status"]) {
    if (!token) {
      setMessage("Add a JWT token before updating leads.");
      return;
    }

    setStatus("loading");
    try {
      const response = await fetch(`${API_URL}/technician/leads/${leadId}/status/`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ status: leadStatus }),
      });
      if (!response.ok) {
        throw new Error("Lead status request failed");
      }
      await loadWorkspace();
      setStatus("success");
      setMessage("Lead updated.");
    } catch {
      setStatus("error");
      setMessage("Could not update lead.");
    }
  }

  async function deleteService(serviceId: number) {
    if (!token) {
      setMessage("Add a JWT token before deleting services.");
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
      setMessage("Service deleted.");
    } catch {
      setStatus("error");
      setMessage("Could not delete service.");
    }
  }

  function toggleZone(zoneId: number) {
    setSelectedZones((current) =>
      current.includes(zoneId) ? current.filter((id) => id !== zoneId) : [...current, zoneId],
    );
  }

  const isLoading = status === "loading";

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 pb-28 pt-5 sm:px-8 md:pb-8 lg:px-12">
      <header className="flex flex-col gap-4 rounded-3xl border bg-card p-5 shadow-sm md:flex-row md:items-center md:justify-between">
        <div>
          <Badge variant="secondary">Technician workspace</Badge>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Onboarding y servicios</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Completa tu perfil, define zonas de cobertura y administra los servicios que el motor de recomendacion usara para sugerirte por WhatsApp.
          </p>
        </div>
        <Button onClick={loadWorkspace} disabled={isLoading} className="bg-emerald-600 hover:bg-emerald-700">
          {isLoading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
          Sync workspace
        </Button>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Conexion con backend</CardTitle>
          <CardDescription>Usa el access token de /api/auth/token/ para probar el flujo autenticado.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1fr_auto_auto]">
          <Input
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="JWT access token"
            type="password"
          />
          <Button variant="outline" onClick={loadWorkspace} disabled={isLoading}>
            Load data
          </Button>
          <Button variant="ghost" onClick={logout} disabled={isLoading}>
            Cerrar sesion
          </Button>
          <p className={`text-sm ${status === "error" ? "text-destructive" : "text-muted-foreground"}`}>{message}</p>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-emerald-100 p-2 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200">
                <UserCheck className="size-5" />
              </div>
              <div>
                <CardTitle>Perfil tecnico</CardTitle>
                <CardDescription>Informacion base para el matching.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form className="space-y-5" onSubmit={submitOnboarding}>
              <div className="space-y-2">
                <Label htmlFor="bio">Bio profesional</Label>
                <Textarea
                  id="bio"
                  value={bio}
                  onChange={(event) => setBio(event.target.value)}
                  placeholder="Ej: Electricista residencial con experiencia en emergencias."
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="availability">Disponibilidad</Label>
                  <select
                    id="availability"
                    value={availability}
                    onChange={(event) => setAvailability(event.target.value)}
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                  >
                    <option value="available">Disponible</option>
                    <option value="busy">Ocupado</option>
                    <option value="offline">Offline</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="responseTime">Respuesta estimada (min)</Label>
                  <Input
                    id="responseTime"
                    min="1"
                    type="number"
                    value={responseTime}
                    onChange={(event) => setResponseTime(event.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-3">
                <Label>Zonas de cobertura</Label>
                <div className="grid gap-2 sm:grid-cols-2">
                  {zones.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Crea zonas en el admin/backend para seleccionarlas aqui.</p>
                  ) : (
                    zones.map((zone) => (
                      <label key={zone.id} className="flex items-center gap-2 rounded-xl border p-3 text-sm">
                        <input
                          checked={selectedZones.includes(zone.id)}
                          onChange={() => toggleZone(zone.id)}
                          type="checkbox"
                        />
                        {zone.name}, {zone.city}
                      </label>
                    ))
                  )}
                </div>
              </div>
              <Button type="submit" disabled={isLoading} className="w-full bg-emerald-600 hover:bg-emerald-700">
                Guardar onboarding
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-blue-100 p-2 text-blue-700 dark:bg-blue-950 dark:text-blue-200">
                <Wrench className="size-5" />
              </div>
              <div>
                <CardTitle>Nuevo servicio</CardTitle>
                <CardDescription>Estos servicios aparecen en las recomendaciones.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={submitService}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="category">Categoria</Label>
                  <select
                    id="category"
                    value={serviceForm.categoryId}
                    onChange={(event) => setServiceForm((current) => ({ ...current, categoryId: event.target.value }))}
                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                    required
                  >
                    <option value="">Selecciona categoria</option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="price">Precio base</Label>
                  <Input
                    id="price"
                    min="0"
                    step="1000"
                    type="number"
                    value={serviceForm.basePrice}
                    onChange={(event) => setServiceForm((current) => ({ ...current, basePrice: event.target.value }))}
                    placeholder="80000"
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="title">Titulo</Label>
                <Input
                  id="title"
                  value={serviceForm.title}
                  onChange={(event) => setServiceForm((current) => ({ ...current, title: event.target.value }))}
                  placeholder="Instalacion electrica residencial"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Descripcion</Label>
                <Textarea
                  id="description"
                  value={serviceForm.description}
                  onChange={(event) => setServiceForm((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Describe alcance, condiciones y tipo de trabajos."
                  required
                />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  checked={serviceForm.isActive}
                  onChange={(event) => setServiceForm((current) => ({ ...current, isActive: event.target.checked }))}
                  type="checkbox"
                />
                Servicio activo
              </label>
              <Button type="submit" disabled={isLoading} className="w-full">
                <Plus className="mr-2 size-4" />
                Crear servicio
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Leads recibidos</CardTitle>
          <CardDescription>Solicitudes creadas cuando un cliente elige tu servicio por WhatsApp.</CardDescription>
        </CardHeader>
        <CardContent>
          <Separator className="mb-4" />
          <div className="grid gap-3">
            {leads.length === 0 ? (
              <div className="rounded-2xl border p-4 text-center text-sm text-muted-foreground">Aun no tienes leads asignados.</div>
            ) : (
              leads.map((lead) => (
                <div key={lead.id} className="rounded-2xl border p-4 shadow-sm">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="font-medium">{lead.service_title ?? "Servicio tecnico"}</p>
                      <p className="mt-1 text-sm text-muted-foreground">Cliente: {lead.client_phone}</p>
                      <p className="mt-1 text-sm text-muted-foreground">Zona: {lead.location || "Sin zona"} - Urgencia: {lead.urgency}</p>
                    </div>
                    <Badge variant={lead.status === "new" ? "default" : "secondary"}>{lead.status}</Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">{lead.message}</p>
                  <div className="mt-4 grid gap-2 sm:grid-cols-3">
                    <Button size="sm" variant="outline" onClick={() => void updateLeadStatus(lead.id, "contacted")}>Contactado</Button>
                    <Button size="sm" variant="outline" onClick={() => void updateLeadStatus(lead.id, "accepted")}>Aceptado</Button>
                    <Button size="sm" variant="outline" onClick={() => void updateLeadStatus(lead.id, "closed")}>Cerrado</Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Servicios publicados</CardTitle>
          <CardDescription>CRUD inicial para el catalogo del tecnico autenticado.</CardDescription>
        </CardHeader>
        <CardContent>
          <Separator className="mb-4" />
          <div className="grid gap-3 md:hidden">
            {services.length === 0 ? (
              <div className="rounded-2xl border p-4 text-center text-sm text-muted-foreground">Todavia no hay servicios cargados.</div>
            ) : (
              services.map((service) => (
                <div key={service.id} className="rounded-2xl border p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{service.title}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{service.category.name}</p>
                    </div>
                    <Badge variant={service.is_active ? "default" : "secondary"}>{service.is_active ? "Activo" : "Inactivo"}</Badge>
                  </div>
                  <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{service.description}</p>
                  <div className="mt-4 flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold">${Number(service.base_price).toLocaleString("es-CO")}</span>
                    <Button variant="outline" size="sm" onClick={() => void deleteService(service.id)}>
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
                <TableRow>
                  <TableHead>Servicio</TableHead>
                  <TableHead>Categoria</TableHead>
                  <TableHead>Precio base</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {services.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground">
                      Todavia no hay servicios cargados.
                    </TableCell>
                  </TableRow>
                ) : (
                  services.map((service) => (
                    <TableRow key={service.id}>
                      <TableCell>
                        <p className="font-medium">{service.title}</p>
                        <p className="line-clamp-1 text-sm text-muted-foreground">{service.description}</p>
                      </TableCell>
                      <TableCell>{service.category.name}</TableCell>
                      <TableCell>${Number(service.base_price).toLocaleString("es-CO")}</TableCell>
                      <TableCell>
                        <Badge variant={service.is_active ? "default" : "secondary"}>
                          {service.is_active ? "Activo" : "Inactivo"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => void deleteService(service.id)}>
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
      <MobileRoleNav />
    </div>
  );
}
