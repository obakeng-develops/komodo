// Short relative time ("just now", "5m ago", "3h ago", "2d ago") from a backend
// timestamp. Backend datetimes are naive UTC, so parse them as UTC, not local.
export function ago(iso: string | null): string | null {
	if (!iso) return null;
	const t = new Date(/[Z+]/.test(iso) ? iso : iso + 'Z').getTime();
	const s = Math.max(0, (Date.now() - t) / 1000);
	if (s < 90) return 'just now';
	const m = s / 60;
	if (m < 90) return `${Math.round(m)}m ago`;
	const h = m / 60;
	if (h < 36) return `${Math.round(h)}h ago`;
	return `${Math.round(h / 24)}d ago`;
}
