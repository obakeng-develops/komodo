<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { Guardrail } from '$lib/types';

	export let guardrail: Guardrail;
	export let readonly = false;

	const dispatch = createEventDispatcher<{ toggle: { key: string; value: boolean } }>();

	function toggle() {
		if (guardrail.kind === 'locked' || readonly) return;
		dispatch('toggle', { key: guardrail.key, value: !guardrail.value });
	}

	function trackClass(on: boolean) {
		return `relative w-[42px] h-6 rounded-full border-none cursor-pointer flex-shrink-0 transition-colors ${on ? 'bg-surface-900' : 'bg-surface-400'}`;
	}

	function thumbClass(on: boolean) {
		return `absolute top-[3px] w-[18px] h-[18px] rounded-full bg-white shadow-sm transition-all ${on ? 'left-[21px]' : 'left-[3px]'}`;
	}
</script>

<div class="px-[18px] py-4 flex items-center justify-between gap-4 border-t border-surface-300">
	<span class="flex-1">
		<span class="block font-sans font-medium text-sm text-surface-900">{guardrail.label}</span>
		<span class="block mt-[3px] font-sans text-xs leading-snug text-surface-500">{guardrail.description}</span>
	</span>
	{#if guardrail.kind === 'toggle'}
		<button class="{trackClass(guardrail.value)} {readonly ? 'opacity-50 !cursor-default' : ''}" on:click={toggle} disabled={readonly} aria-pressed={guardrail.value}>
			<span class={thumbClass(guardrail.value)}></span>
		</button>
	{:else}
		<span class="flex-shrink-0 inline-flex items-center px-2.5 py-1 rounded-full bg-surface-900 text-white font-medium text-[11px] font-sans">
			always on
		</span>
	{/if}
</div>
