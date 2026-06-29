<script lang="ts">
	export let tone: 'neutral' | 'down' | 'degraded' | 'healthy' | 'dark' = 'neutral';
	export let variant: 'solid' | 'outline' | 'dashed' = 'solid';
	export let pill = false; // rounded-full status pill vs. a rounded-md chip
	let className = '';
	export { className as class };

	const solid: Record<string, string> = {
		neutral: 'bg-surface-100 text-surface-600',
		down: 'bg-danger-500/15 text-danger-600',
		degraded: 'bg-warning-500/15 text-warning-600',
		healthy: 'bg-success-500/15 text-success-600',
		dark: 'bg-surface-900 text-white'
	};
	const outline: Record<string, string> = {
		neutral: 'border-surface-400 text-surface-600',
		down: 'border-danger-500 text-danger-600',
		degraded: 'border-warning-500 text-warning-600',
		healthy: 'border-success-500 text-success-600',
		dark: 'border-surface-800 text-surface-800'
	};

	$: shape = pill ? 'rounded-full px-2.5 py-1 gap-1.5' : 'rounded-md px-2 py-0.5';
	$: skin =
		variant === 'solid'
			? solid[tone]
			: `bg-transparent border ${variant === 'dashed' ? 'border-dashed' : ''} ${outline[tone]}`;
</script>

<span class="inline-flex items-center font-sans text-micro font-medium {shape} {skin} {className}">
	<slot />
</span>
