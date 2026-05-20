"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, LogOut, UserCheck } from "lucide-react";

import { API_URL, OnboardingResponse, TechnicianDocument, Zone } from "@/lib/api";
import { clearStoredAuth, restoreSession } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type ApiState = "idle" | "loading" | "success" | "error";

export function TechnicianOnboarding() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [zones, setZones] = useState<Zone[]>([]);
  const [selectedZones, setSelectedZones] = useState<number[]>([]);
  const [bio, setBio] = useState("");
  const [availability, setAvailability] = useState("available");
  const [responseTime, setResponseTime] = useState("30");
  const [documents, setDocuments] = useState<TechnicianDocument[]>([]);
  const [documentType, setDocumentType] = useState<TechnicianDocument["document_type"]>("identity");
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [documentNotes, setDocumentNotes] = useState("");
  const [status, setStatus] = useState<ApiState>("loading");
  const [message, setMessage] = useState("Preparando tu perfil tecnico...");

  const authHeaders = useMemo(
    () => ({
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    }),
    [token],
  );

  const loadInitialData = useCallback(
    async (accessToken: string) => {
      setStatus("loading");
      try {
        const [onboardingResponse, zoneResponse] = await Promise.all([
          fetch(`${API_URL}/technician/onboarding/`, {
            headers: { Authorization: `Bearer ${accessToken}` },
          }),
          fetch(`${API_URL}/zones/`),
        ]);

        if (!onboardingResponse.ok || !zoneResponse.ok) {
          throw new Error("Onboarding bootstrap failed");
        }

        const onboarding = (await onboardingResponse.json()) as OnboardingResponse;
        if (onboarding.onboarding_complete) {
          router.replace("/technician/dashboard");
          return;
        }

        if (onboarding.profile) {
          setBio(onboarding.profile.bio ?? "");
          setAvailability(onboarding.profile.availability_status);
          setResponseTime(String(onboarding.profile.response_time_minutes));
          setSelectedZones(onboarding.profile.zones.map((zone) => zone.id));
          setDocuments(onboarding.profile.documents ?? []);
        }
        setZones((await zoneResponse.json()) as Zone[]);
        setStatus("idle");
        setMessage("Completa tu perfil para activar tu workspace.");
      } catch {
        setStatus("error");
        setMessage("No pudimos cargar el onboarding. Revisa tu sesion e intenta de nuevo.");
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
      await loadInitialData(session.accessToken);
    })();

    return () => {
      mounted = false;
    };
  }, [loadInitialData, router]);

  function logout() {
    clearStoredAuth();
    router.replace("/login");
  }

  function toggleZone(zoneId: number) {
    setSelectedZones((current) =>
      current.includes(zoneId) ? current.filter((id) => id !== zoneId) : [...current, zoneId],
    );
  }

  async function submitOnboarding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      setMessage("Inicia sesion antes de guardar tu onboarding.");
      return;
    }

    setStatus("loading");
    setMessage("Guardando tu perfil...");
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

      setStatus("success");
      router.replace("/technician/dashboard");
    } catch {
      setStatus("error");
      setMessage("No se pudo guardar el onboarding.");
    }
  }

  async function uploadDocument() {
    if (!token || !documentFile) {
      setMessage("Selecciona un archivo antes de subir el documento.");
      return;
    }

    setStatus("loading");
    setMessage("Subiendo documento...");
    try {
      const body = new FormData();
      body.append("document_type", documentType);
      body.append("file", documentFile);
      body.append("notes", documentNotes);

      const response = await fetch(`${API_URL}/technician/documents/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body,
      });
      if (!response.ok) {
        throw new Error("Document upload failed");
      }
      const document = (await response.json()) as TechnicianDocument;
      setDocuments((current) => [document, ...current]);
      setDocumentFile(null);
      setDocumentNotes("");
      setStatus("idle");
      setMessage("Documento enviado para revision.");
    } catch {
      setStatus("error");
      setMessage("No se pudo subir el documento.");
    }
  }

  const isLoading = status === "loading";

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-purple-900 to-slate-950">
      <div className="relative flex min-h-screen items-center justify-center px-4 py-8 sm:px-6 lg:px-8">
        <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-white/5 p-6 shadow-2xl backdrop-blur-md sm:p-8">
          <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-3">
              <div className="inline-flex size-14 items-center justify-center rounded-full bg-gradient-to-br from-orange-400 to-rose-500 text-white shadow-lg">
                <UserCheck className="size-7" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-white">Onboarding tecnico</h1>
                <p className="mt-2 text-sm text-purple-200">{message}</p>
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              className="justify-start text-purple-100 hover:bg-white/10 hover:text-white"
              onClick={logout}
            >
              <LogOut className="mr-2 size-4" />
              Cerrar sesion
            </Button>
          </div>

          <form className="space-y-5" onSubmit={submitOnboarding}>
            <div className="space-y-2">
              <Label htmlFor="bio" className="text-white">
                Bio profesional
              </Label>
              <Textarea
                id="bio"
                value={bio}
                onChange={(event) => setBio(event.target.value)}
                className="min-h-24 border-white/20 bg-white/10 text-white placeholder:text-white/50"
                placeholder="Ej: Electricista residencial con experiencia en emergencias."
                required
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="availability" className="text-white">
                  Disponibilidad
                </Label>
                <select
                  id="availability"
                  value={availability}
                  onChange={(event) => setAvailability(event.target.value)}
                  className="flex h-10 w-full rounded-md border border-white/20 bg-white/10 px-3 py-2 text-sm text-white"
                >
                  <option value="available" className="text-slate-900">
                    Disponible
                  </option>
                  <option value="busy" className="text-slate-900">
                    Ocupado
                  </option>
                  <option value="offline" className="text-slate-900">
                    Offline
                  </option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="responseTime" className="text-white">
                  Respuesta estimada (min)
                </Label>
                <Input
                  id="responseTime"
                  min="1"
                  type="number"
                  value={responseTime}
                  onChange={(event) => setResponseTime(event.target.value)}
                  className="border-white/20 bg-white/10 text-white placeholder:text-white/50"
                  required
                />
              </div>
            </div>

            <div className="space-y-3">
              <Label className="text-white">Zonas de cobertura</Label>
              <div className="grid max-h-80 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
                {zones.length === 0 ? (
                  <p className="rounded-md border border-white/10 bg-white/5 p-3 text-sm text-purple-100">
                    Cargando zonas disponibles...
                  </p>
                ) : (
                  zones.map((zone) => (
                    <label
                      key={zone.id}
                      className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 p-3 text-sm text-purple-50"
                    >
                      <input
                        checked={selectedZones.includes(zone.id)}
                        onChange={() => toggleZone(zone.id)}
                        type="checkbox"
                        className="size-4"
                      />
                      {zone.name}, {zone.city}
                    </label>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <div>
                <h2 className="font-semibold text-white">Documentos de verificacion</h2>
                <p className="mt-1 text-sm text-purple-200">
                  Sube tu documento de identidad o certificaciones. Un administrador los revisara antes de aprobarte.
                </p>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-[180px_1fr]">
                <select
                  value={documentType}
                  onChange={(event) => setDocumentType(event.target.value as TechnicianDocument["document_type"])}
                  className="flex h-10 w-full rounded-md border border-white/20 bg-white/10 px-3 py-2 text-sm text-white"
                >
                  <option value="identity" className="text-slate-900">
                    Identidad
                  </option>
                  <option value="certification" className="text-slate-900">
                    Certificacion
                  </option>
                  <option value="other" className="text-slate-900">
                    Otro
                  </option>
                </select>
                <Input
                  type="file"
                  onChange={(event) => setDocumentFile(event.target.files?.[0] ?? null)}
                  className="border-white/20 bg-white/10 text-white file:text-white"
                />
              </div>
              <Textarea
                value={documentNotes}
                onChange={(event) => setDocumentNotes(event.target.value)}
                className="mt-3 min-h-20 border-white/20 bg-white/10 text-white placeholder:text-white/50"
                placeholder="Notas opcionales para el administrador."
              />
              <Button
                type="button"
                variant="ghost"
                className="mt-3 border border-white/10 text-purple-100 hover:bg-white/10 hover:text-white"
                onClick={() => void uploadDocument()}
                disabled={isLoading || !documentFile}
              >
                Subir documento
              </Button>
              <div className="mt-4 grid gap-2">
                {documents.length === 0 ? (
                  <p className="text-sm text-purple-200">Aun no has subido documentos.</p>
                ) : (
                  documents.map((document) => (
                    <div key={document.id} className="rounded-lg border border-white/10 bg-slate-950/20 p-3 text-sm text-purple-100">
                      <span className="font-medium text-white">{document.document_type}</span> - {document.review_status}
                      {document.admin_notes ? <p className="mt-1 text-purple-200">{document.admin_notes}</p> : null}
                    </div>
                  ))
                )}
              </div>
            </div>

            <Button
              type="submit"
              className="w-full bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600"
              disabled={isLoading || selectedZones.length === 0}
            >
              {isLoading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <UserCheck className="mr-2 size-4" />}
              Completar onboarding
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
