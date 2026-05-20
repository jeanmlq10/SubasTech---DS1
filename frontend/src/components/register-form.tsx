"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Loader2, UserPlus } from "lucide-react";

import { loginWithPassword, registerUser, roleHome } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const TECHNICIAN_PROFESSIONS = [
  { value: "electrician", label: "Electricista" },
  { value: "plumber", label: "Plomero" },
  { value: "locksmith", label: "Cerrajero" },
  { value: "general-handyman", label: "Mantenimiento general" },
];

const TECHNICIAN_ROLE_STORAGE_KEY = "subastech.technicianProfession";

export function RegisterForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"client" | "technician">("client");
  const [technicianProfession, setTechnicianProfession] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("Crea tu cuenta para acceder a tu dashboard personal.");

  const isTechnician = role === "technician";

  useEffect(() => {
    if (!isTechnician) {
      setTechnicianProfession("");
    }
  }, [isTechnician]);

  async function submitRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("Creando tu cuenta...");

    try {
      await registerUser({
        username,
        email: isTechnician ? undefined : email,
        password,
        role,
      });
      const session = await loginWithPassword(username, password);
      if (typeof window !== "undefined") {
        if (isTechnician && technicianProfession) {
          window.localStorage.setItem(TECHNICIAN_ROLE_STORAGE_KEY, technicianProfession);
        } else {
          window.localStorage.removeItem(TECHNICIAN_ROLE_STORAGE_KEY);
        }
      }
      router.push(roleHome(session.user.role));
    } catch (error) {
      const detail = error instanceof Error ? error.message : "No se pudo completar el registro.";
      setMessage(detail);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-purple-900 to-slate-950">
      <div className="relative flex min-h-screen flex-col items-center justify-center px-4 py-8 sm:px-6 lg:px-8">
        <div className="w-full max-w-md">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-8 shadow-2xl backdrop-blur-md">
            <div className="mb-6 space-y-3 text-center">
              <div className="flex justify-center">
                <div className="inline-flex size-14 items-center justify-center rounded-full bg-gradient-to-br from-orange-400 to-rose-500 text-white shadow-lg">
                  <UserPlus className="size-7" />
                </div>
              </div>
              <h1 className="text-3xl font-bold text-white">Regístrate</h1>
              <p className="text-sm text-purple-200">Completa el formulario para crear tu cuenta</p>
            </div>

            <form className="space-y-4" onSubmit={submitRegister}>
              <div className="space-y-2">
                <Label htmlFor="role" className="text-white">
                  Tipo de cuenta
                </Label>
                <select
                  id="role"
                  value={role}
                  onChange={(event) => setRole(event.target.value as "client" | "technician")}
                  className="flex h-9 w-full rounded-md border border-white/20 bg-white/10 px-3 py-1 text-sm text-white"
                >
                  <option value="client" className="text-slate-900">
                    Cliente
                  </option>
                  <option value="technician" className="text-slate-900">
                    Técnico
                  </option>
                </select>
              </div>

              {isTechnician && (
                <div className="space-y-2">
                  <Label htmlFor="technician-profession" className="text-white">
                    Rol técnico
                  </Label>
                  <select
                    id="technician-profession"
                    value={technicianProfession}
                    onChange={(event) => setTechnicianProfession(event.target.value)}
                    className="flex h-9 w-full rounded-md border border-white/20 bg-white/10 px-3 py-1 text-sm text-white"
                    required
                  >
                    <option value="" className="text-slate-900">
                      Selecciona tu profesión
                    </option>
                    {TECHNICIAN_PROFESSIONS.map((profession) => (
                      <option key={profession.value} value={profession.value} className="text-slate-900">
                        {profession.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="username" className="text-white">
                  Usuario
                </Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  className="border-white/20 bg-white/10 text-white placeholder:text-white/50"
                  placeholder="tu_usuario"
                  required
                />
              </div>

              {!isTechnician && (
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-white">
                    Correo
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="border-white/20 bg-white/10 text-white placeholder:text-white/50"
                    placeholder="tu@correo.com"
                    required
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="password" className="text-white">
                  Contraseña
                </Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="border-white/20 bg-white/10 text-white placeholder:text-white/50"
                  placeholder="Mínimo 8 caracteres"
                  minLength={8}
                  required
                />
              </div>

              <Button
                type="submit"
                className="w-full bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600"
                disabled={loading}
              >
                {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <UserPlus className="mr-2 size-4" />}
                Crear cuenta
              </Button>
              {message && <p className="text-sm text-purple-100">{message}</p>}
            </form>

            <div className="mt-6 border-t border-white/10 pt-4 text-center text-xs text-purple-200">
              <p>
                ¿Ya tienes cuenta?{" "}
                <Link href="/login" className="text-orange-400 hover:text-orange-300">
                  Inicia sesión
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
