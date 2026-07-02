<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { isOwner } from '$lib/auth';
	import SegmentedControl from '$lib/components/ui/SegmentedControl.svelte';
	import type { Fleet, FleetService, FleetIncident } from '$lib/types';

	const rollup = (down: number, degraded: number) =>
		down ? `${down} down` : degraded ? `${degraded} degraded` : 'all healthy';

	let fleet: Fleet | null = null;
	let windowHours = 168;
	let loading = true;

	const WINDOWS = [
		{ value: '24', label: '24h' },
		{ value: '168', label: '7d' },
		{ value: '720', label: '30d' }
	];

	onMount(load);

	async function load() {
		loading = true;
		try {
			fleet = await api.fleet.get(windowHours);
		} finally {
			loading = false;
		}
	}

	function setWindow(hours: number) {
		windowHours = hours;
		load();
	}

	async function toggleWatchOnly(svc: FleetService) {
		await api.services.setWatchOnly(svc.id, !svc.watch_only);
		await load();
	}

	async function removeService(svc: FleetService) {
		if (!confirm(`Stop watching ${svc.name}? This removes it and its incident history.`)) return;
		await api.services.delete(svc.id);
		await load();
	}

	// Backend datetimes are naive UTC; parse them as UTC, not local.
	const utc = (s: string) => new Date(/[Z+]/.test(s) ? s : s + 'Z').getTime();

	function dotClass(status: string) {
		if (status === 'down') return 'bg-danger-500';
		if (status === 'degraded') return 'bg-warning-500';
		return 'bg-success-500';
	}

	// Mute the healthy ones to gray so the sub-100% service is the only colored
	// number in a column of all-green rows — easier to spot at a glance.
	function uptimeClass(pct: number) {
		if (pct >= 99.9) return 'text-surface-400';
		if (pct >= 99) return 'text-warning-600 font-medium';
		return 'text-danger-600 font-semibold';
	}

	// Trim noise: "100%" not "100.000%", but keep 2 dp for the imperfect ones.
	const fmtPct = (pct: number) => (pct >= 100 ? '100' : pct.toFixed(2));

	// Status-page strip: one cell per time bucket (hourly for ≤48h, daily beyond),
	// coloured by the worst incident overlapping that bucket. Each cell carries a
	// title so hovering shows the day and how long it was down.
	type Bucket = { worst: 'healthy' | 'degraded' | 'down'; start: number; downMs: number; hourly: boolean };

	function buckets(incidents: FleetIncident[]): Bucket[] {
		const now = Date.now();
		const total = windowHours * 3600 * 1000;
		const start = now - total;
		const hourly = windowHours <= 48;
		const bucketMs = (hourly ? 1 : 24) * 3600 * 1000;
		const count = Math.round(windowHours / (hourly ? 1 : 24));
		const out: Bucket[] = [];
		for (let i = 0; i < count; i++) {
			const bStart = start + i * bucketMs;
			const bEnd = Math.min(bStart + bucketMs, now);
			let worst: Bucket['worst'] = 'healthy';
			let downMs = 0;
			for (const inc of incidents) {
				const s = Math.max(utc(inc.started_at), bStart);
				const e = Math.min(inc.resolved_at ? utc(inc.resolved_at) : now, bEnd);
				if (e <= s) continue;
				if (inc.severity === 'down') {
					worst = 'down';
					downMs += e - s;
				} else if (worst !== 'down') {
					worst = 'degraded';
				}
			}
			out.push({ worst, start: bStart, downMs, hourly });
		}
		return out;
	}

	function bucketColor(worst: Bucket['worst']) {
		if (worst === 'down') return 'bg-danger-500';
		if (worst === 'degraded') return 'bg-warning-500';
		return 'bg-success-500/70';
	}

	function bucketLabel(b: Bucket) {
		const d = new Date(b.start);
		const when = b.hourly
			? d.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric' })
			: d.toLocaleDateString([], { month: 'short', day: 'numeric' });
		if (b.worst === 'healthy') return `${when} · all good`;
		const mins = Math.round(b.downMs / 60000);
		const dur = mins ? ` · ${mins}m down` : '';
		return `${when} · ${b.worst}${dur}`;
	}

	function lastIncidentNote(svc: FleetService) {
		if (!svc.incidents.length) return 'no incidents in window';
		const n = svc.incidents.length;
		return `${n} incident${n === 1 ? '' : 's'} in window`;
	}
</script>

