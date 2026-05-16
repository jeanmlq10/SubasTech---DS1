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
  return "/";
}

export async function loginWithPassword(username: string, password: string): Promise<AuthSession> {
  const tokenResponse = await fetch(`${API_URL}/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!tokenResponse.ok) {
    throw new Error("Invalid username or password");
  }

  const tokenPayload = (await tokenResponse.json()) as { access: string; refresh: string };
  const userResponse = await fetch(`${API_URL}/auth/me/`, {
    headers: { Authorization: `Bearer ${tokenPayload.access}` },
  });

  if (!userResponse.ok) {
    throw new Error("Could not load authenticated user");
  }

  const session = {
    accessToken: tokenPayload.access,
    refreshToken: tokenPayload.refresh,
    user: (await userResponse.json()) as User,
  };
  storeAuth(session);
  return session;
}
