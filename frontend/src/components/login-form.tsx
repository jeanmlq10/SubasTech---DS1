"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Loader2, LogIn, MessageCircle, Gauge, Calendar, ClipboardList } from "lucide-react";

import { loginWithPassword, restoreSession, roleHome } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const features = [
  {
    title: "Dashboard Personal",
    description: "Accede a tu panel personalizado donde podrás ver todas tus solicitudes de servicio y citas agendadas en tiempo real.",
    icon: Calendar,
  },
  {
    title: "Solicitudes en Vivo",
    description: "Gestiona todas tus solicitudes activas, monitorea el estado de cada una y recibe actualizaciones instantáneas.",
    icon: ClipboardList,
  },
  {
    title: "Citas Agendadas",
    description: "Visualiza todas tus citas programadas con detalles completos: técnico, horario, servicio y ubicación.",
    icon: MessageCircle,
  },
  {
    title: "Recomendaciones por IA",
    description: "Recibe recomendaciones personalizadas de técnicos verificados basadas en disponibilidad, zona y reputación.",
    icon: Gauge,
  },
];

export function LoginForm() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("Ingresa con tu correo o usuario para abrir el panel correspondiente a tu rol.");

  useEffect(() => {
    let mounted = true;

    void (async () => {
      const session = await restoreSession();
      if (mounted && session) {
        setMessage(`Sesion activa como ${session.user.username}. Puedes continuar a tu dashboard.`);
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    try {
      const session = await loginWithPassword(identifier, password);
      router.push(roleHome(session.user.role));
    } catch {
      setMessage("No se pudo iniciar sesion. Revisa correo/usuario, clave y backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-purple-900 to-slate-950">
      <div className="pointer-events-none fixed inset-0">
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice">
          <defs>
            <radialGradient id="sunGradient" cx="30%" cy="30%">
              <stop offset="0%" stopColor="#ffa66d" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#ff7a4d" stopOpacity="0.4" />
            </radialGradient>
          </defs>
          <circle cx="200" cy="150" r="80" fill="url(#sunGradient)" />
          {[...Array(15)].map((_, i) => (
            <circle
              key={i}
              cx={Math.random() * 1000}
              cy={Math.random() * 300}
              r={Math.random() * 2}
              fill="white"
              opacity={Math.random() * 0.5 + 0.3}
            />
          ))}
        </svg>
      </div>

      <div className="relative flex min-h-screen flex-col items-center justify-center px-4 py-8 sm:px-6 lg:px-8">
        <div className="w-full max-w-md space-y-8">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-8 backdrop-blur-md shadow-2xl">
            <div className="mb-6 space-y-3 text-center">
              <div className="flex justify-center">
                <div className="inline-flex size-14 items-center justify-center rounded-full bg-gradient-to-br from-orange-400 to-rose-500 text-white shadow-lg">
                  <LogIn className="size-7" />
                </div>
              </div>
              <h1 className="text-3xl font-bold text-white">Login</h1>
              <p className="text-sm text-purple-200">Accede a tu dashboard con tu correo o usuario</p>
            </div>

            <form className="space-y-4" onSubmit={submitLogin}>
              <div className="space-y-2">
                <Label htmlFor="identifier" className="text-white">
                  Correo o usuario
                </Label>
                <Input
                  id="identifier"
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  className="border-white/20 bg-white/10 text-white placeholder:text-white/50"
                  placeholder="tu@correo.com o tu_usuario"
                  required
                />
              </div>
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
                  placeholder="••••••••"
                  required
                />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="remember" className="size-4 rounded" />
                <label htmlFor="remember" className="text-sm text-purple-100">
                  Recuérdame
                </label>
              </div>
              <Button
                type="submit"
                className="w-full bg-gradient-to-r from-orange-400 to-rose-500 font-semibold text-white hover:from-orange-500 hover:to-rose-600"
                disabled={loading}
              >
                {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <LogIn className="mr-2 size-4" />}
                Entrar
              </Button>
              {message && <p className="text-sm text-purple-100">{message}</p>}
            </form>

            <div className="mt-6 border-t border-white/10 pt-4 text-center text-xs text-purple-200">
              <p>
                ¿No tienes cuenta?{" "}
                <Link href="/register" className="text-orange-400 hover:text-orange-300">
                  Regístrate
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="relative z-10 bg-gradient-to-b from-slate-950 to-slate-900 px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <div className="mb-16 text-center">
            <h2 className="mb-4 text-3xl font-bold text-white sm:text-4xl">Bienvenido a SubasTech</h2>
            <p className="text-lg text-purple-200">
              Una plataforma moderna para conectar clientes con técnicos confiables
            </p>
          </div>

          <div className="space-y-12">
            <div className="rounded-2xl border border-purple-500/20 bg-gradient-to-br from-purple-500/10 to-pink-500/10 p-8 backdrop-blur">
              <div className="flex items-start gap-4">
                <div className="flex size-12 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-orange-400 to-rose-500">
                  <Calendar className="size-6 text-white" />
                </div>
                <div>
                  <h3 className="mb-2 text-xl font-semibold text-white">Tu Dashboard Personal</h3>
                  <p className="text-purple-100">
                    Una vez inicies sesión, accede a tu dashboard personalizado donde podrás ver todas tus solicitudes
                    activas y citas agendadas. Monitorea el estado de cada servicio en tiempo real y recibe notificaciones
                    instantáneas de actualizaciones importantes.
                  </p>
                </div>
              </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              {features.map((feature, idx) => {
                const Icon = feature.icon;
                return (
                  <div
                    key={idx}
                    className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-6 backdrop-blur transition-colors hover:bg-purple-500/10"
                  >
                    <div className="mb-3 flex size-10 items-center justify-center rounded-lg bg-gradient-to-br from-orange-400/80 to-rose-500/80">
                      <Icon className="size-5 text-white" />
                    </div>
                    <h4 className="mb-2 font-semibold text-white">{feature.title}</h4>
                    <p className="text-sm text-purple-200">{feature.description}</p>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-16 border-t border-white/10 pt-8 text-center text-sm text-purple-300">
            <p>© 2026 SubasTech. Todos los derechos reservados.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
