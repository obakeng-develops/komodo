<script lang="ts">
	import { slide } from 'svelte/transition';
	import { api } from '$lib/api';
	import type { Incident, IncidentEvent } from '$lib/types';

	export let incident: Incident;
	export let open: boolean = false;

	// List endpoint omits events; fetch them on first expand.
	let events: IncidentEvent[] | null = incident.events ?? null;

	async function toggle() {
		open = !open;
		if (open && events === null) {
			events = await api.incidents.events(incident.id);
		}
	}

	function badgeClass() {
		const base = 'inline-flex items-center justify-center gap-1 flex-shrink-0 min-w-[78px] px-2.5 py-1 rounded-full font-medium text-xs font-sans';
		if (incident.sure) {
			if (incident.severity === 'down') return `${base} bg-surface-900 text-white`;
			return `${base} bg-surface-700 text-white`;
		}
		if (incident.severity === 'down') return `${base} bg-transparent border-[1.5px] border-dashed border-surface-800 text-surface-800`;
		return `${base} bg-transparent border-[1.5px] border-dashed border-surface-600 text-surface-600`;
	}

	function outcome() {
		switch (incident.status) {
			case 'resolved':
				return { label: '✓ resolved', class: 'font-medium text-xs font-sans text-surface-700 flex items-center gap-1' };
			case 'took_over':
				return { label: '? asked first', class: 'font-medium text-xs font-sans text-surface-600 px-2 py-0.5 border border-dashed border-surface-400 rounded-md' };
			case 'escalated':
				return { label: '↑ escalated', class: 'font-medium text-xs font-sans text-surface-900 flex items-center gap-1' };
			default:
				return { label: incident.action_taken || '', class: 'font-medium text-xs font-sans text-surface-500' };
		}
	}

	function codeStyle(code: string) {
		if (/^5\d\d$/.test(code)) return 'text-surface-400';
		if (code === '200') return 'text-surface-300';
		if (code === 'restart') return 'text-surface-200';
		if (code === 'ask first') return 'text-surface-300';
		if (code === 'paged you') return 'text-surface-400';
		return 'text-surface-400';
	}

	function meterClass() {
		return incident.sure
			? 'block h-full bg-surface-900 rounded-full'
			: 'block h-full rounded-full bg-stripe-pattern text-surface-400/50';
	}

	function extractLogs(diagnosis: string): string | null {
		const idx = diagnosis.indexOf('--- docker logs');
		if (idx === -1) return null;
		return diagnosis.slice(idx);
	}

	function diagnosisWithoutLogs(diagnosis: string): string {
		const idx = diagnosis.indexOf('--- docker logs');
		if (idx === -1) return diagnosis;
		return diagnosis.slice(0, idx).trim();
	}

	let showLogs = false;

	$: logs = extractLogs(incident.diagnosis);
	$: cleanDiagnosis = diagnosisWithoutLogs(incident.diagnosis);

	const oc = outcome();
</script>

<div class="border-t border-surface-300 {open ? 'bg-surface-50' : 'bg-transparent'}">
	<button
		class="w-full bg-transparent border-none cursor-pointer text-left px-5 py-[18px] flex items-center gap-[18px]"
		on:click={toggle}
	>
		<span class={badgeClass()}>{incident.severity === 'down' ? '● down' : '◐ degraded'}</span>
		<span class="flex-1 min-w-0">
			<span class="flex items-center mb-1.5">
				<span class="inline-flex items-center px-2 py-0.5 rounded-md bg-surface-200 border border-surface-300 font-medium text-micro font-mono text-surface-700">
					{incident.service_name || incident.service_id}
				</span>
			</span>
			<span class="block font-serif text-base leading-snug text-surface-900">{incident.summary}</span>
			<span class="block mt-1 font-mono text-label text-surface-500">
				{incident.started_at ? new Date(incident.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''} ·
				{incident.duration_seconds !== null ? `${incident.duration_seconds}s` : '—'} ·
				{incident.action_taken || 'Pending'}
			</span>
		</span>
		<span class={oc.class}>{oc.label}</span>
		<span class="flex-shrink-0 text-lg text-surface-400 transition-transform duration-200 {open ? 'rotate-90' : ''}">›</span>
	</button>

	{#if open}
		<div class="px-5 pb-6" transition:slide={{ duration: 200 }}>
			{#if incident.llm_diagnosis}
				<div class="mt-3 px-4 py-3 rounded-lg bg-surface-50 border border-surface-200">
					<div class="font-mono text-micro text-surface-500 tracking-wide uppercase">Diagnosis</div>
					<div class="mt-1.5 font-sans text-body leading-relaxed text-surface-700">{incident.llm_diagnosis}</div>
					{#if incident.llm_suggested_fix}
						<div class="mt-2 font-mono text-label text-surface-600">{incident.llm_suggested_fix}</div>
					{/if}
					{#if incident.llm_confidence}
						<div class="mt-1.5 inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-200 text-surface-700 font-sans text-micro">confidence: {incident.llm_confidence}</div>
					{/if}
				</div>
			{/if}

			<div class="font-serif text-base leading-relaxed text-surface-700">{cleanDiagnosis}</div>

			{#if logs}
				<div class="mt-3">
					<button
						type="button"
						on:click={() => (showLogs = !showLogs)}
						class="px-3 py-1.5 rounded-lg bg-surface-100 text-surface-700 font-sans font-medium text-label border border-surface-300 hover:bg-surface-200"
					>
						{showLogs ? 'Hide logs' : 'View docker logs'}
					</button>
					{#if showLogs}
						<div
							transition:slide={{ duration: 200 }}
							class="mt-2 bg-surface-950 text-surface-100 rounded-lg p-3 font-mono text-micro overflow-x-auto whitespace-pre-wrap max-h-[300px] overflow-y-auto"
						>
							{logs}
						</div>
					{/if}
				</div>
			{/if}

			{#if events && events.length}
				<div class="mt-3.5 bg-surface-950 rounded-xl px-4 py-3.5 font-mono text-xs leading-7 text-surface-300">
					{#each events as ev}
						<div class="flex gap-2.5 items-baseline">
							<span class="text-surface-600 flex-shrink-0 w-[52px]">{new Date(ev.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
							<span class="flex-shrink-0 w-[120px]">{ev.source}</span>
							<span class="text-surface-600">→</span>
							<span class={codeStyle(ev.code)}>{ev.code}</span>
							<span class="text-surface-600">{ev.note}</span>
						</div>
					{/each}
				</div>
			{/if}

			<div class="mt-3.5 flex items-center gap-3.5">
				<span class="font-mono text-micro text-surface-500 tracking-wide uppercase">confidence</span>
				<span class="font-sans font-medium text-sm text-surface-900">{incident.confidence_pct}%</span>
				<span class="flex-1 h-[5px] rounded-full bg-surface-200 overflow-hidden">
					<span class={meterClass()} style="width: {incident.confidence_pct}%"></span>
				</span>
				<span class="font-mono text-label text-surface-500 flex items-center gap-1.5">
					<span class="text-surface-900">✓</span> messaged your phone
				</span>
			</div>
		</div>
	{/if}
</div>
