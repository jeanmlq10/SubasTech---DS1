"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, LogOut, Plus, RefreshCw, Trash2, Wrench } from "lucide-react";

import { API_URL, Category, OnboardingResponse, TechnicianLead, TechnicianService } from "@/lib/api";
import { clearStoredAuth, restoreSession } from "@/lib/auth";
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
  const router = useRouter();
  const [token, setToken] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [services, setServices] = useState<TechnicianService[]>([]);
  const [leads, setLeads] = useState<TechnicianLead[]>([]);
  const [serviceForm, setServiceForm] = useState<ServiceForm>(emptyServiceForm);
  const [status, setStatus] = useState<ApiState>("loading");
  const [message, setMessage] = useState("Cargando tu workspace tecnico...");

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
        const [onboardingResponse, categoryResponse, servicesResponse, leadsResponse] = await Promise.all([
          fetch(`${API_URL}/technician/onboarding/`, { headers: requestHeaders }),
          fetch(`${API_URL}/categories/`),
          fetch(`${API_URL}/technician/services/`, { headers: requestHeaders }),
          fetch(`${API_URL}/technician/leads/`, { headers: requestHeaders }),
        ]);

        if (!onboardingResponse.ok || !categoryResponse.ok || !servicesResponse.ok || !leadsResponse.ok) {
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

  async function updateLeadStatus(leadId: number, leadStatus: TechnicianLead["status"]) {
    if (!token) {
      setMessage("Inicia sesion antes de actualizar leads.");
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
      await loadWorkspace(token);
      setStatus("success");
      setMessage("Lead actualizado.");
    } catch {
      setStatus("error");
      setMessage("No se pudo actualizar el lead.");
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

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 pb-28 pt-5 sm:px-8 md:pb-8 lg:px-12">
      <header className="flex flex-col gap-4 rounded-lg border bg-card p-5 shadow-sm md:flex-row md:items-center md:justify-between">
        <div>
          <Badge variant="secondary">Technician workspace</Badge>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Dashboard tecnico</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Administra servicios publicados y solicitudes recibidas desde el flujo conversacional.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button onClick={() => void loadWorkspace(token)} disabled={isLoading} className="bg-emerald-600 hover:bg-emerald-700">
            {isLoading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
            Sincronizar
          </Button>
          <Button variant="outline" onClick={logout} disabled={isLoading}>
            <LogOut className="mr-2 size-4" />
            Cerrar sesion
          </Button>
        </div>
      </header>

      <p className={`text-sm ${status === "error" ? "text-destructive" : "text-muted-foreground"}`}>{message}</p>

      <Card className="rounded-lg">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-blue-100 p-2 text-blue-700 dark:bg-blue-950 dark:text-blue-200">
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

      <Card className="rounded-lg">
        <CardHeader>
          <CardTitle>Leads recibidos</CardTitle>
          <CardDescription>Solicitudes creadas cuando un cliente elige tu servicio por Telegram.</CardDescription>
        </CardHeader>
        <CardContent>
          <Separator className="mb-4" />
          <div className="grid gap-3">
            {leads.length === 0 ? (
              <div className="rounded-lg border p-4 text-center text-sm text-muted-foreground">Aun no tienes leads asignados.</div>
            ) : (
              leads.map((lead) => (
                <div key={lead.id} className="rounded-lg border p-4 shadow-sm">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="font-medium">{lead.service_title ?? "Servicio tecnico"}</p>
                      <p className="mt-1 text-sm text-muted-foreground">Cliente: {lead.client_phone}</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Zona: {lead.location || "Sin zona"} - Urgencia: {lead.urgency}
                      </p>
                    </div>
                    <Badge variant={lead.status === "new" ? "default" : "secondary"}>{lead.status}</Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">{lead.message}</p>
                  <div className="mt-4 grid gap-2 sm:grid-cols-3">
                    <Button size="sm" variant="outline" onClick={() => void updateLeadStatus(lead.id, "contacted")}>
                      Contactado
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => void updateLeadStatus(lead.id, "accepted")}>
                      Aceptado
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => void updateLeadStatus(lead.id, "closed")}>
                      Cerrado
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-lg">
        <CardHeader>
          <CardTitle>Servicios publicados</CardTitle>
          <CardDescription>Catalogo del tecnico autenticado.</CardDescription>
        </CardHeader>
        <CardContent>
          <Separator className="mb-4" />
          <div className="grid gap-3 md:hidden">
            {services.length === 0 ? (
              <div className="rounded-lg border p-4 text-center text-sm text-muted-foreground">Todavia no hay servicios cargados.</div>
            ) : (
              services.map((service) => (
                <div key={service.id} className="rounded-lg border p-4 shadow-sm">
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
