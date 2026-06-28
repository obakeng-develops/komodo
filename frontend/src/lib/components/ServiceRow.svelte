<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { Service } from '$lib/types';

	export let service: Service;

	const dispatch = createEventDispatcher<{
		toggle: { watch_only: boolean };
		remove: void;
	}>();

	// down = red, degraded = amber, healthy = green.
	function dotClass(status: string) {
		if (status === 'down') return 'bg-danger-500';
		if (status === 'degraded') return 'bg-warning-500';
		return 'bg-success-500';
	}

	function checkedText(at: string | null) {
		if (!at) return 'not checked yet';
		return `checked ${new Date(at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
	}

	function segClass(selected: boolean) {
		return `px-2.5 py-1 rounded-md border-none cursor-pointer font-medium text-[12px] font-sans transition-colors ${
			selected ? 'bg-surface-900 text-white' : 'bg-transparent text-surface-500 hover:text-surface-900'
		}`;
	}

	function sourceBadge(service: Service) {
		if (service.method === 'url') return 'URL';
		if (service.method === 'agent') return service.host_name ?? 'agent';
		return 'docker';
	}

	function sourceDescription(service: Service) {
		if (service.method === 'url') return service.health_check_url ?? 'URL check';
		if (service.method === 'agent') return `reported by ${service.host_name ?? 'agent'}`;
		return 'local Docker';
	}

	function set(watch_only: boolean) {
		if (watch_only !== service.watch_only) dispatch('toggle', { watch_only });
	}

	$: image = service.agent_host_info?.image as string | undefined;
	$: isManual = service.method === 'url';
	$: canRemove = service.method === 'docker' || service.method === 'url';
</script>

	<div class="bg-white border border-surface-300 rounded-xl px-4 py-3.5 flex items-center gap-3.5">
		<span class="w-[7px] h-[7px] rounded-full flex-shrink-0"
		class:bg-danger-500={service.status === 'down'}
		class:bg-warning-500={service.status === 'degraded'}
		class:bg-success-500={service.status === 'healthy'}
	></span>
		<div class="flex-1 min-w-0">
			<div class="flex items-center gap-2">
				<div class="font-mono font-medium text-sm text-surface-900 truncate">{service.name}</div>
				<span class="px-1.5 py-0.5 rounded bg-surface-100 text-surface-600 font-mono text-[10px] uppercase tracking-wide">{sourceBadge(service)}</span>
			</div>
			<div class="mt-[3px] font-mono text-[11px] text-surface-500 truncate">
				{service.status} · {sourceDescription(service)} · {checkedText(service.last_check_at)}{image ? ` · ${image}` : ''}
			</div>
		</div>
		<div class="inline-flex items-center gap-1 p-[3px] rounded-lg bg-surface-100 border border-surface-300 flex-shrink-0">
			<button class={segClass(!service.watch_only)} on:click={() => set(false)}>manage</button>
			<button class={segClass(service.watch_only)} on:click={() => set(true)}>watch-only</button>
		</div>
		{#if canRemove}
			<button
				type="button"
				on:click={() => dispatch('remove')}
				class="px-2 py-1.5 rounded-lg text-danger-600 font-sans font-medium text-[12px] border border-surface-300 hover:bg-danger-500/10 flex-shrink-0"
			>
				Remove
			</button>
		{/if}
	</div>
