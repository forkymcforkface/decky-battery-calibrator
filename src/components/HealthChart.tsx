/**
 * Battery Health Trend Chart Component
 * 
 * Displays historical health % as line graph with grid.
 * Uses SVG for performance (no external chart library).
 * 
 * Props:
 * - data: Array of {recorded_at, health_pct} snapshots (sorted ascending by time)
 * - width: SVG width in pixels
 * - height: SVG height in pixels
 */

export function HealthChart({ data, width, height }: { data: { recorded_at: string; health_pct: number }[]; width: number; height: number }) {
  if (data.length < 2) {
    return <div style={{ color: "#666", fontSize: "12px", padding: "8px 0" }}>Not enough data for chart</div>;
  }

  // Layout
  const pad = { top: 16, right: 8, bottom: 24, left: 40 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  // Data (reverse to show newest on right)
  const pts = data.slice().reverse();
  const minH = Math.min(...pts.map(p => p.health_pct)) - 2;
  const maxH = Math.max(...pts.map(p => p.health_pct)) + 2;
  const hRange = maxH - minH || 1;

  // Scaling functions
  const xScale = (i: number) => pad.left + (i / (pts.length - 1)) * plotW;
  const yScale = (v: number) => pad.top + plotH - ((v - minH) / hRange) * plotH;

  // Generate path data for line
  const pathD = pts.map((p, i) => `${i === 0 ? "M" : "L"}${xScale(i).toFixed(1)},${yScale(p.health_pct).toFixed(1)}`).join("");

  // Y-axis ticks & labels
  const yTicks = 4;
  const yLabels: number[] = [];
  for (let i = 0; i <= yTicks; i++) yLabels.push(minH + (hRange * i) / yTicks);

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {/* Grid lines and Y labels */}
      {yLabels.map((v) => (
        <g key={v}>
          <line x1={pad.left} y1={yScale(v)} x2={width - pad.right} y2={yScale(v)}
            stroke="rgba(255,255,255,0.08)" strokeWidth={1} />
          <text x={pad.left - 4} y={yScale(v) + 4} textAnchor="end" fill="#666" fontSize={10}>
            {v.toFixed(0)}%
          </text>
        </g>
      ))}
      
      {/* Line plot */}
      <path d={pathD} fill="none" stroke="#4ade80" strokeWidth={2} strokeLinejoin="round" />
      
      {/* Data points */}
      {pts.map((p, i) => (
        <circle key={i} cx={xScale(i)} cy={yScale(p.health_pct)} r={2.5} fill="#4ade80" />
      ))}
      
      {/* X-axis label */}
      <text x={width / 2} y={height - 2} textAnchor="middle" fill="#666" fontSize={10}>
        Time →
      </text>
    </svg>
  );
}
