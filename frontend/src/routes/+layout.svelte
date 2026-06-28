<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import { api } from '$lib/api';
	import { connectStream } from '$lib/stream';
	import { currentUser } from '$lib/auth';
	import '../app.css';

	let loading = true;

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
			})
			.catch(() => {
				// api wrapper already redirects to /login on 401
				goto('/login');
			})
			.finally(() => {
				loading = false;
			});
	});
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
