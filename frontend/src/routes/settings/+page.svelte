<script lang="ts">
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { servicesNeedRefresh, servicesStore } from '$lib/stream';
	import { isOwner } from '$lib/auth';
	import AutonomyToggle from '$lib/components/AutonomyToggle.svelte';
	import type { Host, Service, TeamMember, User, UserSettings } from '$lib/types';

	let user: User | null = null;

	let teamMembers: TeamMember[] = [];
	let newMemberName = '';
	let newMemberEmail = '';
	let newMemberPassword = '';
	let addingMember = false;
	let teamError: string | null = null;
	let settings: UserSettings | null = null;
	let services: Service[] = [];
	let hosts: Host[] = [];

	let editName = '';
	let editPhone = '';
	let savingProfile = false;

	const serverUrl = typeof window !== 'undefined' ? window.location.origin : '';

	let newHostName = '';
	let newHostBackendUrl = serverUrl;
	let addingHost = false;
	let addHostError: string | null = null;
	let showHostCommandId: string | null = null;
	let copied = false;

	let newUrlName = '';
	let newUrl = '';
	let addingUrl = false;

	let loadError: string | null = null;
	let loadAttempts = 0;

	let installBackendUrl = serverUrl;

	let editLlmProvider = 'deepseek';
	let editLlmModel = 'deepseek-v4-flash';
	let editLlmApiKey = '';
	let savingLlm = false;
	let llmSavedMessage: string | null = null;

	$: autonomy = settings?.autonomy ?? 'auto_fix';
	$: profileDirty = user && (editName.trim() !== user.name || editPhone.trim() !== (user.phone ?? ''));
	$: llmSettingsDirty = settings && (
		editLlmProvider !== settings.llm_provider ||
		editLlmModel !== settings.llm_model ||
		editLlmApiKey.trim() !== ''
	);
	$: llmApiKeyLabel = settings?.llm_api_key
		? `API key (${settings.llm_api_key})`
		: 'API key';

	onMount(() => {
		load();
		return () => {
			stopAddHostPoll();
			unsubscribeServices();
		};
	});

	async function load() {
		loadError = null;
		loadAttempts += 1;
		const [meRes, settingsRes, servicesRes, hostsRes] = await Promise.allSettled([
			api.me(),
			api.settings.get(),
			api.services.list(),
			api.hosts.list(),
		]);

		if (meRes.status === 'rejected') {
			loadError = meRes.reason instanceof Error ? meRes.reason.message : String(meRes.reason);
			return;
		}

		user = meRes.value;
		editName = user.name;
		editPhone = user.phone ?? '';

		if (settingsRes.status === 'fulfilled') {
			settings = settingsRes.value;
			editLlmProvider = settings.llm_provider;
			editLlmModel = settings.llm_model;
			editLlmApiKey = '';
		} else {
			console.error('settings failed', settingsRes.reason);
		}

		if (servicesRes.status === 'fulfilled') {
			services = servicesRes.value;
			servicesStore.set(services);
		} else {
			console.error('services failed', servicesRes.reason);
		}

		if (hostsRes.status === 'fulfilled') {
			hosts = hostsRes.value;
		} else {
			console.error('hosts failed', hostsRes.reason);
		}

		if (user.role === 'owner') {
			loadTeam();
		}
	}

	let memberServers: Record<string, string[]> = {};

	async function loadTeam() {
		try {
			teamMembers = await api.team.list();
			const operators = teamMembers.filter((m) => m.role === 'operator');
			const grants = await Promise.all(operators.map((m) => api.team.getServers(m.id)));
			const next: Record<string, string[]> = {};
			operators.forEach((m, i) => (next[m.id] = grants[i]));
			memberServers = next;
		} catch (e) {
			console.error('team list failed', e);
		}
	}

	async function toggleMemberServer(memberId: string, hostId: string) {
		const cur = memberServers[memberId] ?? [];
		const next = cur.includes(hostId) ? cur.filter((h) => h !== hostId) : [...cur, hostId];
		const saved = await api.team.setServers(memberId, next);
		memberServers = { ...memberServers, [memberId]: saved };
	}

	async function addMember() {
		teamError = null;
		addingMember = true;
		try {
			await api.team.create(newMemberEmail.trim(), newMemberName.trim(), newMemberPassword);
			newMemberName = '';
			newMemberEmail = '';
			newMemberPassword = '';
			await loadTeam();
		} catch (e) {
			teamError = e instanceof ApiError && e.status === 409 ? 'A user with that email already exists.' : 'Could not add member.';
		} finally {
			addingMember = false;
		}
	}

	async function removeMember(id: string) {
		await api.team.delete(id);
		teamMembers = teamMembers.filter((m) => m.id !== id);
	}

	async function updateAutonomy(e: CustomEvent<'auto_fix' | 'ask_first'>) {
		settings = await api.settings.update({ autonomy: e.detail });
	}

	async function saveProfile() {
		savingProfile = true;
		try {
			user = await api.updateMe({ name: editName.trim(), phone: editPhone.trim() });
		} finally {
			savingProfile = false;
		}
	}

	async function saveLlmSettings() {
		if (!settings) return;
		savingLlm = true;
		llmSavedMessage = null;
		try {
			const patch: Partial<UserSettings> = {
				llm_provider: editLlmProvider,
				llm_model: editLlmModel,
			};
			const keyChanged = editLlmApiKey.trim() !== '';
			if (keyChanged) {
				patch.llm_api_key = editLlmApiKey.trim();
			}
			settings = await api.settings.update(patch);
			editLlmApiKey = '';
			llmSavedMessage = keyChanged ? 'Saved with new API key.' : 'Saved.';
			setTimeout(() => {
				llmSavedMessage = null;
			}, 3000);
		} finally {
			savingLlm = false;
		}
	}

	async function addHostInternal(nameOverride?: string, backendUrl?: string) {
		const name = (nameOverride ?? newHostName).trim();
		if (!name) return;
		addingHost = true;
		addHostError = null;
		try {
			const host = await api.hosts.create(name);
			hosts = [...hosts, { ...host, install_backend_url: backendUrl ?? newHostBackendUrl }];
			showHostCommandId = host.id;
			installBackendUrl = backendUrl ?? newHostBackendUrl;
			newHostName = '';
			newHostBackendUrl = serverUrl;
			startAddHostPoll();
		} catch (err) {
			if (err instanceof ApiError && err.status === 409) {
				addHostError = `A server named “${name}” already exists.`;
			} else {
				addHostError = err instanceof Error ? err.message : String(err);
			}
		} finally {
			addingHost = false;
		}
	}

	let addHostPollTimer: ReturnType<typeof setInterval> | null = null;
	function startAddHostPoll() {
		if (addHostPollTimer) clearInterval(addHostPollTimer);
		let attempts = 0;
		addHostPollTimer = setInterval(async () => {
			attempts += 1;
			try {
				services = await api.services.list();
				servicesStore.set(services);
				if (services.length > 0 || attempts >= 15) {
					if (addHostPollTimer) clearInterval(addHostPollTimer);
					addHostPollTimer = null;
				}
			} catch {
				if (attempts >= 15) {
					if (addHostPollTimer) clearInterval(addHostPollTimer);
					addHostPollTimer = null;
				}
			}
		}, 2000);
	}

	function stopAddHostPoll() {
		if (addHostPollTimer) {
			clearInterval(addHostPollTimer);
			addHostPollTimer = null;
		}
	}

	const unsubscribeServices = servicesNeedRefresh.subscribe(async () => {
		try {
			services = await api.services.list();
			servicesStore.set(services);
		} catch {
			// ignore background refresh failures
		}
	});

	async function addHost() {
		addHostInternal();
	}

	function installCommand(host: Host) {
		const baseUrl = host.install_backend_url?.replace(/\/$/, '') ?? installBackendUrl.replace(/\/$/, '');
		const scriptUrl = `${baseUrl}${api.hosts.scriptUrl()}`;
		const token = host.token ?? host.token_preview;
		return `curl -fsSL ${scriptUrl} | python3 - --server ${baseUrl} --token ${token}`;
	}

	async function copyCommand(host: Host) {
		await navigator.clipboard.writeText(installCommand(host));
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}

	async function removeHost(id: string) {
		await api.hosts.delete(id);
		hosts = hosts.filter((h) => h.id !== id);
		if (showHostCommandId === id) showHostCommandId = null;
	}

	async function setHostAutonomy(id: string, value: string) {
		const autonomy = value === '' ? null : (value as 'auto_fix' | 'ask_first');
		const updated = await api.hosts.setAutonomy(id, autonomy);
		hosts = hosts.map((h) => (h.id === id ? { ...h, autonomy: updated.autonomy } : h));
	}

	async function addUrlService() {
		const name = newUrlName.trim();
		const url = newUrl.trim();
		if (!name || !url) return;
		addingUrl = true;
		try {
			const service = await api.services.createUrl(name, url);
			services = [...services, service];
			newUrlName = '';
			newUrl = '';
		} finally {
			addingUrl = false;
		}
	}

