<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fade, fly } from 'svelte/transition';
	import { api } from '$lib/api';
	import { activeIncident, lastIncidentCreated } from '$lib/stream';
	import IncidentCard from '$lib/components/IncidentCard.svelte';
	import type { Incident, PaginatedIncidents } from '$lib/types';

	let incidents: Incident[] = [];
	let hasMore = false;
	let nextCursor: string | null = null;
	let loading = false;
	let openId: string | null = null;

	onMount(() => {
		load();
	});

	$: if ($lastIncidentCreated) {
		load();
	}

	async function load(cursor?: string) {
		loading = true;
		try {
			const res: PaginatedIncidents = await api.incidents.list(cursor);
			if (cursor) {
				incidents = [...incidents, ...res.data];
			} else {
				incidents = res.data;
			}
			hasMore = res.has_more;
			nextCursor = res.next_cursor;
		} finally {
			loading = false;
		}
	}

	function loadMore() {
		if (nextCursor) load(nextCursor);
	}

	function activeText() {
		if (!$activeIncident) return '';
		if ($activeIncident.view === 'asking') {
			return `${$activeIncident.service_name} is down — waiting for your approval to restart.`;
		}
		if ($activeIncident.view === 'takeover') {
			return `${$activeIncident.service_name} is down — you're handling this one.`;
		}
		return `${$activeIncident.service_name} is down — restarting it now.`;
	}

	function toggleOpen(incident: Incident) {
		openId = openId === incident.id ? null : incident.id;
	}

	$: hasActive = $activeIncident && ['detecting', 'diagnosing', 'fixing', 'verifying', 'asking', 'takeover'].includes($activeIncident.view);
	$: resolvedN = incidents.filter((i) => i.status === 'resolved').length;
	$: tookN = incidents.filter((i) => i.status === 'escalated' || i.status === 'took_over').length;
</script>

<div class="px-10 py-9 pb-20">
	<div class="max-w-[760px] mx-auto">
		<div class="flex justify-between items-baseline">
			<div class="font-serif text-[28px] leading-none text-surface-900 tracking-tight">Incidents</div>
			<div class="font-mono text-[11px] text-surface-500">All incidents · last 30 days</div>
		</div>

		{#if hasActive}
			<div
				class="mt-5 bg-white border border-surface-300 border-l-[3px] border-l-surface-900 rounded-xl px-5 py-4 flex justify-between items-center shadow-sm"
				in:fly={{ y: -10, duration: 250 }}
			>
				<div>
					<div class="font-mono text-[11px] text-surface-900 tracking-widest uppercase">happening now</div>
					<div class="mt-1.5 font-serif text-[19px] leading-snug text-surface-900">{activeText()}</div>
				</div>
				<button
					class="px-4 py-2 rounded-lg bg-surface-900 text-white font-sans font-medium text-[13px] border-none cursor-pointer hover:bg-surface-800 flex-shrink-0"
					on:click={() => goto('/now')}
				>
					Open
				</button>
			</div>
		{/if}

		<div class="mt-6 bg-white border border-surface-300 rounded-2xl shadow-card overflow-hidden">
			{#each incidents as incident (incident.id)}
				<IncidentCard {incident} open={openId === incident.id} on:toggle={() => toggleOpen(incident)} />
			{/each}
			{#if incidents.length === 0 && !loading}
				<div class="px-5 py-8 text-center font-sans text-sm text-surface-500">No incidents yet.</div>
			{/if}
		</div>

		{#if hasMore}
			<div class="mt-4 text-center">
				<button
					class="px-4 py-2 rounded-lg bg-white border border-surface-300 text-surface-700 font-sans text-sm cursor-pointer hover:bg-surface-50 disabled:opacity-50"
					on:click={loadMore}
					disabled={loading}
				>
					{loading ? 'Loading…' : 'Load more'}
				</button>
			</div>
		{/if}

		<div class="mt-4 font-serif text-[13px] leading-relaxed text-surface-500">
			{incidents.length} incidents · {resolvedN} handled without you, {tookN} needed you.
		</div>
	</div>
</div>
