import type { TeamTask, TeamStandup } from "./types";

const API_BASE = "/api";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error ${response.status}: ${error}`);
  }
  return response.json();
}

async function authedFetch<T>(path: string, options?: RequestInit & { signal?: AbortSignal }): Promise<T> {
  const { createClient } = await import("./supabase/client");
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const headers = new Headers(options?.headers || {});
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers, signal: options?.signal });
  if (response.status === 401) {
    throw new Error("auth required");
  }
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API ${response.status}: ${error}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const authedApi = {
  listTeamTasks: (params?: { status?: string; assignee?: string; priority?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.assignee) q.set("assignee", params.assignee);
    if (params?.priority) q.set("priority", params.priority);
    const qs = q.toString();
    return authedFetch<{ items: TeamTask[]; count: number }>(`/team/tasks${qs ? `?${qs}` : ""}`);
  },
  createTeamTask: (body: {
    title: string; description?: string; assignee: string;
    created_by?: string; priority?: string; category?: string; reference_url?: string;
  }) =>
    authedFetch<TeamTask>("/team/tasks", { method: "POST", body: JSON.stringify(body) }),
  updateTeamTask: (id: string, body: {
    status?: string; priority?: string; output?: string; review_notes?: string; assignee?: string;
  }) =>
    authedFetch<TeamTask>(`/team/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  getReviewQueue: () =>
    authedFetch<{ items: TeamTask[]; count: number }>("/team/tasks/queue"),
  getTaskStats: () =>
    authedFetch<{ by_status: Record<string, number>; by_assignee: Record<string, number>; total: number }>("/team/tasks/stats"),
  listStandups: (agentRole?: string, limit = 20) => {
    const q = new URLSearchParams();
    if (agentRole) q.set("agent_role", agentRole);
    q.set("limit", String(limit));
    return authedFetch<{ items: TeamStandup[]; count: number }>(`/team/standups?${q.toString()}`);
  },
  createStandup: (body: {
    agent_role: string; summary: string; blockers?: string; next_actions?: string;
  }) =>
    authedFetch<TeamStandup>("/team/standups", { method: "POST", body: JSON.stringify(body) }),
};