<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { activeIncident, servicesStore } from '$lib/stream';
	import { api } from '$lib/api';
	import { currentUser } from '$lib/auth';
	import type { User, Service } from '$lib/types';

	export let user: User;

	let open = false; // mobile drawer

	async function logout() {
		open = false;
		try {
			await api.auth.logout();
		} finally {
			currentUser.set(null);
			goto('/login');
		}
	}

	// Navigate and close the drawer (no-op on desktop, where it's never open).
	function go(path: string) {
		open = false;
		goto(path);
	}

	$: services = $servicesStore;

	function navClass(path: string, current: string) {
		const active = current === path;
		return `
			w-full flex items-center justify-between text-left px-3 py-2 rounded-lg border-none cursor-pointer
			font-sans text-[13px] font-medium transition-colors
			${active ? 'bg-white text-surface-900 shadow-sm' : 'bg-transparent text-surface-600 hover:bg-surface-200/50'}
		`;
	}

	$: nav = $page.url.pathname.split('/')[1] || 'now';

	$: acting =
		$activeIncident &&
		['detecting', 'diagnosing', 'fixing', 'verifying', 'asking', 'takeover'].includes(
			$activeIncident.view
		);

	function dotClasses(services: Service[]) {
		if ($activeIncident?.view === 'asking') {
			return 'border-2 border-dashed border-surface-800';
		}
		if ($activeIncident?.view === 'takeover') {
			return 'border-2 border-dashed border-surface-400';
		}
		if ($activeIncident?.view && !['resting', 'resolved'].includes($activeIncident.view)) {
			return 'bg-surface-900 animate-pulse';
		}
		if (services.some((s) => s.status === 'down')) {
			return 'bg-danger-500';
		}
		if (services.some((s) => s.status === 'degraded')) {
			return 'bg-warning-500';
		}
		if (services.length > 0) {
			return 'bg-success-500';
		}
		return 'bg-surface-500';
	}

	function summaryText(services: Service[]) {
		const down = services.filter((s) => s.status === 'down').length;
		const degraded = services.filter((s) => s.status === 'degraded').length;
		if (down === 1) return '1 service down';
		if (down > 1) return `${down} services down`;
		if (degraded === 1) return '1 service degraded';
		if (degraded > 1) return `${degraded} services degraded`;
		return 'all green';
	}
</script>

<!-- Mobile top bar -->
<header
	class="md:hidden sticky top-0 z-20 flex items-center justify-between px-4 py-3 bg-surface-200 border-b border-surface-300"
>
	<div class="flex items-center gap-2.5 min-w-0">
		<span
			class="w-7 h-7 rounded-full bg-surface-900 text-white inline-flex items-center justify-center font-serif text-[15px] flex-shrink-0"
			>m</span
		>
		<span class="inline-flex items-center gap-1.5 font-mono text-[11px] text-surface-500 truncate">
			<span class="w-1.5 h-1.5 rounded-full flex-shrink-0 {dotClasses(services)}"></span>
			{$activeIncident?.status_text || summaryText(services)}
		</span>
	</div>
	<button
		on:click={() => (open = true)}
		aria-label="Open menu"
		class="p-2 -mr-2 bg-transparent border-none cursor-pointer text-surface-700 flex-shrink-0"
	>
		<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
			<path d="M3 6h14M3 10h14M3 14h14" stroke-linecap="round" />
		</svg>
	</button>
</header>

<!-- Mobile drawer overlay -->
{#if open}
	<button
		class="md:hidden fixed inset-0 z-30 bg-surface-950/30 border-none cursor-default"
		on:click={() => (open = false)}
		aria-label="Close menu"
	></button>
{/if}

<!-- Sidebar on desktop; off-canvas drawer on mobile -->
<aside
	class="fixed md:sticky top-0 left-0 z-40 h-screen w-[236px] flex-shrink-0 bg-surface-200 border-r border-surface-300 flex flex-col py-6 px-[18px] transition-transform duration-200 md:translate-x-0 {open
		? 'translate-x-0'
		: '-translate-x-full'}"
>
	<div class="flex items-center gap-[11px] px-2">
		<span
			class="w-8 h-8 rounded-full bg-surface-900 text-white inline-flex items-center justify-center font-serif text-[17px]"
			>m</span
		>
		<div>
			<div class="font-sans font-semibold text-[15px] text-surface-900 leading-tight">Mino</div>
			<div class="mt-[3px] inline-flex items-center gap-1.5 font-mono text-[11px] text-surface-500">
				<span class="w-1.5 h-1.5 rounded-full transition-all duration-300 {dotClasses(services)}"></span>
				{$activeIncident?.status_text || summaryText(services)}
			</div>
		</div>
	</div>

	<nav class="mt-[30px] flex flex-col gap-[3px]">
		<button class={navClass('now', nav)} on:click={() => go('/now')}>
			<span>Now</span>
			<span class="w-2 h-2 rounded-full bg-surface-900 {acting ? '' : 'hidden'}"></span>
		</button>
		<button class={navClass('fleet', nav)} on:click={() => go('/fleet')}>
			<span>Fleet</span>
		</button>
		<button class={navClass('incidents', nav)} on:click={() => go('/incidents')}>
			<span>Incidents</span>
		</button>
		<button class={navClass('guardrails', nav)} on:click={() => go('/guardrails')}>
			<span>Guardrails</span>
		</button>
		<button class={navClass('settings', nav)} on:click={() => go('/settings')}>
			<span>Settings</span>
		</button>
	</nav>

	<div class="flex-1"></div>

	<button
		class="flex items-center gap-[11px] p-2.5 rounded-xl bg-transparent border-none cursor-pointer text-left w-full hover:bg-surface-200/80 transition-colors"
		on:click={() => go('/settings')}
	>
		<span
			class="w-[30px] h-[30px] rounded-full bg-surface-400 text-surface-800 inline-flex items-center justify-center font-sans font-medium text-xs"
			>{user.name?.[0] ?? '?'}</span
		>
		<span class="leading-tight flex-1 min-w-0">
			<span class="block font-sans font-medium text-[12px] text-surface-800 truncate">{user.name}</span>
			<span class="block font-mono text-[11px] text-surface-500">{user.role === 'owner' ? 'Owner' : 'Operator'}</span>
		</span>
	</button>
	<button
		class="mt-1 px-3 py-1.5 rounded-lg bg-transparent border-none cursor-pointer text-left w-full font-sans text-[12px] text-surface-500 hover:bg-surface-200/80 hover:text-surface-800 transition-colors"
		on:click={logout}
	>
		Log out
	</button>
</aside>
