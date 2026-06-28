import { writable } from 'svelte/store';
import type { ActiveIncidentState, Service } from './types';

export const activeIncident = writable<ActiveIncidentState | null>(null);
export const lastIncidentCreated = writable<string | null>(null);
export const lastLearningCreated = writable<{ service_id: string; rule: string } | null>(null);
export const servicesNeedRefresh = writable<number>(0);
export const logLines = writable<string[]>([]);
export const servicesStore = writable<Service[]>([]);

let eventSource: EventSource | null = null;
let reconnectDelay = 1000;

export function connectStream() {
  if (eventSource) return;

  eventSource = new EventSource('/api/v1/stream');
  reconnectDelay = 1000;

  eventSource.addEventListener('incident_state', (e) => {
    const data = JSON.parse(e.data);
    activeIncident.set(data);
  });

  eventSource.addEventListener('log_lines', (e) => {
    const data = JSON.parse(e.data);
    if (Array.isArray(data.lines)) {
      logLines.update((lines) => [...lines, ...data.lines]);
    }
  });

  eventSource.addEventListener('incident_created', (e) => {
    const data = JSON.parse(e.data);
    lastIncidentCreated.set(data.incident_id);
  });

  eventSource.addEventListener('learning_created', (e) => {
    const data = JSON.parse(e.data);
    lastLearningCreated.set(data);
  });

  eventSource.addEventListener('services_changed', () => {
    servicesNeedRefresh.update((n) => n + 1);
  });

  eventSource.addEventListener('ping', () => {
    // keepalive
  });

  eventSource.onerror = () => {
    disconnectStream();
    setTimeout(connectStream, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  };
}

export function disconnectStream() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}
