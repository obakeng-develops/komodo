<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { currentUser } from '$lib/auth';

	let ready = false;
	let needsSetup = false;
	let tokenRequired = false;

	let name = '';
	let email = '';
	let password = '';
	let token = '';
	let error: string | null = null;
	let submitting = false;

	onMount(async () => {
		try {
			const s = await api.auth.setupStatus();
			needsSetup = s.needs_setup;
			tokenRequired = s.token_required;
		} catch {
			// fall back to login mode if status can't be read
		} finally {
			ready = true;
		}
	});

	async function submit() {
		error = null;
		submitting = true;
		try {
			const user = needsSetup
				? await api.auth.setup(email.trim(), name.trim(), password, token.trim() || undefined)
				: await api.auth.login(email.trim(), password);
			currentUser.set(user);
			goto('/now');
		} catch {
			error = needsSetup
				? tokenRequired
					? 'Could not create the account — check the setup token.'
					: 'Could not create the account.'
				: 'Invalid email or password.';
		} finally {
			submitting = false;
		}
	}

	$: canSubmit =
		!!email && !!password && (!needsSetup || (!!name && (!tokenRequired || !!token)));
</script>

<div class="min-h-screen flex items-center justify-center bg-surface-100 font-sans">
	<form
		on:submit|preventDefault={submit}
		class="w-[340px] bg-white border border-surface-300 rounded-2xl p-7 flex flex-col gap-4 shadow-sm"
	>
		<div class="flex items-center gap-[11px]">
			<span class="w-8 h-8 rounded-full bg-surface-900 text-white inline-flex items-center justify-center font-serif text-[17px]">k</span>
			<h1 class="font-sans font-semibold text-[15px] text-surface-900">Komodo</h1>
		</div>
		<div class="font-sans text-[13px] text-surface-500 -mt-1">
			{needsSetup ? 'Create the owner account for your fleet.' : 'Sign in to your fleet.'}
		</div>

		{#if ready && needsSetup}
			<label class="flex flex-col gap-1">
				<span class="font-sans text-[11px] text-surface-500">Name</span>
				<input
					type="text"
					bind:value={name}
					required
					autocomplete="name"
					class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-sans text-sm text-surface-900 focus:outline-none focus:border-surface-500"
				/>
			</label>
		{/if}

		<label class="flex flex-col gap-1">
			<span class="font-sans text-[11px] text-surface-500">Email</span>
			<input
				type="email"
				bind:value={email}
				required
				autocomplete="username"
				class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 focus:outline-none focus:border-surface-500"
			/>
		</label>
		<label class="flex flex-col gap-1">
			<span class="font-sans text-[11px] text-surface-500">Password</span>
			<input
				type="password"
				bind:value={password}
				required
				autocomplete={needsSetup ? 'new-password' : 'current-password'}
				class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 focus:outline-none focus:border-surface-500"
			/>
		</label>

		{#if ready && needsSetup && tokenRequired}
			<label class="flex flex-col gap-1">
				<span class="font-sans text-[11px] text-surface-500">Setup token</span>
				<input
					type="text"
					bind:value={token}
					required
					class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 focus:outline-none focus:border-surface-500"
				/>
				<span class="font-sans text-[11px] text-surface-400">From the backend's <span class="font-mono">SETUP_TOKEN</span>.</span>
			</label>
		{/if}

		<div class="min-h-[18px]">
			{#if error}
				<span class="font-sans text-[12px] text-danger-600">{error}</span>
			{/if}
		</div>

		<button
			type="submit"
			disabled={submitting || !ready || !canSubmit}
			class="px-4 py-2 rounded-lg bg-surface-900 text-white font-sans font-medium text-[13px] border-none cursor-pointer hover:bg-surface-800 disabled:opacity-40 disabled:cursor-default"
		>
			{#if submitting}
				{needsSetup ? 'Creating…' : 'Signing in…'}
			{:else}
				{needsSetup ? 'Create account' : 'Sign in'}
			{/if}
		</button>
	</form>
</div>
