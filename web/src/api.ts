import type { GameState, RoomView } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function authHeaders(): HeadersInit {
  const tg = window.Telegram?.WebApp;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  } else {
    const params = new URLSearchParams(window.location.search);
    headers["X-Dev-User"] = params.get("devName") || "Dev Player";
    headers["X-Dev-User-Id"] = params.get("devId") || "dev-user";
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export function createGame(bots: number): Promise<GameState> {
  return request<GameState>("/api/games", {
    method: "POST",
    body: JSON.stringify({ bots }),
  });
}

export function getGame(id: string): Promise<GameState> {
  return request<GameState>(`/api/games/${id}`);
}

export function sendAction(id: string, type: "roll" | "bank"): Promise<GameState> {
  return request<GameState>(`/api/games/${id}/actions`, {
    method: "POST",
    body: JSON.stringify({ type }),
  });
}

export function createRoom(bots: number, maxHumans: number): Promise<RoomView> {
  return request<RoomView>("/api/rooms", {
    method: "POST",
    body: JSON.stringify({ bots, max_humans: maxHumans }),
  });
}

export function joinRoom(code: string): Promise<RoomView> {
  return request<RoomView>(`/api/rooms/${encodeURIComponent(code.trim().toUpperCase())}/join`, {
    method: "POST",
  });
}

export function startRoom(code: string): Promise<RoomView> {
  return request<RoomView>(`/api/rooms/${encodeURIComponent(code)}/start`, {
    method: "POST",
  });
}

export function getRoom(code: string): Promise<RoomView> {
  return request<RoomView>(`/api/rooms/${encodeURIComponent(code)}`);
}

export function currentUserId(): string {
  const tg = window.Telegram?.WebApp;
  const fromTg = tg?.initDataUnsafe?.user?.id;
  if (fromTg != null) return String(fromTg);
  const params = new URLSearchParams(window.location.search);
  return params.get("devId") || "dev-user";
}
