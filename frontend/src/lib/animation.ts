/* ─────────────────────────────────────────────────────────
 * ANIMATION STORYBOARD
 *
 *    0ms   state triggers crossfade
 *  120ms   card shell crossfades
 *  200ms   inner content group flies in together
 *  320ms   status dot morphs to new state
 *  600ms   all settled
 * ───────────────────────────────────────────────────────── */

import { crossfade, fly } from 'svelte/transition';
import { cubicOut } from 'svelte/easing';

export const TIMING = {
  cardCrossfade: 220,
  contentFly: 260,
  contentDelay: 80,
  dotMorph: 300,
  pulse: 1600,
  settle: 600,
};

export const MOTION = {
  card: {
    duration: `${TIMING.cardCrossfade}ms`,
    easing: 'cubic-bezier(0.22, 0.61, 0.36, 1)',
  },
  content: {
    y: 12,
    duration: `${TIMING.contentFly}ms`,
    delay: `${TIMING.contentDelay}ms`,
    easing: 'cubic-bezier(0.22, 0.61, 0.36, 1)',
  },
  pulse: {
    duration: '1.6s',
    easing: 'ease-in-out',
  },
};

export const [cardSend, cardReceive] = crossfade({
  duration: TIMING.cardCrossfade,
  fallback(node) {
    return fly(node, {
      y: MOTION.content.y,
      duration: TIMING.contentFly,
      delay: TIMING.contentDelay,
      easing: cubicOut,
    });
  },
});

export function contentFly(node: Element) {
  return fly(node, {
    y: MOTION.content.y,
    duration: TIMING.contentFly,
    delay: TIMING.contentDelay,
    easing: cubicOut,
  });
}
