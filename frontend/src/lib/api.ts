import { goto } from '$app/navigation';
import type {
  ActiveIncidentState,
  Fleet,
  Guardrail,
  Host,
  Incident,
  IncidentEvent,
  Learning,
  PaginatedIncidents,
  Service,
  TeamMember,
  User,
  UserSettings,
} from './types';
import { currentUser } from './auth';

const API_BASE = '/api/v1';

function idempotencyKey(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: string
  ) {
    super(`${status}: ${body}`);
    this.name = 'ApiError';
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  if (!res.ok) {
    let text: string;
    try {
      text = await res.text();
    } catch {
      text = res.statusText;
    }
    // Session expired / not logged in: bounce to login (except for the
    // login call itself, which surfaces the error on the form).
    if (res.status === 401 && !path.startsWith('/auth/')) {
      currentUser.set(null);
      goto('/login');
    }
    throw new ApiError(res.status, text);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

export const api = {
  auth: {
    setupStatus: () =>
      request<{ needs_setup: boolean; token_required: boolean }>('/auth/setup-status'),
    setup: (email: string, name: string, password: string, token?: string) =>
      request<User>('/auth/setup', {
        method: 'POST',
        body: JSON.stringify({ email, name, password, token: token || null }),
      }),
    login: (email: string, password: string) =>
      request<User>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    logout: () => request<void>('/auth/logout', { method: 'POST' }),
  },

  team: {
    list: () => request<TeamMember[]>('/users'),
    create: (email: string, name: string, password: string) =>
      request<TeamMember>('/users', {
        method: 'POST',
        body: JSON.stringify({ email, name, password }),
      }),
    delete: (id: string) => request<void>(`/users/${id}`, { method: 'DELETE' }),
  },

  me: () => request<User>('/me'),
  updateMe: (patch: { name?: string; phone?: string }) =>
    request<User>('/me', {
      method: 'PATCH',
      body: JSON.stringify(patch),
      headers: { 'Idempotency-Key': idempotencyKey() },
    }),

  settings: {
    get: () => request<UserSettings>('/me/settings'),
    update: (patch: Partial<UserSettings>) =>
      request<UserSettings>('/me/settings', {
        method: 'PATCH',
        body: JSON.stringify(patch),
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
  },

  services: {
    list: () => request<Service[]>('/services'),
    createUrl: (name: string, health_check_url: string) =>
      request<Service>('/services', {
        method: 'POST',
        body: JSON.stringify({ name, method: 'url', health_check_url }),
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
    setWatchOnly: (id: string, watch_only: boolean) =>
      request<Service>(`/services/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ watch_only }),
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
    delete: (id: string) =>
      request<void>(`/services/${id}`, {
        method: 'DELETE',
      }),
  },

  fleet: {
    get: (windowHours = 168) => request<Fleet>(`/fleet?window_hours=${windowHours}`),
  },

  hosts: {
    list: () => request<Host[]>('/hosts'),
    create: (name: string) =>
      request<Host & { token: string }>('/hosts', {
        method: 'POST',
        body: JSON.stringify({ name }),
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
    delete: (id: string) =>
      request<void>(`/hosts/${id}`, {
        method: 'DELETE',
      }),
    setAutonomy: (id: string, autonomy: 'auto_fix' | 'ask_first' | null) =>
      request<Host>(`/hosts/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ autonomy }),
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
    rotateToken: (id: string) =>
      request<Host>(`/hosts/${id}/rotate-token`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
    scriptUrl: () => `${API_BASE}/agent/script`,
  },

  incidents: {
    list: (cursor?: string, limit = 20) =>
      request<PaginatedIncidents>(
        `/incidents?${cursor ? `cursor=${cursor}&` : ''}limit=${limit}`
      ),
    get: (id: string, include?: string[]) =>
      request<Incident>(
        `/incidents/${id}${include ? `?include=${include.join(',')}` : ''}`
      ),
    events: (id: string) => request<IncidentEvent[]>(`/incidents/${id}/events`),
    approve: (id: string) =>
      request<ActiveIncidentState>(`/incidents/${id}/approve`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
    takeOver: (id: string) =>
      request<ActiveIncidentState>(`/incidents/${id}/take-over`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
    resolve: (id: string) =>
      request<ActiveIncidentState>(`/incidents/${id}/resolve`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
    handBack: (id: string) =>
      request<ActiveIncidentState>(`/incidents/${id}/hand-back`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
  },

  learnings: {
    list: () => request<Learning[]>('/learnings'),
  },

  guardrails: {
    list: () => request<Guardrail[]>('/guardrails'),
    update: (key: string, value: boolean) =>
      request<Guardrail>(`/guardrails/${key}`, {
        method: 'PATCH',
        body: JSON.stringify({ value }),
        headers: { 'Idempotency-Key': idempotencyKey() },
      }),
  },

  simulate: () =>
    request<ActiveIncidentState>('/simulate', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey() },
    }),
};
