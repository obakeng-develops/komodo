<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let checked = false;
	export let disabled = false;

	const dispatch = createEventDispatcher<{ change: boolean }>();
	function toggle() {
		if (!disabled) dispatch('change', !checked);
	}
</script>

<button
	type="button"
	on:click={toggle}
	{disabled}
	aria-pressed={checked}
	class="relative w-[42px] h-6 rounded-full border-none flex-shrink-0 transition-colors {checked
		? 'bg-surface-900'
		: 'bg-surface-400'} {disabled ? 'opacity-50 cursor-default' : 'cursor-pointer'}"
>
	<span
		class="absolute top-[3px] w-[18px] h-[18px] rounded-full bg-white shadow-sm transition-all {checked
			? 'left-[21px]'
			: 'left-[3px]'}"
	></span>
</button>
