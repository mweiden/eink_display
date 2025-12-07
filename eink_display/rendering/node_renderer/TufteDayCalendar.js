import React, { useEffect, useState } from "react";

/**
 * TufteDayCalendar (React)
 *
 * Minimal, information-dense single-day calendar using Tufte-style design:
 * - One vertical spine (timeline) with hour markers (light ink) and event ticks (dark ink)
 * - Labels live in narrow text columns to the right; leaders connect ticks → labels
 * - Overlapping events stagger horizontally; label collisions are resolved per column
 * - Optional bottom density sparkline (disabled by default here)
 * - Classic Macintosh "Chicago" font via @font-face (you must host the files)
 */

// Inline CSS to register Chicago font faces. Place font files at the referenced URLs.
const CHICAGO_CSS = `
@font-face {
  font-family: 'Geneva';
  font-weight: normal;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Geneva';
  font-weight: normal;
  font-style: normal;
  font-display: swap;
}
`;

// Convenience: convert hour/minute to absolute minutes (e.g., minutes(13,45) → 825)
function minutes(h, m = 0) { return h * 60 + m; }

// Live clock formatter (12-hour time: HH:MM)
function fmtTimeDisplay(date) {
  let h = date.getHours();
  const m = date.getMinutes();
  h = h % 12 || 12;
  const mm = String(m).padStart(2, "0");
  return `${h}:${mm}`;
}

/**
 * Buckets per-bucket covered minutes to visualize schedule density as a sparkline.
 * We add the *amount of overlap (in minutes)* contributed by each event to each bucket.
 */
function computeDensityBuckets(events, dayStart, dayEnd, bucketMinutes = 5) {
  const total = dayEnd - dayStart;                 // total minutes displayed
  const n = Math.max(1, Math.ceil(total / bucketMinutes));
  const buckets = new Array(n).fill(0);            // minutes-covered accumulator per bucket

  for (const e of events) {
    // Clamp event to viewport; everything is in absolute minutes of the day
    const s = Math.max(0, e.start - dayStart);
    const en = Math.min(total, e.end - dayStart);
    if (en <= s) continue;                         // no overlap with viewport

    // Identify buckets intersected by [s, en)
    const startIdx = Math.floor(s / bucketMinutes);
    const endIdx = Math.ceil(en / bucketMinutes);

    // Distribute the overlap length into each bucket it crosses
    for (let i = startIdx; i < endIdx; i++) {
      const bStart = i * bucketMinutes;
      const bEnd = (i + 1) * bucketMinutes;
      const overlap = Math.max(0, Math.min(en, bEnd) - Math.max(s, bStart));
      buckets[i] += overlap;
    }
  }

  const maxBucket = Math.max(1, ...buckets);       // guard against divide-by-zero later
  return { buckets, maxBucket };
}

/**
 * assignOverlapColumns
 *
 * Greedy scanline that assigns a small integer column index to each event so
 * simultaneous events can be horizontally staggered (visual deconfliction of ticks).
 *
 * Input must be sorted by (start, end) ascending.
 */
function assignOverlapColumns(evts) {
  const active = [];               // active intervals with { end, col }
  const out = new Map();           // event.id → column idx

  for (const e of evts) {
    // Expire intervals that have ended by e.start
    for (let i = active.length - 1; i >= 0; i--) {
      if (active[i].end <= e.start) active.splice(i, 1);
    }

    // Choose the smallest nonnegative column not used by actives
    let col = 0;
    const used = new Set(active.map(a => a.col));
    while (used.has(col)) col++;

    active.push({ end: e.end, col });
    out.set(e.id, col);
  }

  return out;
}

/**
 * assignLabelColumnsTop
 *
 * Determine which *text* column each label should inhabit based on desired top
 * positions and a simple vertical box height estimate. We cluster labels that
 * would collide vertically into a group, then sweep-assignment so earlier items
 * in the cluster push later items to columns further to the left, producing a
 * rightward trending leader flow.
 */
