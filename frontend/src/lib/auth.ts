import { API_URL, User } from "@/lib/api";

export type AuthSession = {
  accessToken: string;
  refreshToken: string;
  user: User;
};

const STORAGE_KEY = "subastech.auth";

export function getStoredAuth(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as AuthSession;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function storeAuth(session: AuthSession) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearStoredAuth() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(STORAGE_KEY);
}

async function fetchCurrentUser(accessToken: string): Promise<User> {
  const response = await fetch(`${API_URL}/auth/me/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    throw new Error("Could not load authenticated user");
  }

  return (await response.json()) as User;
}

async function refreshStoredSession(session: AuthSession): Promise<AuthSession> {
  const refreshResponse = await fetch(`${API_URL}/auth/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: session.refreshToken }),
  });

  if (!refreshResponse.ok) {
    throw new Error("Could not refresh session");
  }

  const refreshPayload = (await refreshResponse.json()) as { access: string };
  const user = await fetchCurrentUser(refreshPayload.access);
  const refreshedSession = {
    ...session,
    accessToken: refreshPayload.access,
    user,
  };
  storeAuth(refreshedSession);
  return refreshedSession;
}

export function roleHome(role: User["role"]): string {
  if (role === "technician") {
    return "/technician";
  }
  if (role === "admin") {
    return "/admin";
  }
  if (role === "arbiter") {
    return "/arbiter";
  }
  return "/dashboard";
}

export type RegisterPayload = {
  username: string;
  email?: string;
  password: string;
  role: "client" | "technician";
  technician_trade?: "electrician" | "plumber" | "locksmith" | "general-handyman";
  phone_number?: string;
  address?: string;
};

export async function registerUser(payload: RegisterPayload): Promise<void> {
  const response = await fetch(`${API_URL}/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as Record<string, unknown> | null;
    const detail =
      body && typeof body === "object"
        ? Object.entries(body)
            .map(([key, value]) => {
              if (Array.isArray(value)) {
                return `${key}: ${value.join(", ")}`;
              }
              return `${key}: ${String(value)}`;
            })
            .join(" · ")
        : "No se pudo completar el registro.";
    throw new Error(detail);
  }
}

export async function loginWithPassword(identifier: string, password: string): Promise<AuthSession> {
  const login = identifier.trim();
  const credentialPayload = login.includes("@") ? { email: login, password } : { username: login, password };
  const tokenResponse = await fetch(`${API_URL}/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credentialPayload),
  });

  if (!tokenResponse.ok) {
    throw new Error("Invalid username or password");
  }

  const tokenPayload = (await tokenResponse.json()) as { access: string; refresh: string };
  const user = await fetchCurrentUser(tokenPayload.access);
  const session = {
    accessToken: tokenPayload.access,
    refreshToken: tokenPayload.refresh,
    user,
  };
  storeAuth(session);
  return session;
}

export async function restoreSession(): Promise<AuthSession | null> {
  const session = getStoredAuth();
  if (!session) {
    return null;
  }

  try {
    const user = await fetchCurrentUser(session.accessToken);
    const hydratedSession = { ...session, user };
    storeAuth(hydratedSession);
    return hydratedSession;
  } catch {
    try {
      return await refreshStoredSession(session);
    } catch {
      clearStoredAuth();
      return null;
    }
  }
}
