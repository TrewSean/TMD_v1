"use client";
import { useMemo, useState } from "react";

export interface LineSeries { name: string; color: string; points: { x: number; y: number; label?: string }[] }

/**
 * Minimal SVG line chart: hairline grid, 2px lines, end dots with surface ring,
 * crosshair + tooltip on hover, legend when > 1 series. x is numeric (ms or years).
 */
export default function LineChart({
  series, height = 240, yDp = 2, yUnit = "", xKind = "date", xTicks, xTickLabels,
}: {
  series: LineSeries[]; height?: number; yDp?: number; yUnit?: string; xKind?: "date" | "years"; xTicks?: number[]; xTickLabels?: Record<number, string>;
}) {
  const yFmt = (v: number) => v.toFixed(yDp);
  const xFmt = (v: number) => xTickLabels?.[v] ?? (xKind === "date"
    ? new Date(v).toLocaleDateString("en-AU", { timeZone: "Australia/Sydney", day: "numeric", month: "short" })
    : v < 1 ? `${Math.round(v * 12)}m` : `${v}y`);
  const W = 720, H = height, PAD = { l: 44, r: 16, t: 12, b: 26 };
  const [hover, setHover] = useState<number | null>(null);
  const all = series.flatMap((s) => s.points);
  const { xs, ys, xmin, xmax, ymin, ymax, yt } = useMemo(() => {
    const xsv = all.map((p) => p.x), ysv = all.map((p) => p.y);
    const xmin = Math.min(...xsv), xmax = Math.max(...xsv);
    let ymin = Math.min(...ysv), ymax = Math.max(...ysv);
    const span = ymax - ymin || 1;
    ymin -= span * 0.08; ymax += span * 0.08;
    const step = niceStep((ymax - ymin) / 4);
    const yt: number[] = [];
    for (let v = Math.ceil(ymin / step) * step; v <= ymax; v += step) yt.push(+v.toFixed(6));
    return { xs: xsv, ys: ysv, xmin, xmax, ymin, ymax, yt };
  }, [all]);
  if (all.length === 0) return <div className="text-[12px] text-muted py-8">No data yet.</div>;
  void xs; void ys;
  const sx = (x: number) => PAD.l + ((x - xmin) / ((xmax - xmin) || 1)) * (W - PAD.l - PAD.r);
  const sy = (y: number) => PAD.t + (1 - (y - ymin) / ((ymax - ymin) || 1)) * (H - PAD.t - PAD.b);
  const xt = xTicks ?? linspace(xmin, xmax, 5);

  // hover: nearest x among all points
  const hoverX = hover === null ? null : nearest(all.map((p) => p.x), hover);

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
        onMouseMove={(e) => {
          const r = (e.target as SVGElement).closest("svg")!.getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          setHover(xmin + ((px - PAD.l) / (W - PAD.l - PAD.r)) * (xmax - xmin));
        }}
        onMouseLeave={() => setHover(null)}>
        {yt.map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={sy(v)} y2={sy(v)} stroke="var(--hair)" strokeWidth={1} />
            <text x={PAD.l - 8} y={sy(v) + 3.5} fontSize={10.5} textAnchor="end" fill="var(--muted)" className="num">{yFmt(v)}{yUnit}</text>
          </g>
        ))}
        {xt.map((v) => (
          <text key={v} x={sx(v)} y={H - 8} fontSize={10.5} textAnchor="middle" fill="var(--muted)" className="num">{xFmt(v)}</text>
        ))}
        <line x1={PAD.l} x2={W - PAD.r} y1={sy(ymin)} y2={sy(ymin)} stroke="var(--axis)" strokeWidth={1} />
        {series.map((s) => (
          <g key={s.name}>
            <path d={s.points.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(" ")}
              fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            {s.points.length > 0 && (() => { const p = s.points[s.points.length - 1]; return (
              <g><circle cx={sx(p.x)} cy={sy(p.y)} r={5} fill="var(--surface)" /><circle cx={sx(p.x)} cy={sy(p.y)} r={3.5} fill={s.color} /></g>
            ); })()}
          </g>
        ))}
        {hoverX !== null && (
          <g>
            <line x1={sx(hoverX)} x2={sx(hoverX)} y1={PAD.t} y2={H - PAD.b} stroke="var(--axis)" strokeWidth={1} />
            {series.map((s) => { const p = s.points.find((q) => q.x === hoverX); return p ? (
              <g key={s.name}><circle cx={sx(p.x)} cy={sy(p.y)} r={5} fill="var(--surface)" /><circle cx={sx(p.x)} cy={sy(p.y)} r={3.5} fill={s.color} /></g>
            ) : null; })}
          </g>
        )}
      </svg>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-[12px] mt-1 min-h-[18px]">
        {series.length > 1 && series.map((s) => (
          <span key={s.name} className="inline-flex items-center gap-1.5 text-ink-2"><span className="inline-block w-3 h-[2px]" style={{ background: s.color }} />{s.name}</span>
        ))}
        {hoverX !== null && (
          <span className="ml-auto num text-ink-2">
            {xFmt(hoverX)}{series.map((s) => { const p = s.points.find((q) => q.x === hoverX); return p ? ` · ${series.length > 1 ? s.name + " " : ""}${yFmt(p.y)}${yUnit}` : ""; })}
          </span>
        )}
      </div>
    </div>
  );
}

function niceStep(raw: number) { const p = Math.pow(10, Math.floor(Math.log10(raw))); const m = raw / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p; }
function linspace(a: number, b: number, n: number) { return Array.from({ length: n }, (_, i) => a + ((b - a) * i) / (n - 1)); }
function nearest(xs: number[], x: number) { let best = xs[0]; for (const v of xs) if (Math.abs(v - x) < Math.abs(best - x)) best = v; return best; }
