<script lang="ts">
	export let value = '';
	export let font: 'mono' | 'sans' = 'mono';
</script>

<input
	bind:value
	on:input
	on:change
	class="px-3 py-2 rounded-control bg-white border border-surface-300 text-label text-surface-900 focus:outline-none focus:border-surface-500 {font ===
	'mono'
		? 'font-mono'
		: 'font-sans'}"
	{...$$restProps}
/>
