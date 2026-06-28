<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { Guardrail } from '$lib/types';
	import Switch from './ui/Switch.svelte';
	import Badge from './ui/Badge.svelte';

	export let guardrail: Guardrail;
	export let readonly = false;

	const dispatch = createEventDispatcher<{ toggle: { key: string; value: boolean } }>();

	function onChange(next: boolean) {
		if (guardrail.kind === 'locked' || readonly) return;
		dispatch('toggle', { key: guardrail.key, value: next });
	}
</script>

<div class="px-[18px] py-4 flex items-center justify-between gap-4 border-t border-surface-300">
	<span class="flex-1">
		<span class="block font-sans font-medium text-sm text-surface-900">{guardrail.label}</span>
		<span class="block mt-[3px] font-sans text-xs leading-snug text-surface-500">{guardrail.description}</span>
	</span>
	{#if guardrail.kind === 'toggle'}
		<Switch checked={guardrail.value} disabled={readonly} on:change={(e) => onChange(e.detail)} />
	{:else}
		<Badge tone="dark" class="flex-shrink-0 px-2.5 py-1 rounded-full text-micro">always on</Badge>
	{/if}
</div>
