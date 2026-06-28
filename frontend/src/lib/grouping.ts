import type { Service } from './types';

export interface ServerGroup {
	name: string; // host name, or a label for hostless (URL) checks
	services: Service[];
	down: number;
	degraded: number;
}

const HOSTLESS = 'URL checks';

// Group services by the server (host) they run on, unhealthiest server first.
export function groupByServer(services: Service[]): ServerGroup[] {
	const byName = new Map<string, Service[]>();
	for (const s of services) {
		const key = s.host_name ?? HOSTLESS;
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
