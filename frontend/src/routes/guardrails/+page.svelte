<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { lastLearningCreated } from '$lib/stream';
	import { isOwner } from '$lib/auth';
	import GuardrailRow from '$lib/components/GuardrailRow.svelte';
	import { ago } from '$lib/time';
	import type { Guardrail as GuardrailType, Learning } from '$lib/types';

	let learnings: Learning[] = [];
	let guardrails: GuardrailType[] = [];
	let loading = true;

	onMount(() => {
		load();
	});

	$: if ($lastLearningCreated) {
		load();
	}

	async function load() {
		try {
			[learnings, guardrails] = await Promise.all([
				api.learnings.list(),
				api.guardrails.list(),
			]);
		} finally {
			loading = false;
		}
	}

	async function toggleGuardrail(key: string, value: boolean) {
		await api.guardrails.update(key, value);
		guardrails = guardrails.map((g) => (g.key === key ? { ...g, value } : g));
	}

	function chipClass(auto: boolean) {
		return auto
			? 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-900 text-white font-medium text-micro font-sans'
			: 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-transparent border-[1.5px] border-dashed border-surface-700 text-surface-700 font-medium text-micro font-sans';
	}

	function serviceChipClass() {
		return 'inline-flex items-center px-2 py-0.5 rounded-md bg-surface-100 border border-surface-300 font-medium text-micro font-mono text-surface-700';
	}

	// A plain-English read on how much to trust a learned rule, from its recovery
	// record. Shown next to the raw "recovered N/M" count.
	function confidence(l: Learning): string {
		const ratio = l.incident_count ? l.success_count / l.incident_count : 0;
		if (l.incident_count >= 3 && ratio >= 0.9) return 'high confidence';
		if (ratio >= 0.6) return 'medium confidence';
		return 'low confidence';
	}

</script>

<div class="px-4 sm:px-10 py-7 sm:py-9 pb-20">
	<div class="max-w-[640px] mx-auto">
		<div class="font-serif text-title leading-none text-surface-900 tracking-tight">Learning & guardrails</div>
		<div class="mt-2 font-sans text-sm leading-relaxed text-surface-500">
			What it has picked up on its own, and the limits it obeys on every restart.
		</div>

		<div class="mt-7 font-sans font-semibold text-label text-surface-700">What I've learned</div>
		<div class="mt-3.5 flex flex-col gap-3">
			{#if loading && learnings.length === 0}
				{#each [0, 1] as _card}
					<div class="bg-white border border-surface-300 rounded-xl p-5 shadow-sm" aria-hidden="true">
						<div class="flex justify-between items-center gap-3">
							<div class="h-5 w-28 rounded-md bg-surface-100 animate-pulse"></div>
							<div class="h-6 w-24 rounded-full bg-surface-100 animate-pulse"></div>
						</div>
						<div class="mt-3 h-4 w-4/5 rounded bg-surface-200 animate-pulse"></div>
						<div class="mt-2.5 h-3 w-1/2 rounded bg-surface-100 animate-pulse"></div>
					</div>
				{/each}
			{:else}
				{#each learnings as learning (learning.id)}
				<div class="bg-white border border-surface-300 rounded-xl p-5 shadow-sm">
					<div class="flex justify-between items-center gap-3">
						<span class={serviceChipClass()}>{learning.service_name || 'all containers'}</span>
						<span class={chipClass(learning.behavior === 'auto_fix')}>
							{learning.behavior === 'auto_fix' ? 'auto-fixing' : 'asking first'}
						</span>
					</div>
					<div class="mt-3 font-serif text-heading leading-relaxed text-surface-900">{learning.rule}</div>
					<div class="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 font-mono text-label text-surface-500">
						<span>{learning.learned_from}</span>
						{#if learning.incident_count}
							<span class="text-surface-300">·</span>
							<span class="text-surface-700">{confidence(learning)}</span>
						{/if}
						{#if ago(learning.updated_at)}
							<span class="text-surface-300">·</span>
							<span>last recovered {ago(learning.updated_at)}</span>
						{/if}
					</div>
				</div>
			{:else}
				<div class="font-sans text-xs text-surface-500">Nothing learned yet. It picks up rules as it recovers containers.</div>
				{/each}
			{/if}
		</div>

		<div class="mt-8 font-sans font-semibold text-label text-surface-700">Your guardrails</div>
		<div class="mt-1 font-sans text-sm leading-relaxed text-surface-500">Hard limits the agent obeys on every restart. Locked ones can't be turned off.</div>

		<div class="mt-3.5 bg-white border border-surface-300 rounded-2xl overflow-hidden shadow-sm">
			{#if loading && guardrails.length === 0}
				{#each [0, 1, 2] as _row}
					<div class="px-[18px] py-4 flex items-center justify-between gap-4 border-t border-surface-300" aria-hidden="true">
						<div class="flex-1 flex flex-col gap-2">
							<div class="h-3.5 w-40 rounded bg-surface-200 animate-pulse"></div>
							<div class="h-3 w-3/4 rounded bg-surface-100 animate-pulse"></div>
						</div>
						<div class="h-5 w-10 rounded-full bg-surface-100 animate-pulse flex-shrink-0"></div>
					</div>
				{/each}
			{:else}
				{#each guardrails as guardrail (guardrail.id)}
					<GuardrailRow {guardrail} readonly={!$isOwner} on:toggle={(e) => toggleGuardrail(e.detail.key, e.detail.value)} />
				{/each}
			{/if}
		</div>
	</div>
</div>
