<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { isOwner } from '$lib/auth';
	import type { Fleet, FleetService, FleetIncident } from '$lib/types';

	const rollup = (down: number, degraded: number) =>
		down ? `${down} down` : degraded ? `${degraded} degraded` : 'all healthy';

	let fleet: Fleet | null = null;
	let windowHours = 168;
	let loading = true;

	const WINDOWS = [
		{ label: '24h', hours: 24 },
		{ label: '7d', hours: 168 },
		{ label: '30d', hours: 720 }
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

	function uptimeClass(pct: number) {
		if (pct >= 99.9) return 'text-success-600';
		if (pct >= 99) return 'text-warning-600';
		return 'text-danger-600';
	}

	// Down/degraded stretches positioned across the window, status-page style.
	function segments(incidents: FleetIncident[]) {
		const now = Date.now();
		const start = now - windowHours * 3600 * 1000;
		const span = now - start;
		return incidents
			.map((inc) => {
				const s = Math.max(utc(inc.started_at), start);
				const e = Math.min(inc.resolved_at ? utc(inc.resolved_at) : now, now);
				return {
					left: ((s - start) / span) * 100,
					width: Math.max(((e - s) / span) * 100, 0.6),
					severity: inc.severity
				};
			})
			.filter((seg) => seg.width > 0 && seg.left < 100);
	}

	function lastIncidentNote(svc: FleetService) {
		if (!svc.incidents.length) return 'no incidents in window';
		const n = svc.incidents.length;
		return `${n} incident${n === 1 ? '' : 's'} in window`;
	}
</script>

<div class="px-10 py-9 pb-20">
	<div class="max-w-[760px] mx-auto">
		<div class="flex items-end justify-between gap-4">
			<div>
				<div class="font-serif text-[28px] leading-none text-surface-900 tracking-tight">Fleet</div>
				<div class="mt-2 font-sans text-sm leading-relaxed text-surface-500">
					Every server and how it's held up.
				</div>
			</div>
			<div class="inline-flex rounded-lg border border-surface-300 overflow-hidden flex-shrink-0">
				{#each WINDOWS as w}
					<button
						type="button"
						on:click={() => setWindow(w.hours)}
						class="px-3 py-1.5 font-mono text-[12px] border-none cursor-pointer {windowHours === w.hours ? 'bg-surface-900 text-white' : 'bg-white text-surface-600 hover:bg-surface-50'}"
					>{w.label}</button>
				{/each}
			</div>
		</div>

		{#if loading && !fleet}
			<div class="mt-8 font-sans text-sm text-surface-500">Loading…</div>
		{:else if fleet && fleet.servers.length === 0}
			<div class="mt-8 font-sans text-sm text-surface-500">
				No servers yet. Add one in <a class="underline" href="/settings">Settings</a> and run the agent.
			</div>
		{:else if fleet}
			<div class="mt-7 flex flex-col gap-5">
				{#each fleet.servers as server (server.name)}
					<div class="bg-white border border-surface-300 rounded-2xl p-5 shadow-sm">
						<div class="flex items-center justify-between gap-3 pb-3 border-b border-surface-100">
							<div class="font-mono text-[13px] text-surface-900 truncate">{server.name}</div>
							<div class="font-mono text-[11px] {server.down ? 'text-danger-600' : server.degraded ? 'text-warning-600' : 'text-surface-400'}">
								{rollup(server.down, server.degraded)}
							</div>
						</div>
						<div class="mt-3 flex flex-col gap-3.5">
							{#each server.services as svc (svc.id)}
								<div>
									<div class="flex items-center justify-between gap-3">
										<span class="flex items-center gap-2 min-w-0">
											<span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {dotClass(svc.status)}"></span>
											<span class="font-mono text-[13px] text-surface-800 truncate">{svc.name}</span>
											{#if svc.watch_only}
												<span class="flex-shrink-0 px-1.5 py-0.5 rounded bg-surface-100 text-surface-500 font-sans text-[10px]">watch-only</span>
											{/if}
										</span>
										<span class="flex items-center gap-3 flex-shrink-0">
											{#if $isOwner}
												<button type="button" on:click={() => toggleWatchOnly(svc)} class="bg-transparent border-none cursor-pointer font-sans text-[11px] text-surface-400 hover:text-surface-700" title={svc.watch_only ? 'Let Komodo act on this again' : 'Watch only — Komodo flags it but never restarts it'}>
													{svc.watch_only ? 'allow fixes' : 'watch-only'}
												</button>
												<button type="button" on:click={() => removeService(svc)} class="bg-transparent border-none cursor-pointer font-sans text-[11px] text-surface-400 hover:text-danger-600" title="Stop watching this service">remove</button>
											{/if}
											<span class="font-mono text-[12px] {uptimeClass(svc.uptime_pct)}">{svc.uptime_pct}%</span>
										</span>
									</div>
									<div class="mt-1.5 relative h-2 rounded-full bg-success-500/30 overflow-hidden">
										{#each segments(svc.incidents) as seg}
											<span
												class="absolute top-0 h-full {seg.severity === 'down' ? 'bg-danger-500' : 'bg-warning-500'}"
												style="left:{seg.left}%;width:{seg.width}%"
											></span>
										{/each}
									</div>
									<div class="mt-1 font-sans text-[11px] text-surface-400">{lastIncidentNote(svc)}</div>
								</div>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
