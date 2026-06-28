<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let value: 'auto_fix' | 'ask_first';

	const dispatch = createEventDispatcher<{ change: 'auto_fix' | 'ask_first' }>();

	function select(mode: 'auto_fix' | 'ask_first') {
		if (mode !== value) dispatch('change', mode);
	}

	function segmentClass(selected: boolean) {
		return `
			px-3.5 py-1.5 rounded-md border-none cursor-pointer font-medium text-[12px] font-sans transition-colors
			${selected ? 'bg-surface-900 text-white' : 'bg-transparent text-surface-500 hover:text-surface-900'}
		`;
	}
</script>

<div class="inline-flex items-center gap-1 p-[3px] rounded-lg bg-surface-200 border border-surface-300">
	<button class={segmentClass(value === 'auto_fix')} on:click={() => select('auto_fix')}>auto-fix</button>
	<button class={segmentClass(value === 'ask_first')} on:click={() => select('ask_first')}>ask first</button>
</div>
