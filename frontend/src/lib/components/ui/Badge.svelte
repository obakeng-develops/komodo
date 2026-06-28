<script lang="ts">
	export let tone: 'neutral' | 'down' | 'degraded' | 'healthy' | 'dark' = 'neutral';
	let className = '';
	export { className as class };

	const tones: Record<string, string> = {
		neutral: 'bg-surface-100 text-surface-600',
		down: 'bg-danger-500/15 text-danger-600',
		degraded: 'bg-warning-500/15 text-warning-600',
		healthy: 'bg-success-500/15 text-success-600',
		dark: 'bg-surface-900 text-white'
	};
</script>

<span
	class="inline-flex items-center px-2 py-0.5 rounded-md font-sans text-micro font-medium {tones[tone]} {className}"
>
	<slot />
</span>