function assignLabelColumnsTop({ items, boxH, minGap = 4 }) {
  // Sort items by their desired top so we can scan downwards
  const sorted = items.map(d => ({ ...d })).sort((a, b) => a.desiredTop - b.desiredTop);

  // Greedy clustering by vertical overlap (boxH + minGap)
  const clusters = [];
  let cur = [];
  let curBottom = -Infinity;

  for (const it of sorted) {
    if (cur.length === 0) {
      cur.push(it);
      curBottom = it.desiredTop + boxH;
      continue;
    }
    if (it.desiredTop < curBottom + minGap) {
      // still overlapping this cluster
      cur.push(it);
      curBottom = Math.max(curBottom, it.desiredTop + boxH);
    } else {
      // close current, start new
      clusters.push(cur);
      cur = [it];
      curBottom = it.desiredTop + boxH;
    }
  }
  if (cur.length) clusters.push(cur);

  // For each cluster, assign columns right→left so the top-most item ends far right
  const colMap = new Map(); // id → label column idx
  for (const cluster of clusters) {
    const k = cluster.length;
    cluster.forEach((it, idx) => {
      const col = k - 1 - idx; // earliest (top) → rightmost column
      colMap.set(it.id, col);
    });
  }
  return colMap;
}

const sampleEvents = [
  { title: "Design Review", where: "MTV–Aristotle", start: minutes(9, 0), end: minutes(9, 45) },
  { title: "Rachel / Matt", where: "MTV–Descartes", start: minutes(11, 0), end: minutes(11, 30) },
  { title: "Team Lunch", where: "Cafeteria", start: minutes(13, 0), end: minutes(14, 0) },
  { title: "Recruiting Sync", where: "MTV–DaVinci", start: minutes(13, 45), end: minutes(14, 30) },
  { title: "Luke / Matt", where: "MTV–Descartes", start: minutes(16, 0), end: minutes(16, 35) },
  { title: "Kevin / Matt", where: "MTV–Descartes", start: minutes(16, 30), end: minutes(17, 0) },
];

/**
 * Main component
 */
