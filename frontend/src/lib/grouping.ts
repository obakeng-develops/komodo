import type { Incident, Service } from './types';

export interface ServerGroup {
	name: string; // host name, or a label for hostless (URL) checks
	services: Service[];
	down: number;
	degraded: number;
}

const HOSTLESS = 'URL checks';

// The "server" a service is grouped under: the agent host for agent/docker
// checks, the Fly app for fly machines (their natural grouping), and the
// shared "URL checks" bucket for hostless url checks. See #78.
function serverKey(s: Service): string {
	if (s.method === 'fly') return s.fly_app ?? 'Fly';
	return s.host_name ?? HOSTLESS;
}

// Group services by the server they run on, unhealthiest server first.
export function groupByServer(services: Service[]): ServerGroup[] {
	const byName = new Map<string, Service[]>();
	for (const s of services) {
		const key = serverKey(s);
		const list = byName.get(key) ?? [];
		list.push(s);
		byName.set(key, list);
	}
	return [...byName.entries()]
		.map(([name, svcs]) => ({
			name,
			services: svcs,
			down: svcs.filter((s) => s.status === 'down').length,
			degraded: svcs.filter((s) => s.status === 'degraded').length,
		}))
		.sort((a, b) => b.down - a.down || b.degraded - a.degraded || a.name.localeCompare(b.name));
}

export function serverRollup(g: ServerGroup): string {
	if (g.down) return `${g.down} down`;
	if (g.degraded) return `${g.degraded} degraded`;
	return 'all healthy';
}

export interface IncidentGroup {
	service_id: string;
	name: string; // service/machine name
	incidents: Incident[];
}

// Group incidents by service (machine), most-recently-active group first; the
// incidents within a group keep their input order (newest first). Grouping only
// spans the incidents passed in — i.e. the pages loaded so far. See #76.
export function groupByService(incidents: Incident[]): IncidentGroup[] {
	const byId = new Map<string, Incident[]>();
	for (const inc of incidents) {
		const list = byId.get(inc.service_id) ?? [];
		list.push(inc);
		byId.set(inc.service_id, list);
	}
	const recency = (list: Incident[]) =>
		Math.max(...list.map((i) => new Date(i.started_at).getTime() || 0));
	return [...byId.entries()]
		.map(([service_id, list]) => ({
			service_id,
			name: list[0].service_name ?? service_id,
			incidents: list,
		}))
		.sort((a, b) => recency(b.incidents) - recency(a.incidents));
}
