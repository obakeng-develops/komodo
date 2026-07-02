<script lang="ts">
	import { goto } from '$app/navigation';
	import { fade } from 'svelte/transition';
	import { api } from '$lib/api';
	import { servicesStore } from '$lib/stream';
	import type { Host, UserSettings } from '$lib/types';
	import Button from '$lib/components/ui/Button.svelte';
	import SegmentedControl from '$lib/components/ui/SegmentedControl.svelte';

	// Shown on the Now page only while the owner has no services yet (#82). Two
	// paths: watch a server via the agent (Mino's main job), or a quick URL
	// check. Adding a URL pushes it into servicesStore so the parent swaps this
	// card out; the server path clears once the agent connects and reports a
	// service (servicesStore is kept fresh by the layout).
	export let settings: UserSettings | null = null;

	const serverUrl = typeof window !== 'undefined' ? window.location.origin : '';

	let mode: 'server' | 'url' = 'server';

	// Server / agent path
	let hostName = '';
	let minoUrl = serverUrl;
	let creatingHost = false;
	let createdHost: (Host & { token: string }) | null = null;
	let hostError: string | null = null;
	let copied = false;

	$: installCommand = createdHost
		? (() => {
				const base = minoUrl.replace(/\/$/, '');
				return `curl -fsSL ${base}${api.hosts.scriptUrl()} | python3 - --server ${base} --token ${createdHost.token}`;
			})()
		: '';

	async function createHost() {
		const n = hostName.trim();
		if (!n) return;
		creatingHost = true;
		hostError = null;
		try {
			createdHost = await api.hosts.create(n);
		} catch {
			hostError = "Couldn't create the server. Try again.";
		} finally {
			creatingHost = false;
		}
	}

	async function copyCommand() {
		await navigator.clipboard.writeText(installCommand);
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}

	// URL path
	let urlName = '';
	let url = '';
	let addingUrl = false;
	let urlError: string | null = null;

	async function addUrlService() {
		const n = urlName.trim();
		const u = url.trim();
		if (!n || !u) return;
		addingUrl = true;
		urlError = null;
		try {
			const service = await api.services.createUrl(n, u);
			servicesStore.update((s) => [...s, service]);
		} catch {
			urlError = "Couldn't add that. Check the name and URL.";
		} finally {
			addingUrl = false;
		}
	}

	const inputClass =
		'px-3 py-2 rounded-lg bg-white border border-surface-300 text-sm text-surface-900 focus:outline-none focus:border-surface-500';

	$: autonomyLabel = settings?.autonomy === 'ask_first' ? 'ask-first' : 'auto-fix';
	$: nextSteps = [
		{
			title: 'Connect an LLM',
			body: 'Get a written cause and fix on each incident. Optional. Monitoring and restarts work without it.',
			done: !!settings?.llm_api_key,
			cta: 'Add a key'
		},
		{
			title: 'Choose how it acts',
			body: `Auto-fix restarts on its own; ask-first waits for your approval. Currently ${autonomyLabel}.`,
			done: !!settings,
			cta: 'Set autonomy'
		}
	];
</script>