const TufteDayCalendar = ({
  events = sampleEvents,             // list of { title, where, start, end }
  dayStart = minutes(8, 0),          // inclusive minute
  dayEnd = minutes(21, 0),           // inclusive minute
  showDensity = false,               // toggle for sparkline at bottom
}) => {
  // Canvas (portrait mock for e‑ink prototype) and padding
  const DISPLAY_W = 480;
  const DISPLAY_H = 800;
  const PADDING_Y = 24;              // room at top/bottom for labels & clock

  // Coordinate mapping: minute → pixel along y
  const total = dayEnd - dayStart;
  const pxPerMin = (DISPLAY_H - PADDING_Y * 2) / total;
  const height = Math.floor(total * pxPerMin);

  // Build hour label ticks (on rounded hours inside viewport)
  const hours = [];
  for (let m = Math.ceil(dayStart / 60) * 60; m <= dayEnd; m += 60) hours.push(m);

  // Normalize events with stable ids and sorted order for scanline algorithms
  const evts = [...events]
    .map((e, i) => ({ id: i, ...e }))
    .sort((a, b) => a.start - b.start || a.end - b.end);

  // Create tiny gaps between directly abutting meetings so the dark ticks don't merge
  const gapPx = 2;
  const yRanges = evts.map(e => ({
    id: e.id,
    y1: Math.round((e.start - dayStart) * pxPerMin),
    y2: Math.round((e.end - dayStart) * pxPerMin),
  }));
  for (let i = 1; i < yRanges.length; i++) {
    const prev = yRanges[i - 1];
    const cur = yRanges[i];
    if (Math.abs(cur.y1 - prev.y2) <= 0.5) { // nearly touching → add a sliver gap
      prev.y2 -= gapPx / 2;
      cur.y1 += gapPx / 2;
    }
  }

  // Label placement preparation
  const LABEL_LINE_H = 11;                  // estimate: single text line height
  const LABEL_BOX_H = LABEL_LINE_H * 2 + 4; // two lines + breathing room
  const labelItems = evts.map((e, i) => ({ id: e.id, desiredTop: yRanges[i].y1 }));

  // Column selection (which text column to use) based on vertical clustering
  const labelCols = assignLabelColumnsTop({ items: labelItems, boxH: LABEL_BOX_H, minGap: 4 });

  // Per-column vertical anti-collision: push labels downward within their column
  const labelMap = new Map(labelItems.map(d => [d.id, { top: d.desiredTop }]));
  const byCol = new Map();
  for (const it of labelItems) {
    const col = labelCols.get(it.id) || 0;
    if (!byCol.has(col)) byCol.set(col, []);
    byCol.get(col).push(it);
  }
  for (const [col, arr] of byCol.entries()) {
    arr.sort((a, b) => a.desiredTop - b.desiredTop);
    let lastBottom = -Infinity;
    for (const it of arr) {
      const desired = labelMap.get(it.id)?.top ?? 0;
      let t = Math.max(desired, lastBottom + 2);        // maintain min vertical gap
      t = Math.min(t, height - LABEL_BOX_H);            // clamp within viewport
      labelMap.set(it.id, { top: t });
      lastBottom = t + LABEL_BOX_H;
    }
  }

  // Compute overlap columns for the dark vertical ticks (stagger when overlapping)
  const columns = assignOverlapColumns(evts);

  // Optional density series (kept at 10-min buckets here to be light-weight)
  const { buckets, maxBucket } = computeDensityBuckets(evts, dayStart, dayEnd, 10);

  // Layout constants — kept small (low-ink) to match Tufte’s ethos
  const TICK_WIDTH = 3.5;            // thickness of event ticks on the spine
  const TICK_SHIFT = 2 * TICK_WIDTH; // horizontal offset between overlap columns

  // We intentionally shifted the whole timeline 20px left earlier.
  const axisInset = 0;               // spine X (previously 10; now at left grid edge)
  const axisX = axisInset;

  // Label columns geometry (start further left due to the 20px shift)
  const labelOffsetLeft = 28;        // X of the first label column
  const labelColGap = 10;            // gap between label columns
  const labelColWidth = 160;         // width per label column
  const textOffset = -3;             // nudge so leader meets near top of text block

  // Live time (top-right) and the animated dot that toggles vertical position each half-minute
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);
  const showDotHigh = time.getSeconds() >= 30;

  return (
    <div
      className="relative bg-white text-neutral-900 antialiased border border-black"
      style={{ width: DISPLAY_W, height: DISPLAY_H, fontFamily: 'Chicago, ChicagoFLF, Chicagoflf, Geneva, Verdana, sans-serif' }}
    >
      {/* Inject the @font-face rules for Chicago */}
      <style dangerouslySetInnerHTML={{ __html: CHICAGO_CSS }} />

      {/* Top-right live clock with the half-minute dot wobble */}
      <div className="absolute top-3 right-3 text-[32px] font-medium tracking-tight flex items-center select-none">
        <span className="text-[20px]">{fmtTimeDisplay(time)}</span>
        <span className={`text-[12px] leading-none relative ml-[2px] mr-[3px] ${showDotHigh ? 'translate-y-[-5px]' : 'translate-y-[5px]'}`} style={{ color: '#999999' }}>•</span>
        <span className="text-[20px]">{time.getHours() >= 12 ? 'PM' : 'AM'}</span>
      </div>

      {/* Main grid: left column = hour labels; right = spine/ticks/labels */}
      <div className="px-2" style={{ paddingTop: PADDING_Y, height: DISPLAY_H - PADDING_Y * 2 }}>
        <div className="grid" style={{ gridTemplateColumns: '72px 1fr', columnGap: '16px' }}>
          {/* Hour labels column (shifted left 20px as requested) */}
          <div className="relative" style={{ height, left: '-20px', top: '-5px' }}>
            {hours.map((m) => (
              <div
                key={m}
                className="absolute w-full pr-1 text-right text-[13px] text-neutral-700 select-none"
                style={{ top: Math.round((m - dayStart) * pxPerMin) - 6 }}
              >
                {`${Math.floor(m / 60) % 12 || 12}${m / 60 >= 12 ? ' PM' : ' AM'}`}
              </div>
            ))}
          </div>

          {/* Timeline pane (also shifted left 20px) */}
          <div className="relative" style={{ height, left: '-20px' }}>
            <svg className="absolute inset-0 w-full h-full overflow-visible">
              {/* Spine (light gray) */}
              <line x1={axisX} y1={0} x2={axisX} y2={height} stroke="#bdbec2" strokeWidth="0.5" />

              {/* Hour & half-hour tick guides (hairlines) */}
              {hours.map((m) => {
                const y = Math.round((m - dayStart) * pxPerMin);
                const yHalf = y + Math.round(30 * pxPerMin);
                return (
                  <g key={m}>
                    <line x1={axisX} y1={y} x2={axisX + 5} y2={y} stroke="#bdbec2" strokeWidth="0.5" />
                    {yHalf < height && (
                      <line x1={axisX} y1={yHalf} x2={axisX + 3} y2={yHalf} stroke="#e5e6e8" strokeWidth="0.5" />
                    )}
                  </g>
                );
              })}

              {/* "Now" dot on the spine if current time is within visible range */}
              {(() => {
                const h = time.getHours();
                const nowMin = h * 60 + time.getMinutes();
                if (nowMin >= dayStart && nowMin <= dayEnd) {
                  return (
                    <circle cx={axisX} cy={Math.round((nowMin - dayStart) * pxPerMin)} r={5} fill="#1f2937" />
                  );
                }
                return null;
              })()}

              {/* Event ticks (dark) plus horizontal leaders over to the label columns */}
              {evts.map((e, i) => {
                const r = yRanges[i];
                const col = columns.get(e.id) || 0;
                const dx = col * TICK_SHIFT;          // staggered horizontal offset
                const tickX = axisX + dx;              // base spine X + offset per overlap

                const lblCol = labelCols.get(e.id) || 0;
                const labelLeft = labelOffsetLeft + lblCol * (labelColWidth + labelColGap);

                return (
                  <g key={e.id}>
                    {/* Event vertical mark */}
                    <line x1={tickX} y1={r.y1} x2={tickX} y2={r.y2} stroke="#111827" strokeWidth={3.5} strokeLinecap="butt" />
                    {/* Leader from tick start → label column */}
                    <line x1={tickX} y1={r.y1} x2={labelLeft} y2={r.y1} stroke="#d1d5db" strokeWidth="0.6" />
                  </g>
                );
              })}
            </svg>

            {/* Absolute-positioned label blocks at computed (left, top) */}
            {evts.map((e, i) => {
              const lblCol = labelCols.get(e.id) || 0;
              const left = labelOffsetLeft + lblCol * (labelColWidth + labelColGap);
              const lm = labelMap.get(e.id);
              const top = (lm ? lm.top : yRanges[i].y1) + textOffset;
              return (
                <div key={e.id} className="absolute" style={{ top, left }}>
                  <div className="pl-2" style={{ width: labelColWidth, maxWidth: labelColWidth }}>
                    <div className="text-[15px] leading-tight font-medium">{e.title}</div>
                    <div className="text-[12px] leading-tight text-neutral-600">
                      {`${Math.floor(e.start / 60) % 12 || 12}:${String(e.start % 60).padStart(2, '0')}–${Math.floor(e.end / 60) % 12 || 12}:${String(e.end % 60).padStart(2, '0')} ${e.where ? `· ${e.where}` : ''}`}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Optional density sparkline — disabled by default via showDensity */}
        {showDensity && (
          <div className="mt-2">
            <svg className="w-full h-16" viewBox={`0 0 ${buckets.length} 24`}>
              <g transform="translate(16,0)">
                <line x1="0" y1="23" x2={buckets.length - 32} y2="23" stroke="#e5e7eb" strokeWidth="0.6" />
                <polyline
                  fill="none"
                  stroke="#111827"
                  strokeWidth=".6"
                  points={buckets.map((v, i) => `${i},${23 - (v / Math.max(1, maxBucket)) * 20}`).join(" ")}
                />
              </g>
            </svg>
          </div>
        )}
      </div>
    </div>
  );
};

export default TufteDayCalendar;
