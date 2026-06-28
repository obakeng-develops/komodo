<script lang="ts">
	import type { TimelineItem } from '$lib/types';

	export let items: TimelineItem[];

	function dotClass(kind: TimelineItem['kind']) {
		switch (kind) {
			case 'done':
				return 'w-[11px] h-[11px] rounded-full bg-surface-900';
			case 'active':
				return 'w-3 h-3 rounded-full bg-surface-900 shadow-[0_0_0_4px_rgba(38,38,38,0.12)] animate-pulse';
			case 'wait':
				return 'w-3 h-3 rounded-full border-2 border-dashed border-surface-800 box-border';
			default:
				return 'w-[11px] h-[11px] rounded-full border-[1.5px] border-surface-400 bg-white box-border';
		}
	}

	function lineClass(kind: TimelineItem['kind']) {
		return kind === 'done' ? 'bg-surface-900' : 'bg-surface-300';
	}

	function textClass(kind: TimelineItem['kind']) {
		if (kind === 'done') return 'font-sans text-[14px] leading-snug text-surface-700';
		if (kind === 'active' || kind === 'wait') return 'font-sans text-[15px] leading-snug font-semibold text-surface-900';
		return 'font-sans text-[14px] leading-snug text-surface-500';
	}
</script>

<div class="flex flex-col" in:fly={{ y: 8, duration: 240, delay: 80 }}>
	{#each items as item, i}
		<div class="flex gap-3.5 items-stretch">
			<div class="w-3 flex flex-col items-center pt-[3px]">
				<span class="{dotClass(item.kind)} flex-shrink-0 transition-all duration-300"></span>
				{#if i !== items.length - 1}
					<span class="w-0.5 flex-1 min-h-[12px] mt-1 {lineClass(item.kind)} transition-colors duration-300"></span>
				{/if}
			</div>
			<div class="flex-1 pb-3.5">
				<div class={textClass(item.kind)}>{item.text}</div>
				{#if item.time}
					<div class="font-mono text-[11px] text-surface-500 mt-[3px]">{item.time}</div>
				{/if}
			</div>
		</div>
	{/each}
</div>

<script lang="ts" context="module">
	import { fly } from 'svelte/transition';
</script>
