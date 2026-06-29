<script lang="ts">
	export let variant: 'primary' | 'secondary' | 'ghost' | 'danger' = 'primary';
	export let size: 'sm' | 'md' | 'lg' = 'md';
	export let type: 'button' | 'submit' = 'button';
	export let disabled = false;

	const variants: Record<string, string> = {
		primary: 'bg-surface-900 text-white border border-surface-900 hover:bg-surface-800',
		secondary: 'bg-white text-surface-700 border border-surface-300 hover:bg-surface-50',
		ghost: 'bg-transparent text-surface-600 border-none hover:text-surface-900',
		danger: 'bg-white text-danger-600 border border-surface-300 hover:bg-danger-500/10'
	};
	const sizes: Record<string, string> = {
		sm: 'px-3 py-1.5 text-label',
		md: 'px-4 py-2 text-label',
		lg: 'px-5 py-2.5 text-body'
	};
</script>

<button
	{type}
	{disabled}
	on:click
	class="inline-flex items-center justify-center gap-1.5 rounded-control font-sans font-medium cursor-pointer transition-colors disabled:opacity-40 disabled:cursor-default {variants[variant]} {sizes[size]}"
	{...$$restProps}
>
	<slot />
</button>