</script>

<div class="px-4 sm:px-10 py-7 sm:py-9 pb-20">
	<div class="max-w-[560px] mx-auto">
		<div class="font-serif text-title leading-none text-surface-900 tracking-tight">Settings</div>

		{#if loadError}
			<div class="mt-5 bg-danger-500/10 border border-danger-500/30 rounded-card p-5">
				<div class="font-sans font-semibold text-label text-danger-600">Can't reach the backend</div>
				<div class="mt-1 font-sans text-xs text-danger-600 leading-snug">
					{loadError}
				</div>
				<button
					type="button"
					on:click={load}
					class="mt-3 px-3 py-1.5 rounded-lg bg-danger-600 text-white font-sans font-medium text-label border-none hover:bg-danger-600"
				>
					Retry
				</button>
			</div>
		{/if}

		<div class="mt-7 bg-white border border-surface-300 rounded-card p-5 shadow-card">
			<div class="font-sans font-semibold text-label text-surface-700">Profile</div>
			{#if user}
				<div class="mt-3.5 flex items-center gap-[14px]">
					<span class="w-11 h-11 rounded-full bg-surface-900 text-white inline-flex items-center justify-center font-sans font-semibold text-sm">
						{(user.name || '?').slice(0, 2).toUpperCase()}
					</span>
					<div class="font-mono text-micro text-surface-500">{user.email}</div>
				</div>
				<div class="mt-4 flex flex-col gap-3">
					<label class="flex flex-col gap-1">
						<span class="font-sans text-micro text-surface-500">Name</span>
						<input
							type="text"
							bind:value={editName}
							class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-sans text-sm text-surface-900 focus:outline-none focus:border-surface-500"
						/>
					</label>
					<label class="flex flex-col gap-1">
						<span class="font-sans text-micro text-surface-500">Phone</span>
						<input
							type="text"
							placeholder="+1 (555) 555-0100"
							bind:value={editPhone}
							class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 placeholder:text-surface-400 focus:outline-none focus:border-surface-500"
						/>
					</label>
					<div class="flex justify-end">
						<button
							type="button"
							disabled={!profileDirty || savingProfile}
							on:click={saveProfile}
							class="px-4 py-2 rounded-lg bg-surface-900 text-white font-sans font-medium text-label border-none cursor-pointer hover:bg-surface-800 disabled:opacity-40 disabled:cursor-default"
						>
							{savingProfile ? 'Saving…' : 'Save'}
						</button>
					</div>
				</div>
			{/if}
		</div>

		{#if $isOwner}
		<div class="mt-5 bg-white border border-surface-300 rounded-card p-5 shadow-card">
			<div class="flex justify-between items-start gap-4">
				<span class="flex-1">
						<span class="block font-sans font-semibold text-label text-surface-700">Default autonomy</span>
						<span class="block mt-[3px] font-sans text-xs leading-snug text-surface-500">
							What the agent should do when it sees an incident for the first time.
						</span>
					</span>
					<AutonomyToggle value={autonomy} on:change={(e) => updateAutonomy(e)} />
				</div>
			</div>

		<div class="mt-5 bg-white border border-surface-300 rounded-card p-5 shadow-card">
			<div class="font-sans font-semibold text-label text-surface-700">LLM diagnosis</div>
			<div class="mt-1 font-sans text-xs leading-snug text-surface-500">
				Add a DeepSeek API key to get AI-powered root-cause analysis when an incident opens.
			</div>
			{#if settings?.llm_api_key}
				<div class="mt-3.5 flex flex-col gap-2">
					<div class="font-sans text-label text-surface-700">Configured provider</div>
					<div class="bg-white border border-surface-300 rounded-xl px-4 py-3.5 flex items-center gap-3.5">
						<span class="w-[7px] h-[7px] rounded-full flex-shrink-0 bg-success-500"></span>
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2">
								<div class="font-mono font-medium text-sm text-surface-900 truncate">{settings.llm_provider}</div>
								<span class="px-1.5 py-0.5 rounded bg-surface-100 text-surface-600 font-mono text-micro uppercase tracking-wide">{settings.llm_model}</span>
							</div>
							<div class="mt-[3px] font-mono text-micro text-surface-500 truncate">
								API key {settings.llm_api_key}
							</div>
						</div>
					</div>
				</div>
			{/if}
			<div class="mt-3.5 flex flex-col gap-3">
				<label class="flex flex-col gap-1">
					<span class="font-sans text-micro text-surface-500">Provider</span>
					<select
						bind:value={editLlmProvider}
						class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-sans text-sm text-surface-900 focus:outline-none focus:border-surface-500"
					>
						<option value="deepseek">DeepSeek</option>
						<option value="openrouter">OpenRouter</option>
					</select>
				</label>
				<label class="flex flex-col gap-1">
					<span class="font-sans text-micro text-surface-500">Model</span>
					{#if editLlmProvider === 'openrouter'}
						<input
							type="text"
							bind:value={editLlmModel}
							placeholder="e.g. anthropic/claude-3.5-sonnet"
							class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 focus:outline-none focus:border-surface-500"
						/>
					{:else}
						<select
							bind:value={editLlmModel}
							class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-sans text-sm text-surface-900 focus:outline-none focus:border-surface-500"
						>
							<option value="deepseek-v4-pro">deepseek-v4-pro</option>
							<option value="deepseek-v4-flash">deepseek-v4-flash</option>
						</select>
					{/if}
				</label>
				<label class="flex flex-col gap-1">
					<span class="font-sans text-micro text-surface-500">{llmApiKeyLabel}</span>
					<input
						type="password"
						placeholder={settings?.llm_api_key ? 'Enter a new key to replace the saved one' : 'sk-...'}
						bind:value={editLlmApiKey}
						class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 focus:outline-none focus:border-surface-500"
					/>
				</label>
				<div class="flex justify-between items-center">
					{#if llmSavedMessage}
						<span class="font-sans text-label text-success-600">{llmSavedMessage}</span>
					{:else}
						<span></span>
					{/if}
					<button
						type="button"
						disabled={savingLlm || !llmSettingsDirty}
						on:click={saveLlmSettings}
						class="px-4 py-2 rounded-lg bg-surface-900 text-white font-sans font-medium text-label border-none cursor-pointer hover:bg-surface-800 disabled:opacity-40 disabled:cursor-default"
					>
						{savingLlm ? 'Saving…' : 'Save'}
					</button>
				</div>
			</div>
		</div>


			<div class="mt-5 bg-white border border-surface-300 rounded-card p-5 shadow-card">
				<div class="font-sans font-semibold text-label text-surface-700">Connected servers</div>
				<div class="mt-1 font-sans text-xs leading-snug text-surface-500">
					Install the open-source agent on each server you want to monitor. The agent reports containers and runs <span class="font-mono">docker restart</span> when asked.
				</div>
				<div class="mt-3.5 flex flex-col gap-2.5">
					{#each hosts as host (host.id)}
						<div class="bg-white border border-surface-300 rounded-xl px-4 py-3.5">
							<div class="flex flex-wrap items-center justify-between gap-3">
								<div class="min-w-0">
									<div class="flex items-center gap-2">
										<span class="font-mono font-medium text-sm text-surface-900 truncate">{host.name}</span>
										{#if host.agent_outdated}
											<span class="flex-shrink-0 px-1.5 py-0.5 rounded bg-warning-500/15 text-warning-600 font-sans text-micro font-medium" title="Re-run the install command to update this agent">agent out of date</span>
										{/if}
									</div>
									<div class="mt-[3px] font-mono text-micro text-surface-500">
										{host.token_preview}
										{#if host.last_seen_at}
											· seen {new Date(host.last_seen_at).toLocaleString()}
										{:else}
											· never seen
										{/if}
									</div>
								</div>
								<div class="flex items-center gap-2 flex-shrink-0">
									<select
										value={host.autonomy ?? ''}
										on:change={(e) => setHostAutonomy(host.id, e.currentTarget.value)}
										title="Autonomy for this server"
										class="px-2 py-1.5 rounded-lg bg-white border border-surface-300 font-sans text-label text-surface-700 focus:outline-none focus:border-surface-500"
									>
										<option value="">Fleet default</option>
										<option value="auto_fix">Auto-fix</option>
										<option value="ask_first">Ask first</option>
									</select>
									<button
										type="button"
										on:click={() => {
											showHostCommandId = showHostCommandId === host.id ? null : host.id;
											if (showHostCommandId === host.id) {
												installBackendUrl = host.install_backend_url ?? serverUrl;
											}
										}}
										class="px-3 py-1.5 rounded-lg bg-surface-100 text-surface-700 font-sans font-medium text-label border border-surface-300 hover:bg-surface-200"
									>
										{showHostCommandId === host.id ? 'Hide' : 'Install'}
									</button>
									<button
										type="button"
										on:click={() => removeHost(host.id)}
										class="px-3 py-1.5 rounded-lg text-danger-600 font-sans font-medium text-label border border-surface-300 hover:bg-danger-500/10"
									>
										Remove
									</button>
								</div>
							</div>
							{#if showHostCommandId === host.id}
								<div class="mt-3">
									<div class="font-sans text-micro text-surface-600 mb-1.5">
										Run this on <span class="font-semibold">{host.name}</span>:
									</div>
									<div class="bg-surface-900 text-surface-100 rounded-lg p-3 font-mono text-micro overflow-x-auto whitespace-pre-wrap">
										{installCommand(host)}
									</div>
									<div class="mt-2 flex flex-col gap-2">
										<label class="flex flex-col gap-1">
											<span class="font-sans text-micro text-surface-500">Backend URL</span>
											<input
												type="url"
												bind:value={installBackendUrl}
												placeholder={serverUrl}
												class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 focus:outline-none focus:border-surface-500"
											/>
										</label>
										<div class="flex justify-end">
											<button
												type="button"
												on:click={() => copyCommand(host)}
												class="px-3 py-1.5 rounded-lg bg-surface-900 text-white font-sans font-medium text-label border-none hover:bg-surface-800"
											>
												{copied ? 'Copied!' : 'Copy command'}
											</button>
										</div>
									</div>
								</div>
							{/if}
						</div>
					{/each}
					{#if hosts.length === 0}
						<div class="font-sans text-xs text-surface-500">
							Add a server below to generate the install command. The agent reports that server's Docker containers here.
						</div>
					{/if}
				</div>
				<div class="mt-4 pt-4 border-t border-surface-200">
					<div class="font-sans font-semibold text-label text-surface-700 mb-2">Add server</div>
					{#if addHostError}
						<div class="mb-2 font-sans text-micro text-danger-600 bg-danger-500/10 rounded-lg px-3 py-2">
							{addHostError}
						</div>
					{/if}
					<div class="flex flex-col gap-2">
						<label class="flex flex-col gap-1">
							<span class="font-sans text-micro text-surface-500">Backend URL</span>
							<input
								type="url"
								bind:value={newHostBackendUrl}
								placeholder={serverUrl}
								class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 focus:outline-none focus:border-surface-500"
							/>
						</label>
						<div class="flex gap-2">
							<input
								type="text"
								placeholder="Server name (e.g. prod-web-01)"
								bind:value={newHostName}
								class="flex-1 px-3 py-2 rounded-lg bg-white border border-surface-300 font-sans text-sm text-surface-900 focus:outline-none focus:border-surface-500"
							/>
							<button
								type="button"
								disabled={!newHostName.trim() || addingHost}
								on:click={addHost}
								class="px-4 py-2 rounded-lg bg-surface-900 text-white font-sans font-medium text-label border-none cursor-pointer hover:bg-surface-800 disabled:opacity-40 disabled:cursor-default"
							>
								{addingHost ? 'Adding…' : 'Add server'}
							</button>
						</div>
					</div>
				</div>
			</div>

			<div class="mt-5 bg-white border border-surface-300 rounded-card p-5 shadow-card">
				<div class="font-sans font-semibold text-label text-surface-700">Add URL service</div>
				<div class="mt-1 font-sans text-xs leading-snug text-surface-500">
					Or monitor an external endpoint (not a server) with a URL health check.
				</div>
				<div class="mt-3 flex flex-col gap-2">
					<div class="flex gap-2">
						<input
							type="text"
							placeholder="Name"
							bind:value={newUrlName}
							class="flex-1 px-3 py-2 rounded-lg bg-white border border-surface-300 font-sans text-sm text-surface-900 focus:outline-none focus:border-surface-500"
						/>
						<input
							type="url"
							placeholder="https://api.example.com/health"
							bind:value={newUrl}
							class="flex-[2] px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 placeholder:text-surface-400 focus:outline-none focus:border-surface-500"
						/>
					</div>
					<div class="flex justify-end">
						<button
							type="button"
							disabled={!newUrlName.trim() || !newUrl.trim() || addingUrl}
							on:click={addUrlService}
							class="px-4 py-2 rounded-lg bg-surface-900 text-white font-sans font-medium text-label border-none cursor-pointer hover:bg-surface-800 disabled:opacity-40 disabled:cursor-default"
						>
							{addingUrl ? 'Adding…' : 'Add URL service'}
						</button>
					</div>
				</div>
			</div>

		<div class="mt-5 bg-white border border-surface-300 rounded-card p-5 shadow-card">
			<div class="font-sans font-semibold text-label text-surface-700">Team</div>
			<div class="mt-1 font-sans text-xs leading-snug text-surface-500">
				People who can sign in. Operators act on incidents but can't change settings. Scope each operator to specific servers below — or leave it open for full access.
			</div>
			<div class="mt-3.5 flex flex-col gap-2.5">
				{#each teamMembers as member (member.id)}
					<div class="bg-white border border-surface-300 rounded-xl px-4 py-3">
						<div class="flex items-center justify-between gap-3">
							<div class="min-w-0">
								<div class="font-sans font-medium text-sm text-surface-900 truncate">{member.name}</div>
								<div class="mt-[2px] font-mono text-micro text-surface-500 truncate">{member.email}</div>
							</div>
							<div class="flex items-center gap-2 flex-shrink-0">
								<span class="px-2 py-0.5 rounded-full bg-surface-100 text-surface-600 font-mono text-micro uppercase tracking-wide">{member.role}</span>
								{#if member.role !== 'owner'}
									<button type="button" on:click={() => removeMember(member.id)} class="px-3 py-1.5 rounded-lg text-danger-600 font-sans font-medium text-label border border-surface-300 hover:bg-danger-500/10">Remove</button>
								{/if}
							</div>
						</div>
						{#if member.role === 'operator' && hosts.length}
							<div class="mt-3 pt-3 border-t border-surface-100">
								<div class="font-sans text-micro text-surface-500 mb-1.5">
									{(memberServers[member.id]?.length ?? 0) === 0
										? 'Server access: all servers'
										: `Server access: ${memberServers[member.id].length} of ${hosts.length} servers`}
								</div>
								<div class="flex flex-wrap gap-1.5">
									{#each hosts as host (host.id)}
										{@const on = (memberServers[member.id] ?? []).includes(host.id)}
										<button
											type="button"
											on:click={() => toggleMemberServer(member.id, host.id)}
											title={on ? 'Allowed — click to revoke' : 'Click to allow this server'}
											class="px-2 py-0.5 rounded-md font-mono text-micro border cursor-pointer {on ? 'bg-surface-900 text-white border-surface-900' : 'bg-white text-surface-600 border-surface-300 hover:bg-surface-50'}"
										>{host.name}</button>
									{/each}
								</div>
								<div class="mt-1.5 font-sans text-micro text-surface-400">No servers selected means full access.</div>
							</div>
						{/if}
					</div>
				{/each}
				{#if !teamMembers.some((m) => m.role === 'operator')}
					<div class="font-sans text-xs text-surface-500">No operators yet — add a friend below.</div>
				{/if}
			</div>
			<div class="mt-4 pt-4 border-t border-surface-200">
				<div class="font-sans font-semibold text-label text-surface-700 mb-2">Add operator</div>
				{#if teamError}
					<div class="mb-2 font-sans text-micro text-danger-600 bg-danger-500/10 rounded-lg px-3 py-2">{teamError}</div>
				{/if}
				<div class="flex flex-col gap-2">
					<input type="text" placeholder="Name" bind:value={newMemberName} class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-sans text-sm text-surface-900 focus:outline-none focus:border-surface-500" />
					<input type="email" placeholder="friend@example.com" bind:value={newMemberEmail} class="px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 focus:outline-none focus:border-surface-500" />
					<div class="flex gap-2">
						<input type="password" placeholder="Password" bind:value={newMemberPassword} class="flex-1 px-3 py-2 rounded-lg bg-white border border-surface-300 font-mono text-sm text-surface-900 focus:outline-none focus:border-surface-500" />
						<button type="button" disabled={!newMemberName.trim() || !newMemberEmail.trim() || !newMemberPassword || addingMember} on:click={addMember} class="px-4 py-2 rounded-lg bg-surface-900 text-white font-sans font-medium text-label border-none cursor-pointer hover:bg-surface-800 disabled:opacity-40 disabled:cursor-default">{addingMember ? 'Adding…' : 'Add'}</button>
					</div>
				</div>
			</div>
		</div>
		{/if}
		</div>
	</div>
