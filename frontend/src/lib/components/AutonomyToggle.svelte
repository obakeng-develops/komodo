<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import SegmentedControl from './ui/SegmentedControl.svelte';

	export let value: 'auto_fix' | 'ask_first';

	const dispatch = createEventDispatcher<{ change: 'auto_fix' | 'ask_first' }>();
	const options = [
		{ value: 'auto_fix', label: 'auto-fix' },
		{ value: 'ask_first', label: 'ask first' }
	];

	function onChange(e: CustomEvent<string>) {
		dispatch('change', e.detail as 'auto_fix' | 'ask_first');
	}
</script>

<SegmentedControl {options} {value} on:change={onChange} />
