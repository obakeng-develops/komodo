<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let options: { value: string; label: string }[];
	export let value: string;
	// 'sm' suits inline use (rows); 'md' for prominent toggles.
	export let size: 'sm' | 'md' = 'md';

	const dispatch = createEventDispatcher<{ change: string }>();
	function select(v: string) {
		if (v !== value) dispatch('change', v);
	}

	$: pad = size === 'sm' ? 'px-2.5 py-1' : 'px-3.5 py-1.5';
</script>

<div class="inline-flex items-center gap-1 p-[3px] rounded-control bg-surface-200 border border-surface-300">
	{#each options as opt (opt.value)}
		<button
			type="button"
			on:click={() => select(opt.value)}
			class="{pad} rounded-md border-none cursor-pointer font-medium text-label font-sans transition-colors {value ===
			opt.value
				? 'bg-surface-900 text-white'
				: 'bg-transparent text-surface-500 hover:text-surface-900'}"
		>
			{opt.label}
		</button>
	{/each}
</div>
