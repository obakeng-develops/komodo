<script lang="ts">
	// Container only — callers pass their own padding via `class` since it varies.
	let className = '';
	export { className as class };
</script>

<div class="bg-white border border-surface-300 rounded-card shadow-card {className}">
	<slot />
</div>
