<script lang="ts">
	export let value: string;
</script>

<select
	bind:value
	on:change
	class="px-3 py-2 rounded-control bg-white border border-surface-300 font-sans text-label text-surface-900 focus:outline-none focus:border-surface-500"
	{...$$restProps}
>
	<slot />
</select>
