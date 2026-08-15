import type { Obs } from "./types";

/** Last observation with ts <= when. Mirrors tmd/calcs/changes.py: never interpolate. */
export function valueAtOrBefore(points: Obs[], when: Date): Obs | null {
  let best: Obs | null = null;
  for (const p of points) {
    if (new Date(p.ts).getTime() <= when.getTime()) best = p;
    else break;
  }
  return best;
}

/** Change of the latest point vs the last point at least `days` earlier. */
export function changeOver(points: Obs[], days: number, unit: string): number | null {
  if (points.length < 2) return null;
  const last = points[points.length - 1];
  const ref = valueAtOrBefore(points, new Date(new Date(last.ts).getTime() - days * 86_400_000));
  if (!ref || ref.ts === last.ts) return null;
  const a = parseFloat(last.value), b = parseFloat(ref.value);
  if (!isFinite(a) || !isFinite(b)) return null;
  if (unit === "pct") return a - b; // in percentage points; format as bp
  return b === 0 ? null : (a / b - 1) * 100; // percent change
}
