<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import { api } from '$lib/api';
	import { connectStream, servicesStore, servicesNeedRefresh } from '$lib/stream';
	import { currentUser } from '$lib/auth';
	import '../app.css';

	let loading = true;
	let unsubscribeServices: (() => void) | null = null;

	$: isLogin = $page.url.pathname.startsWith('/login');

	onMount(() => {
		if (isLogin) {
			loading = false;
			return;
		}
		api.me()
			.then((u) => {
				currentUser.set(u);
				connectStream();
				// Single owner of the services list: keep servicesStore fresh on
				// mount and on every services_changed, so every consumer (Now,
				// Sidebar) stays live regardless of which page is mounted. See #74.
				// subscribe() fires immediately, covering the initial load too.
				unsubscribeServices = servicesNeedRefresh.subscribe(async () => {
					try {
						servicesStore.set(await api.services.list());
					} catch {
						// ignore background refresh failures
					}
				});
			})
			.catch(() => {
				// api wrapper already redirects to /login on 401
				goto('/login');
			})
			.finally(() => {
				loading = false;
			});
	});

	onDestroy(() => unsubscribeServices?.());
</script>

{#if isLogin}
	<slot />
{:else if loading || !$currentUser}
	<div class="min-h-screen flex items-center justify-center text-surface-500">Loading…</div>
{:else}
	<div class="min-h-screen md:flex font-sans text-surface-900">
		<Sidebar user={$currentUser} />
		<main class="flex-1 min-w-0 bg-surface-100 min-h-screen">
			<slot />
		</main>
	</div>
{/if}