<div in:fade>
	<div class="inline-flex items-center gap-2 font-mono text-xs text-surface-500 tracking-wide">
		<span class="w-2 h-2 rounded-full bg-surface-500"></span>
		setup
	</div>
	<div class="mt-7 font-serif text-display text-surface-900 tracking-tight">Let's watch your first service.</div>
	<div class="mt-4 font-sans text-base leading-relaxed text-surface-600">
		Install the agent on a server to watch its containers, or add a URL health check.
	</div>

	<div class="mt-5">
		<SegmentedControl
			options={[
				{ value: 'server', label: 'A server' },
				{ value: 'url', label: 'A URL check' }
			]}
			value={mode}
			on:change={(e) => (mode = e.detail === 'url' ? 'url' : 'server')}
		/>
	</div>

	{#if mode === 'server'}
		{#if !createdHost}
			<form class="mt-4 flex flex-col gap-3" on:submit|preventDefault={createHost}>
				<label class="flex flex-col gap-1">
					<span class="font-sans text-micro text-surface-500">Server name</span>
					<input type="text" placeholder="e.g. prod-web-01" bind:value={hostName} class="{inputClass} font-sans" />
				</label>
				<label class="flex flex-col gap-1">
					<span class="font-sans text-micro text-surface-500">Mino URL</span>
					<input type="url" placeholder={serverUrl} bind:value={minoUrl} class="{inputClass} font-mono" />
					<span class="font-sans text-micro text-surface-400">The agent on the server reports back here, usually this Mino instance.</span>
				</label>
				<div>
					<Button type="submit" size="lg" disabled={!hostName.trim() || creatingHost}>
						{creatingHost ? 'Creating…' : 'Get install command'}
					</Button>
				</div>
				{#if hostError}
					<span class="font-sans text-micro text-danger-600">{hostError}</span>
				{/if}
			</form>
		{:else}
			<div class="mt-4 flex flex-col gap-2">
				<span class="font-sans text-label text-surface-600">Run this on <span class="font-mono text-surface-900">{createdHost.name}</span>, then it shows up here once the agent connects:</span>
				<div class="flex items-stretch gap-2">
					<code class="flex-1 px-3 py-2.5 rounded-lg bg-surface-950 text-surface-100 font-mono text-micro overflow-x-auto whitespace-pre">{installCommand}</code>
					<button type="button" on:click={copyCommand} class="flex-shrink-0 px-3 rounded-lg bg-surface-200 text-surface-700 font-sans font-medium text-label border border-surface-300 cursor-pointer hover:bg-surface-300">{copied ? 'Copied' : 'Copy'}</button>
				</div>
				<div class="inline-flex items-center gap-2 font-mono text-micro text-surface-500">
					<span class="w-1.5 h-1.5 rounded-full bg-surface-400 animate-pulse"></span>
					Waiting for {createdHost.name} to connect…
				</div>
			</div>
		{/if}
	{:else}
		<form class="mt-4 flex flex-col gap-2" on:submit|preventDefault={addUrlService}>
			<div class="flex flex-col sm:flex-row gap-2">
				<input type="text" placeholder="Service name (e.g. payments-api)" bind:value={urlName} class="{inputClass} font-sans flex-1" />
				<input type="url" placeholder="https://api.example.com/health" bind:value={url} class="{inputClass} font-mono flex-[2] placeholder:text-surface-400" />
			</div>
			{#if urlError}
				<span class="font-sans text-micro text-danger-600">{urlError}</span>
			{/if}
			<div>
				<Button type="submit" size="lg" disabled={!urlName.trim() || !url.trim() || addingUrl}>
					{addingUrl ? 'Adding…' : 'Add URL check'}
				</Button>
			</div>
		</form>
	{/if}

	<div class="mt-7 pt-5 border-t border-surface-200">
		<div class="font-mono text-[11px] text-surface-500 tracking-widest uppercase">next, when you're ready</div>
		<div class="mt-3 flex flex-col divide-y divide-surface-100 border-t border-b border-surface-100">
			{#each nextSteps as step}
				<div class="flex items-start gap-3.5 py-3">
					<span
						class="mt-0.5 w-5 h-5 rounded-full flex-shrink-0 inline-flex items-center justify-center font-mono text-[11px] {step.done
							? 'bg-surface-900 text-white'
							: 'border border-surface-300 text-surface-400'}"
					>
						{step.done ? '✓' : '·'}
					</span>
					<span class="flex-1 min-w-0">
						<span class="block font-sans font-medium text-sm text-surface-900">{step.title}</span>
						<span class="block mt-0.5 font-sans text-label leading-snug text-surface-500">{step.body}</span>
					</span>
					<button
						type="button"
						on:click={() => goto('/settings')}
						class="flex-shrink-0 mt-0.5 bg-transparent border-none cursor-pointer font-sans text-micro text-surface-500 underline underline-offset-[3px] decoration-surface-300 hover:text-surface-900"
					>
						{step.done ? 'change' : step.cta}
					</button>
				</div>
			{/each}
		</div>
	</div>
</div>
