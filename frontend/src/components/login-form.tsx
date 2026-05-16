"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Loader2, LogIn, ShieldCheck } from "lucide-react";

import { MobileRoleNav } from "@/components/mobile-role-nav";
import { getStoredAuth, loginWithPassword, roleHome } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const demoUsers = [
  { username: "demo_admin", role: "Admin", target: "/admin" },
  { username: "tech_carlos", role: "Tecnico", target: "/technician" },
  { username: "demo_arbiter", role: "Arbitro", target: "/arbiter" },
];

export function LoginForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("Ingresa con tu usuario para abrir el panel correspondiente a tu rol.");

  useEffect(() => {
    const session = getStoredAuth();
    if (session) {
      setMessage(`Sesion activa como ${session.user.username}. Puedes continuar a tu dashboard.`);
    }
  }, []);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    try {
      const session = await loginWithPassword(username, password);
      router.push(roleHome(session.user.role));
    } catch {
      setMessage("No se pudo iniciar sesion. Revisa usuario, clave y backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-5 py-10">
      <Card className="w-full max-w-md shadow-xl">
        <CardHeader className="space-y-4">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200">
            <ShieldCheck className="size-6" />
          </div>
          <div>
            <Badge variant="secondary">SubasTech access</Badge>
            <CardTitle className="mt-3 text-3xl">Iniciar sesion</CardTitle>
            <CardDescription className="mt-2">JWT real conectado al backend Django.</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submitLogin}>
            <div className="space-y-2">
              <Label htmlFor="username">Usuario</Label>
              <Input id="username" value={username} onChange={(event) => setUsername(event.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Contrasena</Label>
              <Input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
            </div>
            <Button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700" disabled={loading}>
              {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <LogIn className="mr-2 size-4" />}
              Entrar
            </Button>
            <p className="text-sm text-muted-foreground">{message}</p>
          </form>
          <div className="mt-6 space-y-3">
            <p className="text-sm font-medium">Usuarios demo</p>
            <div className="grid gap-2 sm:grid-cols-3">
              {demoUsers.map((user) => (
                <Button
                  key={user.username}
                  type="button"
                  variant="outline"
                  className="h-auto flex-col items-start gap-1 p-3 text-left"
                  onClick={() => {
                    setUsername(user.username);
                    setPassword("Subastech123!");
                    setMessage(`Listo: ${user.username}. Presiona Entrar para abrir ${user.target}.`);
                  }}
                >
                  <span>{user.role}</span>
                  <span className="text-xs text-muted-foreground">{user.username}</span>
                </Button>
              ))}
            </div>
          </div>
          <div className="mt-6 grid gap-2 text-sm text-muted-foreground">
            <Link className="hover:text-foreground" href="/demo">Ver guia demo</Link>
            <Link className="hover:text-foreground" href="/technician">Ir a panel tecnico</Link>
            <Link className="hover:text-foreground" href="/admin">Ir a panel admin</Link>
            <Link className="hover:text-foreground" href="/arbiter">Ir a panel arbitro</Link>
          </div>
        </CardContent>
      </Card>
      <MobileRoleNav />
    </main>
  );
}
