import { derived, writable } from 'svelte/store';
import type { User } from './types';

export const currentUser = writable<User | null>(null);

export const isOwner = derived(currentUser, ($u) => $u?.role === 'owner');
