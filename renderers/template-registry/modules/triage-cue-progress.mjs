/** Composition-clock drawing: each validated cue starts at zero ink.
 * Settle before its end and the frozen source clock; never borrow global progress.
 */
export function cueInk(seconds, start, stop, activeEnd) {
  const span = Math.min(.45, (stop - start) * .45, activeEnd - start);
  if (!(span > 0)) throw new RangeError('positive validated cue interval required');
  if (seconds <= start) return 0;
  if (seconds >= start + span) return 1;
  const u = (seconds - start) / span;
  return u * u * (3 - 2 * u);
}
