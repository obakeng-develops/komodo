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
			? 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-900 text-white font-medium text-[11px] font-sans'
			: 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-transparent border-[1.5px] border-dashed border-surface-700 text-surface-700 font-medium text-[11px] font-sans';
	}

	function serviceChipClass() {
		return 'inline-flex items-center px-2 py-0.5 rounded-md bg-surface-100 border border-surface-300 font-medium text-[11px] font-mono text-surface-700';
	}
</script>

<div class="px-10 py-9 pb-20">
	<div class="max-w-[640px] mx-auto">
		<div class="font-serif text-[28px] leading-none text-surface-900 tracking-tight">Learning & guardrails</div>
		<div class="mt-2 font-sans text-sm leading-relaxed text-surface-500">
			What it has picked up on its own, and the limits it obeys on every restart.
		</div>

		<div class="mt-7 font-sans font-semibold text-[13px] text-surface-700">What I've learned</div>
		<div class="mt-3.5 flex flex-col gap-3">
			{#each learnings as learning (learning.id)}
				<div class="bg-white border border-surface-300 rounded-xl p-5 shadow-sm">
					<div class="flex justify-between items-center gap-3">
						<span class={serviceChipClass()}>{learning.service_name || 'all containers'}</span>
						<span class={chipClass(learning.behavior === 'auto_fix')}>
							{learning.behavior === 'auto_fix' ? '● auto-fixing' : '? asking first'}
						</span>
					</div>
					<div class="mt-3 font-serif text-[17px] leading-relaxed text-surface-900">{learning.rule}</div>
					<div class="mt-2 font-mono text-[12px] text-surface-500">{learning.learned_from}</div>
				</div>
			{:else}
				<div class="font-sans text-xs text-surface-500">Nothing learned yet — it picks up rules as it recovers containers.</div>
			{/each}
		</div>

		<div class="mt-8 font-sans font-semibold text-[13px] text-surface-700">Your guardrails</div>
		<div class="mt-1 font-sans text-sm leading-relaxed text-surface-500">Hard limits the agent obeys on every restart. Locked ones can't be turned off.</div>

		<div class="mt-3.5 bg-white border border-surface-300 rounded-2xl overflow-hidden shadow-sm">
			{#each guardrails as guardrail (guardrail.id)}
				<GuardrailRow {guardrail} readonly={!$isOwner} on:toggle={(e) => toggleGuardrail(e.detail.key, e.detail.value)} />
			{/each}
		</div>
	</div>
</div>
