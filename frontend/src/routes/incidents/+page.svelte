<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fade, fly, slide } from 'svelte/transition';
	import { api } from '$lib/api';
	import { activeIncident, lastIncidentCreated } from '$lib/stream';
	import IncidentCard from '$lib/components/IncidentCard.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import { groupByService, type IncidentGroup } from '$lib/grouping';
	import { ago } from '$lib/time';
	import type { Incident, PaginatedIncidents } from '$lib/types';

	let incidents: Incident[] = [];
	let hasMore = false;
	let nextCursor: string | null = null;
	let loading = true;
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

	// Groups start collapsed; expanded holds the service_ids the user opened.
	// Keyed by service_id so it survives `groups` recomputing after "Load more".
	let expanded = new Set<string>();
	function toggleGroup(id: string) {
		expanded.has(id) ? expanded.delete(id) : expanded.add(id);
		expanded = new Set(expanded);
	}
	function expandAll() {
		expanded = new Set(groups.map((g) => g.service_id));
	}
	function collapseAll() {
		expanded = new Set();
	}

	// Still needs a human: an incident that's open, escalated, or handed over.
	const needsAttention = (g: IncidentGroup) =>
		g.incidents.some((i) => ['open', 'escalated', 'took_over'].includes(i.status));

	$: hasActive = $activeIncident && ['detecting', 'diagnosing', 'fixing', 'verifying', 'asking', 'takeover'].includes($activeIncident.view);
	$: groups = groupByService(incidents);
	$: allExpanded = groups.length > 0 && groups.every((g) => expanded.has(g.service_id));
	$: resolvedN = incidents.filter((i) => i.status === 'resolved').length;
	$: tookN = incidents.filter((i) => i.status === 'escalated' || i.status === 'took_over').length;
</script>

<div class="px-4 sm:px-10 py-7 sm:py-9 pb-20">
	<div class="max-w-[760px] mx-auto">
		<div class="flex flex-wrap gap-2 justify-between items-baseline">
			<div class="font-serif text-title leading-none text-surface-900 tracking-tight">Incidents</div>
			<div class="inline-flex items-center gap-3">
				{#if groups.length > 0}
					<button
						type="button"
						on:click={() => (allExpanded ? collapseAll() : expandAll())}
						class="bg-transparent border-none cursor-pointer font-mono text-micro text-surface-500 underline underline-offset-[3px] decoration-surface-300 hover:text-surface-900"
					>
						{allExpanded ? 'collapse all' : 'expand all'}
					</button>
				{/if}
				<span class="font-mono text-micro text-surface-500">All incidents · last 30 days</span>
			</div>
		</div>

		{#if hasActive}
			<div
				class="mt-5 bg-white border border-surface-300 border-l-[3px] border-l-surface-900 rounded-card px-5 py-4 flex flex-wrap gap-3 justify-between items-center shadow-sm"
				in:fly={{ y: -10, duration: 250 }}
			>
				<div class="min-w-0">
					<div class="font-mono text-micro text-surface-900 tracking-widest uppercase">happening now</div>
					<div class="mt-1.5 font-serif text-heading leading-snug text-surface-900">{activeText()}</div>
				</div>
				<Button on:click={() => goto('/now')}>Open</Button>
			</div>
		{/if}

		{#if loading && incidents.length === 0}
			<div class="mt-6 flex flex-col gap-5" aria-hidden="true">
				{#each [0, 1] as _card}
					<div class="bg-white border border-surface-300 rounded-2xl shadow-card overflow-hidden">
						<div class="px-5 pt-4 pb-3 flex items-baseline justify-between">
							<div class="h-3 w-32 rounded bg-surface-200 animate-pulse"></div>
							<div class="h-3 w-16 rounded bg-surface-100 animate-pulse"></div>
						</div>
						{#each [0, 1] as _row}
							<div class="px-5 py-[18px] flex items-center gap-[18px] border-t border-surface-300">
								<div class="h-6 w-[78px] rounded-full bg-surface-100 animate-pulse flex-shrink-0"></div>
								<div class="flex-1 flex flex-col gap-2">
									<div class="h-3 w-24 rounded bg-surface-100 animate-pulse"></div>
									<div class="h-3.5 w-3/5 rounded bg-surface-200 animate-pulse"></div>
								</div>
								<div class="h-3 w-16 rounded bg-surface-100 animate-pulse flex-shrink-0"></div>
							</div>
						{/each}
					</div>
				{/each}
			</div>
		{:else if incidents.length === 0}
			<div class="mt-6 bg-white border border-surface-300 rounded-2xl shadow-card px-5 py-8 text-center font-sans text-sm text-surface-500">
				No incidents yet.
			</div>
		{/if}

		<div class="mt-6 flex flex-col gap-5">
			{#each groups as group (group.service_id)}
				{@const attention = needsAttention(group)}
				<div class="bg-white border border-surface-300 rounded-2xl shadow-card overflow-hidden">
					<button
						type="button"
						on:click={() => toggleGroup(group.service_id)}
						aria-expanded={expanded.has(group.service_id)}
						class="w-full bg-transparent border-none cursor-pointer text-left px-5 py-3.5 flex items-center gap-3 hover:bg-surface-50"
					>
						<span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {attention ? 'bg-surface-900' : 'border border-surface-300'}"></span>
						<span class="font-mono text-label text-surface-900 tracking-wide uppercase truncate">{group.name}</span>
						<span class="flex-1 min-w-0 flex items-center gap-2.5 font-mono text-micro text-surface-500">
							<span class="flex-shrink-0">{group.incidents.length} incident{group.incidents.length === 1 ? '' : 's'}</span>
							{#if ago(group.incidents[0]?.started_at)}
								<span class="text-surface-300">·</span>
								<span class="flex-shrink-0">last {ago(group.incidents[0].started_at)}</span>
							{/if}
							{#if attention}
								<span class="text-surface-300">·</span>
								<span class="text-surface-900 flex-shrink-0">needs you</span>
							{/if}
						</span>
						<span class="flex-shrink-0 text-lg text-surface-400 transition-transform duration-200 {expanded.has(group.service_id) ? 'rotate-90' : ''}">›</span>
					</button>
					{#if expanded.has(group.service_id)}
						<div transition:slide={{ duration: 200 }}>
							{#each group.incidents as incident (incident.id)}
								<IncidentCard {incident} showService={false} open={openId === incident.id} on:toggle={() => toggleOpen(incident)} />
							{/each}
						</div>
					{/if}
				</div>
			{/each}
		</div>

		{#if hasMore}
			<div class="mt-4 text-center">
				<Button variant="secondary" on:click={loadMore} disabled={loading}>
					{loading ? 'Loading…' : 'Load more'}
				</Button>
			</div>
		{/if}

		<div class="mt-4 font-serif text-label leading-relaxed text-surface-500">
			{incidents.length} incidents · {resolvedN} handled without you, {tookN} needed you.
		</div>
	</div>
</div>
