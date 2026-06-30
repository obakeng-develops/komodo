<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { lastLearningCreated } from '$lib/stream';
	import { isOwner } from '$lib/auth';
	import GuardrailRow from '$lib/components/GuardrailRow.svelte';
	import type { Guardrail as GuardrailType, Learning } from '$lib/types';

	let learnings: Learning[] = [];
	let guardrails: GuardrailType[] = [];

	onMount(() => {
		load();
	});

	$: if ($lastLearningCreated) {
		load();
	}

	async function load() {
		[learnings, guardrails] = await Promise.all([
			api.learnings.list(),
			api.guardrails.list(),
		]);
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

	// Backend datetimes are naive UTC; parse as UTC, not local (matches /fleet).
	function ago(iso: string | null): string | null {
		if (!iso) return null;
		const t = new Date(/[Z+]/.test(iso) ? iso : iso + 'Z').getTime();
		const s = Math.max(0, (Date.now() - t) / 1000);
		if (s < 90) return 'just now';
		const m = s / 60;
		if (m < 90) return `${Math.round(m)}m ago`;
		const h = m / 60;
		if (h < 36) return `${Math.round(h)}h ago`;
		return `${Math.round(h / 24)}d ago`;
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
				<div class="font-sans text-xs text-surface-500">Nothing learned yet — it picks up rules as it recovers containers.</div>
			{/each}
		</div>

		<div class="mt-8 font-sans font-semibold text-label text-surface-700">Your guardrails</div>
		<div class="mt-1 font-sans text-sm leading-relaxed text-surface-500">Hard limits the agent obeys on every restart. Locked ones can't be turned off.</div>

		<div class="mt-3.5 bg-white border border-surface-300 rounded-2xl overflow-hidden shadow-sm">
			{#each guardrails as guardrail (guardrail.id)}
				<GuardrailRow {guardrail} readonly={!$isOwner} on:toggle={(e) => toggleGuardrail(e.detail.key, e.detail.value)} />
			{/each}
		</div>
	</div>
</div>
