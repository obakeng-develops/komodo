<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { currentUser } from '$lib/auth';
	import Input from '$lib/components/ui/Input.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	let ready = false;
	let needsSetup = false;
	let tokenRequired = false;

	let name = '';
	let email = '';
	let password = '';
	let confirmPassword = '';
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

	$: passwordsMatch = !needsSetup || password === confirmPassword;
	$: canSubmit =
		!!email && !!password && (!needsSetup || (!!name && passwordsMatch && (!tokenRequired || !!token)));
</script>

<div class="min-h-screen flex items-center justify-center px-4 bg-surface-100 font-sans">
	<form
		on:submit|preventDefault={submit}
		class="w-full max-w-[340px] bg-white border border-surface-300 rounded-card p-7 flex flex-col gap-4 shadow-card"
	>
		<div class="flex items-center gap-[11px]">
			<span class="w-8 h-8 rounded-full bg-surface-900 text-white inline-flex items-center justify-center font-serif text-heading">k</span>
			<h1 class="font-sans font-semibold text-body text-surface-900">Komodo</h1>
		</div>
		<div class="font-sans text-label text-surface-500 -mt-1">
			{needsSetup ? 'Create the owner account for your fleet.' : 'Sign in to your fleet.'}
		</div>

		{#if ready && needsSetup}
			<label for="name" class="flex flex-col gap-1">
				<span class="font-sans text-micro text-surface-500">Name</span>
				<Input id="name" type="text" font="sans" bind:value={name} required autocomplete="name" />
			</label>
		{/if}

		<label for="email" class="flex flex-col gap-1">
			<span class="font-sans text-micro text-surface-500">Email</span>
			<Input id="email" type="email" bind:value={email} required autocomplete="username" />
		</label>
		<label for="password" class="flex flex-col gap-1">
			<span class="font-sans text-micro text-surface-500">Password</span>
			<Input
				id="password"
				type="password"
				bind:value={password}
				required
				autocomplete={needsSetup ? 'new-password' : 'current-password'}
			/>
		</label>

		{#if ready && needsSetup}
			<label for="confirm-password" class="flex flex-col gap-1">
				<span class="font-sans text-micro text-surface-500">Confirm password</span>
				<Input id="confirm-password" type="password" bind:value={confirmPassword} required autocomplete="new-password" />
				{#if password && confirmPassword && password !== confirmPassword}
					<span class="font-sans text-micro text-danger-600">Passwords don't match.</span>
				{/if}
			</label>
		{/if}

		{#if ready && needsSetup && tokenRequired}
			<label for="token" class="flex flex-col gap-1">
				<span class="font-sans text-micro text-surface-500">Setup token</span>
				<Input id="token" type="text" bind:value={token} required />
				<span class="font-sans text-micro text-surface-400">From the backend's <span class="font-mono">SETUP_TOKEN</span>.</span>
			</label>
		{/if}

		<div class="min-h-[18px]">
			{#if error}
				<span class="font-sans text-label text-danger-600">{error}</span>
			{/if}
		</div>

		<Button type="submit" disabled={submitting || !ready || !canSubmit}>
			{#if submitting}
				{needsSetup ? 'Creating…' : 'Signing in…'}
			{:else}
				{needsSetup ? 'Create account' : 'Sign in'}
			{/if}
		</Button>
	</form>
</div>