<div class="px-4 sm:px-10 py-7 sm:py-9 pb-20">
	<div class="max-w-[760px] mx-auto">
		<div class="flex flex-wrap items-end justify-between gap-4">
			<div>
				<div class="font-serif text-title leading-none text-surface-900">Fleet</div>
				<div class="mt-2 font-sans text-label leading-relaxed text-surface-500">
					Every server and how it's held up.
				</div>
			</div>
			<SegmentedControl
				options={WINDOWS}
				value={String(windowHours)}
				size="sm"
				on:change={(e) => setWindow(Number(e.detail))}
			/>
		</div>

		{#if loading && !fleet}
			<div class="mt-7 flex flex-col gap-5" aria-hidden="true">
				{#each [0, 1] as _card}
					<div class="bg-white border border-surface-300 rounded-card p-5 shadow-card">
						<div class="flex items-center justify-between pb-3 border-b border-surface-100">
							<div class="h-3 w-32 rounded bg-surface-200 animate-pulse"></div>
							<div class="h-3 w-16 rounded bg-surface-100 animate-pulse"></div>
						</div>
						<div class="mt-4 flex flex-col gap-4">
							{#each [0, 1, 2] as _row}
								<div>
									<div class="flex items-center justify-between">
										<div class="h-3 w-40 rounded bg-surface-200 animate-pulse"></div>
										<div class="h-3 w-10 rounded bg-surface-100 animate-pulse"></div>
									</div>
									<div class="mt-2 h-7 rounded bg-surface-100 animate-pulse"></div>
								</div>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{:else if fleet && fleet.servers.length === 0}
			<div class="mt-8 bg-white border border-surface-300 rounded-card p-6 shadow-card text-center">
				<div class="font-serif text-heading text-surface-900">No servers yet</div>
				<div class="mt-1.5 font-sans text-sm text-surface-500">Add a server and install the agent, or add a URL check to watch.</div>
				<a href="/settings" class="inline-block mt-4 px-4 py-2 rounded-lg bg-surface-900 text-white font-sans font-medium text-label no-underline hover:bg-surface-800">Add a service</a>
			</div>
		{:else if fleet}
			<div class="mt-7 flex flex-col gap-5">
				{#each fleet.servers as server (server.name)}
					<div class="bg-white border border-surface-300 rounded-card p-5 shadow-card">
						<div class="flex items-center justify-between gap-3 pb-3 border-b border-surface-100">
							<div class="font-mono text-label text-surface-900 truncate">{server.name}</div>
							<div class="font-mono text-micro {server.down ? 'text-danger-600' : server.degraded ? 'text-warning-600' : 'text-surface-400'}">
								{rollup(server.down, server.degraded)}
							</div>
						</div>
						<div class="mt-3 flex flex-col gap-3.5">
							{#each server.services as svc (svc.id)}
								<div>
									<div class="flex items-center justify-between gap-3">
										<span class="flex items-center gap-2 min-w-0">
											<span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {dotClass(svc.status)}"></span>
											<span class="font-mono text-label text-surface-800 truncate">{svc.name}</span>
											{#if svc.watch_only}
												<span class="flex-shrink-0 px-1.5 py-0.5 rounded bg-surface-100 text-surface-500 font-sans text-micro">watch-only</span>
											{/if}
										</span>
										<span class="flex items-center gap-3 flex-shrink-0">
											{#if $isOwner}
												<button type="button" on:click={() => toggleWatchOnly(svc)} class="bg-transparent border-none cursor-pointer font-sans text-micro text-surface-500 underline underline-offset-[3px] decoration-surface-300 hover:text-surface-900" title={svc.watch_only ? 'Let Mino act on this again' : 'Watch only. Mino flags it but never restarts it'}>
													{svc.watch_only ? 'allow fixes' : 'pause fixes'}
												</button>
												<button type="button" on:click={() => removeService(svc)} class="bg-transparent border-none cursor-pointer font-sans text-micro text-surface-500 underline underline-offset-[3px] decoration-surface-300 hover:text-danger-600" title="Stop watching this service">remove</button>
											{/if}
											<span class="font-mono text-label {uptimeClass(svc.uptime_pct)}">{fmtPct(svc.uptime_pct)}%</span>
										</span>
									</div>
									<div class="mt-2 flex items-stretch gap-px h-7 rounded overflow-hidden">
										{#each buckets(svc.incidents) as b}
											<span
												class="flex-1 transition-opacity hover:opacity-70 {bucketColor(b.worst)}"
												title={bucketLabel(b)}
											></span>
										{/each}
									</div>
									<div class="mt-1 font-sans text-micro text-surface-400">{lastIncidentNote(svc)}</div>
								</div>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
