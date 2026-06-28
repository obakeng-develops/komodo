<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fade } from 'svelte/transition';
	import { api } from '$lib/api';
	import { activeIncident, logLines, servicesStore } from '$lib/stream';
	import { isOwner } from '$lib/auth';
	import { cardReceive, cardSend, contentFly } from '$lib/animation';
	import AutonomyToggle from '$lib/components/AutonomyToggle.svelte';
	import Timeline from '$lib/components/Timeline.svelte';
	import type { Service, UserSettings } from '$lib/types';

	let settings: UserSettings | null = null;
	let services: Service[] = [];
	let loading = false;
	let viewKey = 'resting';
	let logContainer: HTMLPreElement | null = null;
	let previousIncidentId: string | null = null;

	const MAX_LOG_LINES = 500;

	onMount(() => {
		api.settings.get().then((s) => (settings = s));
		api.services.list().then((s) => {
			services = s;
			servicesStore.set(s);
		});
	});

	$: if ($activeIncident) {
		viewKey = $activeIncident.view;
	} else {
		viewKey = 'resting';
	}

	$: if ($activeIncident?.incident_id !== previousIncidentId) {
		logLines.set([]);
		previousIncidentId = $activeIncident?.incident_id ?? null;
	}

	$: if (logContainer && $logLines.length) {
		logContainer.scrollTop = logContainer.scrollHeight;
	}

	$: trimmedLogLines = $logLines.slice(-MAX_LOG_LINES);

	async function updateAutonomy(mode: 'auto_fix' | 'ask_first') {
		if (!settings) return;
		settings = await api.settings.update({ autonomy: mode });
	}

	async function simulate() {
		loading = true;
		try {
			await api.simulate();
		} finally {
			loading = false;
		}
	}

	async function approve() {
		if ($activeIncident?.incident_id) {
			await api.incidents.approve($activeIncident.incident_id);
		}
	}

	async function takeOver() {
		if ($activeIncident?.incident_id) {
			await api.incidents.takeOver($activeIncident.incident_id);
		}
	}

	async function handBack() {
		if ($activeIncident?.incident_id) {
			await api.incidents.handBack($activeIncident.incident_id);
		}
	}

	async function manualResolve() {
		if ($activeIncident?.incident_id) {
			await api.incidents.resolve($activeIncident.incident_id);
		}
	}

	async function backToWatching() {
		activeIncident.set(null);
	}

	function dotClasses() {
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

	function badgeClasses() {
		if (!$activeIncident) return '';
		const base = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full font-medium text-[11px] font-sans flex-shrink-0';
		if ($activeIncident.view === 'asking') return `${base} border border-dashed border-surface-800 text-surface-800`;
		if ($activeIncident.view === 'takeover') return `${base} border border-dashed border-surface-500 text-surface-500`;
		if ($activeIncident.view === 'resolved') return `${base} border border-surface-300 text-surface-700`;
		return `${base} bg-surface-900 text-white`;
	}

	function badgeLabel() {
		if (!$activeIncident) return '';
		if ($activeIncident.view === 'asking') return '? asking';
		if ($activeIncident.view === 'takeover') return '⌐ you';
		if ($activeIncident.view === 'resolved') return '✓ recovered';
		return '● down';
	}

	function shellClasses() {
		const base = 'bg-white border rounded-2xl shadow-card overflow-hidden transition-colors duration-300';
		if ($activeIncident?.view === 'asking') return `${base} border-surface-800`;
		if (['detecting', 'diagnosing', 'fixing', 'verifying'].includes($activeIncident?.view || '')) {
			return `${base} border-surface-900`;
		}
		return `${base} border-surface-300`;
	}

	function summaryText() {
		const down = services.filter((s) => s.status === 'down').length;
		const degraded = services.filter((s) => s.status === 'degraded').length;
		if (down === 1) return '1 service down';
		if (down > 1) return `${down} services down`;
		if (degraded === 1) return '1 service degraded';
		if (degraded > 1) return `${degraded} services degraded`;
		return 'All services healthy';
	}

	$: statusText = $activeIncident?.status_text || summaryText();
</script>

<div class="px-10 py-9 pb-20">
	<div class="max-w-[680px] mx-auto">
		<div class="flex justify-between items-center mb-6">
			<div class="font-serif text-[22px] leading-none text-surface-900 tracking-tight">Now</div>
			<div class="inline-flex items-center gap-2.5">
				<span class="font-mono text-[11px] text-surface-500 tracking-widest uppercase">autonomy</span>
				{#if $isOwner}
					<AutonomyToggle value={settings?.autonomy || 'auto_fix'} on:change={(e) => updateAutonomy(e.detail)} />
				{:else}
					<span class="px-2 py-0.5 rounded-full bg-surface-100 text-surface-700 font-mono text-[11px]">{settings?.autonomy === 'auto_fix' ? 'auto-fix' : 'ask first'}</span>
				{/if}
			</div>
		</div>

		<div class="relative">
			{#key viewKey}
				<div
					class={shellClasses()}
					in:cardReceive={{ key: viewKey }}
					out:cardSend={{ key: viewKey }}
					aria-live="polite"
				>
					{#if !$activeIncident || $activeIncident.view === 'resting'}
						<div class="p-10" in:contentFly|local>
							<div class="inline-flex items-center gap-2 font-mono text-xs text-surface-500 tracking-wide">
										<span class="w-2 h-2 rounded-full {dotClasses()}"></span>
								{statusText}
							</div>
							<div class="mt-7 font-serif text-[40px] leading-tight text-surface-900 tracking-tight">Everything's fine.</div>
							<div class="mt-4 font-sans text-base leading-relaxed text-surface-600">
								{summaryText()} · watching <strong class="font-semibold text-surface-900">{services.length} service{services.length === 1 ? '' : 's'}</strong>.
							</div>
							<div class="mt-6 pt-5 border-t border-surface-200 flex justify-between items-center">
								<button
									class="bg-transparent border-none cursor-pointer font-mono text-xs text-surface-500 underline underline-offset-[3px] decoration-surface-400 hover:text-surface-900"
									on:click={() => goto('/settings')}
								>
									I watch every container on this host — see them in settings
								</button>
								{#if $isOwner}
									<button
										class="bg-transparent border-none cursor-pointer font-mono text-xs text-surface-500 underline underline-offset-[3px] decoration-surface-400 hover:text-surface-900 disabled:opacity-50"
										on:click={simulate}
										disabled={loading}
									>
										▸ {loading ? 'stopping a container…' : 'stop a container (test recovery)'}
									</button>
								{/if}
							</div>
						</div>
					{:else if $activeIncident.view === 'asking'}
						<div class="p-9" in:contentFly|local>
							<div class="flex justify-between items-start gap-4">
								<div class="font-serif text-[30px] leading-snug text-surface-900 tracking-tight">
									{$activeIncident.service_name} is down. A restart usually fixes it — want me to?
								</div>
								<span class={badgeClasses()}>{badgeLabel()}</span>
							</div>
							<div class="mt-5">
								<Timeline items={$activeIncident.timeline} />
							</div>
							{#if $activeIncident.llm_diagnosis}
								<div class="mt-4 px-4 py-3 rounded-lg bg-surface-50 border border-surface-200">
									<div class="font-mono text-[11px] text-surface-500 tracking-wide uppercase">Diagnosis</div>
									<div class="mt-1.5 font-sans text-[15px] leading-relaxed text-surface-700">
										{$activeIncident.llm_diagnosis}
									</div>
									{#if $activeIncident.llm_confidence}
										<div class="mt-1.5 inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-200 text-surface-700 font-sans text-[11px]">
											confidence: {$activeIncident.llm_confidence}
										</div>
									{/if}
								</div>
							{:else}
								<div class="mt-4 px-4 py-3 rounded-lg bg-surface-50 border border-surface-200">
									<div class="font-mono text-[11px] text-surface-500 tracking-wide uppercase">Diagnosis</div>
									<div class="mt-1.5 font-sans text-[15px] leading-relaxed text-surface-700">
										Diagnosis pending…
									</div>
								</div>
							{/if}
							{#if $activeIncident.proposed_fix}
								<div class="mt-4 px-4 py-3 rounded-lg bg-surface-50 border border-surface-200">
									<div class="font-mono text-[11px] text-surface-500 tracking-wide uppercase">suggested fix</div>
									<div class="mt-1.5 font-sans text-[15px] leading-relaxed text-surface-700">
										<span class="font-mono text-[13px]">{$activeIncident.proposed_fix}</span>
									</div>
								</div>
							{/if}
							<div class="mt-5 border border-surface-300 rounded-xl overflow-hidden">
								<div class="px-4 py-2.5 bg-surface-50 border-b border-surface-300 flex justify-between items-center">
									<div class="font-mono text-[11px] text-surface-600 tracking-wide uppercase">Live logs · {$activeIncident.service_name}</div>
									<button
										type="button"
										on:click={() => logLines.set([])}
										class="font-sans text-[11px] text-surface-500 hover:text-surface-900"
									>
										Clear
									</button>
								</div>
								<pre
									bind:this={logContainer}
									class="h-48 p-4 bg-surface-950 text-surface-200 font-mono text-[12px] leading-snug overflow-y-auto whitespace-pre-wrap"
									>{#if trimmedLogLines.length}{trimmedLogLines.join('\n')}{:else}<span class="text-surface-500">Waiting for log lines from the agent…</span>{/if}</pre>
							</div>
							<div class="mt-5 pt-5 border-t border-surface-200 flex items-center gap-3">
								<button
									class="inline-flex items-center justify-center px-5 py-2.5 rounded-lg bg-surface-900 text-white font-sans font-medium text-sm border-none cursor-pointer hover:bg-surface-800"
									on:click={approve}
								>
									Approve restart
								</button>
								<button
									class="inline-flex items-center justify-center px-4 py-2.5 rounded-lg bg-white text-surface-700 font-sans font-medium text-sm border border-surface-300 cursor-pointer hover:bg-surface-50"
									on:click={takeOver}
								>
									I'll handle it
								</button>
							</div>
						</div>
					{:else if ['detecting', 'diagnosing', 'fixing', 'verifying'].includes($activeIncident.view)}
						<div class="p-9" in:contentFly|local>
							<div class="flex justify-between items-start gap-4">
								<div class="font-serif text-[30px] leading-snug text-surface-900 tracking-tight">
									{$activeIncident.service_name} is wedged. I'm restarting it.
								</div>
								<span class={badgeClasses()}>{badgeLabel()}</span>
							</div>
							<div class="mt-5">
								<Timeline items={$activeIncident.timeline} />
							</div>
							{#if $activeIncident.llm_diagnosis}
								<div class="mt-4 px-4 py-3 rounded-lg bg-surface-50 border border-surface-200">
									<div class="font-mono text-[11px] text-surface-500 tracking-wide uppercase">Diagnosis</div>
									<div class="mt-1.5 font-sans text-[15px] leading-relaxed text-surface-700">
										{$activeIncident.llm_diagnosis}
									</div>
									{#if $activeIncident.llm_confidence}
										<div class="mt-1.5 inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-200 text-surface-700 font-sans text-[11px]">
											confidence: {$activeIncident.llm_confidence}
										</div>
									{/if}
								</div>
							{:else}
								<div class="mt-4 px-4 py-3 rounded-lg bg-surface-50 border border-surface-200">
									<div class="font-mono text-[11px] text-surface-500 tracking-wide uppercase">Diagnosis</div>
									<div class="mt-1.5 font-sans text-[15px] leading-relaxed text-surface-700">
										Diagnosis pending…
									</div>
								</div>
							{/if}
							{#if $activeIncident.proposed_fix}
								<div class="mt-4 px-4 py-3 rounded-lg bg-surface-50 border border-surface-200">
									<div class="font-mono text-[11px] text-surface-500 tracking-wide uppercase">suggested fix</div>
									<div class="mt-1.5 font-sans text-[15px] leading-relaxed text-surface-700">
										<span class="font-mono text-[13px]">{$activeIncident.proposed_fix}</span>
									</div>
								</div>
							{/if}
							<div class="mt-5 border border-surface-300 rounded-xl overflow-hidden">
								<div class="px-4 py-2.5 bg-surface-50 border-b border-surface-300 flex justify-between items-center">
									<div class="font-mono text-[11px] text-surface-600 tracking-wide uppercase">Live logs · {$activeIncident.service_name}</div>
									<button
										type="button"
										on:click={() => logLines.set([])}
										class="font-sans text-[11px] text-surface-500 hover:text-surface-900"
									>
										Clear
									</button>
								</div>
								<pre
									bind:this={logContainer}
									class="h-48 p-4 bg-surface-950 text-surface-200 font-mono text-[12px] leading-snug overflow-y-auto whitespace-pre-wrap"
									>{#if trimmedLogLines.length}{trimmedLogLines.join('\n')}{:else}<span class="text-surface-500">Waiting for log lines from the agent…</span>{/if}</pre>
							</div>
							<div class="mt-5 pt-5 border-t border-surface-200 flex justify-between items-center">
								<div class="flex items-center gap-3">
									<button
										class="inline-flex items-center justify-center px-5 py-2.5 rounded-lg bg-surface-900 text-white font-sans font-medium text-sm border-none cursor-pointer hover:bg-surface-800"
										on:click={takeOver}
									>
										Take over
									</button>
								</div>
								<span class="font-mono text-[12px] text-surface-500 flex items-center gap-1.5">
									<span class="text-surface-900">✓</span> messaged your phone
								</span>
							</div>
						</div>
					{:else if $activeIncident.view === 'resolved'}
						<div class="p-9" in:contentFly|local>
							<div class={badgeClasses()}>{badgeLabel()}</div>
							<div class="mt-4 font-serif text-4xl leading-tight text-surface-900 tracking-tight">{$activeIncident.service_name} is back.</div>
							<div class="mt-3.5 font-sans text-base leading-relaxed text-surface-600">
								Down for <span class="font-mono text-sm text-surface-900">{$activeIncident.elapsed}s</span>. Health check is green again.
							</div>
							{#if $activeIncident.llm_diagnosis}
								<div class="mt-4 px-4 py-3 rounded-lg bg-surface-50 border border-surface-200">
									<div class="font-mono text-[11px] text-surface-500 tracking-wide uppercase">Diagnosis</div>
									<div class="mt-1.5 font-sans text-[15px] leading-relaxed text-surface-700">
										{$activeIncident.llm_diagnosis}
									</div>
									{#if $activeIncident.llm_confidence}
										<div class="mt-1.5 inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-200 text-surface-700 font-sans text-[11px]">
											confidence: {$activeIncident.llm_confidence}
										</div>
									{/if}
								</div>
							{/if}
							{#if $activeIncident.proposed_fix}
								<div class="mt-4 px-4 py-3 rounded-lg bg-surface-50 border border-surface-200">
									<div class="font-mono text-[11px] text-surface-500 tracking-wide uppercase">suggested fix</div>
									<div class="mt-1.5 font-sans text-[15px] leading-relaxed text-surface-700">
										<span class="font-mono text-[13px]">{$activeIncident.proposed_fix}</span>
									</div>
								</div>
							{/if}
							<div class="mt-5 border border-surface-300 rounded-xl overflow-hidden">
								<div class="px-4 py-2.5 bg-surface-50 border-b border-surface-300 flex justify-between items-center">
									<div class="font-mono text-[11px] text-surface-600 tracking-wide uppercase">Logs · {$activeIncident.service_name}</div>
									<button
										type="button"
										on:click={() => logLines.set([])}
										class="font-sans text-[11px] text-surface-500 hover:text-surface-900"
									>
										Clear
									</button>
								</div>
								<pre
									bind:this={logContainer}
									class="h-48 p-4 bg-surface-950 text-surface-200 font-mono text-[12px] leading-snug overflow-y-auto whitespace-pre-wrap"
									>{#if trimmedLogLines.length}{trimmedLogLines.join('\n')}{:else}<span class="text-surface-500">No logs captured.</span>{/if}</pre>
							</div>
							<div class="mt-7 pt-5 border-t border-surface-200 flex justify-between items-center">
								<button
									class="inline-flex items-center justify-center px-5 py-2.5 rounded-lg bg-surface-900 text-white font-sans font-medium text-sm border-none cursor-pointer hover:bg-surface-800"
									on:click={backToWatching}
								>
									Back to watching
								</button>
								<button
									class="bg-transparent border-none cursor-pointer font-mono text-xs text-surface-500 underline underline-offset-[3px] decoration-surface-400 hover:text-surface-900"
									on:click={() => goto('/incidents')}
								>
									added to incidents →
								</button>
							</div>
						</div>
					{:else if $activeIncident.view === 'takeover'}
						<div class="p-9" in:contentFly|local>
							<div class={badgeClasses()}>{badgeLabel()}</div>
							<div class="mt-4 font-serif text-[32px] leading-snug text-surface-900 tracking-tight">Okay — it's yours.</div>
							<div class="mt-3.5 font-serif text-base leading-relaxed text-surface-600">
								I've stepped back and won't touch anything. Here's the fix I was about to run, if it helps:
							</div>
							<div class="mt-4 bg-surface-950 rounded-xl px-[18px] py-4 font-mono text-[13px] leading-relaxed text-surface-300">
								<span class="text-surface-500">$</span> {$activeIncident.proposed_fix || `docker restart ${$activeIncident.service_name}`}
							</div>
							<div class="mt-3.5 flex gap-4">
								<button class="bg-transparent border-none cursor-pointer font-medium text-xs font-mono text-surface-600 underline underline-offset-[3px] decoration-surface-400 hover:text-surface-900">view logs ↗</button>
								<button class="bg-transparent border-none cursor-pointer font-medium text-xs font-mono text-surface-600 underline underline-offset-[3px] decoration-surface-400 hover:text-surface-900">open /healthz ↗</button>
							</div>
							<div class="mt-6 pt-5 border-t border-surface-200 flex items-center gap-3">
								<button
									class="inline-flex items-center justify-center px-5 py-2.5 rounded-lg bg-surface-900 text-white font-sans font-medium text-sm border-none cursor-pointer hover:bg-surface-800"
									on:click={manualResolve}
								>
									Mark it resolved
								</button>
								<button
									class="inline-flex items-center justify-center px-4 py-2.5 rounded-lg bg-white text-surface-700 font-sans font-medium text-sm border border-surface-300 cursor-pointer hover:bg-surface-50"
									on:click={handBack}
								>
									Hand back to the agent
								</button>
							</div>
						</div>
					{/if}
				</div>
			{/key}
		</div>
	</div>
</div>
