import React, { useEffect, useState } from "react";

const CHICAGO_CSS = `
@font-face {
  font-family: 'Chicago';
  src: url('/fonts/Chicago.woff2') format('woff2'),
       url('/fonts/Chicago.woff') format('woff');
  font-weight: normal;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'ChicagoFLF';
  src: url('/fonts/ChicagoFLF.woff2') format('woff2'),
       url('/fonts/ChicagoFLF.woff') format('woff');
  font-weight: normal;
  font-style: normal;
  font-display: swap;
}
`;

function minutes(h, m = 0) {
  return h * 60 + m;
}

function fmtTimeDisplay(date) {
  let h = date.getHours();
  const m = date.getMinutes();
  h = h % 12 || 12;
  const mm = String(m).padStart(2, "0");
  return `${h}:${mm}`;
}

function computeDensityBuckets(events, dayStart, dayEnd, bucketMinutes = 5) {
  const total = dayEnd - dayStart;
  const n = Math.max(1, Math.ceil(total / bucketMinutes));
  const buckets = new Array(n).fill(0);

  for (const e of events) {
    const s = Math.max(0, e.start - dayStart);
    const en = Math.min(total, e.end - dayStart);
    if (en <= s) continue;

    const startIdx = Math.floor(s / bucketMinutes);
    const endIdx = Math.ceil(en / bucketMinutes);

    for (let i = startIdx; i < endIdx; i++) {
      const bStart = i * bucketMinutes;
      const bEnd = (i + 1) * bucketMinutes;
      const overlap = Math.max(0, Math.min(en, bEnd) - Math.max(s, bStart));
      buckets[i] += overlap;
    }
  }

  const maxBucket = Math.max(1, ...buckets);
  return { buckets, maxBucket };
}

function assignOverlapColumns(evts) {
  const active = [];
  const out = new Map();

  for (const e of evts) {
    for (let i = active.length - 1; i >= 0; i--) {
      if (active[i].end <= e.start) active.splice(i, 1);
    }

    let col = 0;
    const used = new Set(active.map((a) => a.col));
    while (used.has(col)) col++;

    active.push({ end: e.end, col });
    out.set(e.id, col);
  }

  return out;
}

function assignLabelColumnsTop({ items, boxH, minGap = 4 }) {
  const sorted = items.map((d) => ({ ...d })).sort((a, b) => a.desiredTop - b.desiredTop);

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
      cur.push(it);
      curBottom = Math.max(curBottom, it.desiredTop + boxH);
    } else {
      clusters.push(cur);
      cur = [it];
      curBottom = it.desiredTop + boxH;
    }
  }
  if (cur.length) clusters.push(cur);

  const colMap = new Map();
  for (const cluster of clusters) {
    const k = cluster.length;
    cluster.forEach((it, idx) => {
      const col = k - 1 - idx;
      colMap.set(it.id, col);
    });
  }
  return colMap;
}

const DEFAULT_DAY_START = minutes(8, 0);
const DEFAULT_DAY_END = minutes(21, 0);

const TufteDayCalendar = ({
  events = [],
  dayStart = DEFAULT_DAY_START,
  dayEnd = DEFAULT_DAY_END,
  showDensity = false,
}) => {
  const DISPLAY_W = 480;
  const DISPLAY_H = 800;
  const PADDING_Y = 24;

  const total = dayEnd - dayStart;
  const pxPerMin = (DISPLAY_H - PADDING_Y * 2) / total;
  const height = Math.floor(total * pxPerMin);

  const hours = [];
  for (let m = Math.ceil(dayStart / 60) * 60; m <= dayEnd; m += 60) hours.push(m);

  const evts = [...events]
    .map((e, i) => ({ id: i, ...e }))
    .sort((a, b) => a.start - b.start || a.end - b.end);

  const gapPx = 2;
  const yRanges = evts.map((e) => ({
    id: e.id,
    y1: Math.round((e.start - dayStart) * pxPerMin),
    y2: Math.round((e.end - dayStart) * pxPerMin),
  }));
  for (let i = 1; i < yRanges.length; i++) {
    const prev = yRanges[i - 1];
    const cur = yRanges[i];
    if (Math.abs(cur.y1 - prev.y2) <= 0.5) {
      prev.y2 -= gapPx / 2;
      cur.y1 += gapPx / 2;
    }
  }

  const LABEL_LINE_H = 11;
  const LABEL_BOX_H = LABEL_LINE_H * 2 + 4;
  const labelItems = evts.map((e, i) => ({ id: e.id, desiredTop: yRanges[i].y1 }));

  const labelCols = assignLabelColumnsTop({ items: labelItems, boxH: LABEL_BOX_H, minGap: 4 });

  const labelMap = new Map(labelItems.map((d) => [d.id, { top: d.desiredTop }]));
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
      let t = Math.max(desired, lastBottom + 2);
      t = Math.min(t, height - LABEL_BOX_H);
      labelMap.set(it.id, { top: t });
      lastBottom = t + LABEL_BOX_H;
    }
  }

  const columns = assignOverlapColumns(evts);
  const { buckets, maxBucket } = computeDensityBuckets(evts, dayStart, dayEnd, 10);

  const TICK_WIDTH = 3.5;
  const TICK_SHIFT = 2 * TICK_WIDTH;
  const axisInset = 0;
  const axisX = axisInset;
  const labelOffsetLeft = 28;
  const labelColGap = 10;
  const labelColWidth = 160;
  const textOffset = -3;

  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);
  const showDotHigh = time.getSeconds() >= 30;

  return (
    <div
      className="relative bg-white text-neutral-900 antialiased border border-black"
      style={{
        width: DISPLAY_W,
        height: DISPLAY_H,
        fontFamily: 'Chicago, ChicagoFLF, Chicagoflf, Geneva, Verdana, sans-serif',
      }}
    >
      <style dangerouslySetInnerHTML={{ __html: CHICAGO_CSS }} />

      <div className="absolute top-3 right-3 text-[32px] font-medium tracking-tight flex items-center select-none">
        <span className="text-[20px]">{fmtTimeDisplay(time)}</span>
        <span
          className={`text-[12px] leading-none relative ml-[2px] mr-[3px] ${
            showDotHigh ? 'translate-y-[-5px]' : 'translate-y-[5px]'
          }`}
          style={{ color: '#999999' }}
        >
          •
        </span>
        <span className="text-[20px]">{time.getHours() >= 12 ? 'PM' : 'AM'}</span>
      </div>

      <div className="px-2" style={{ paddingTop: PADDING_Y, height: DISPLAY_H - PADDING_Y * 2 }}>
        <div className="grid" style={{ gridTemplateColumns: '72px 1fr', columnGap: '16px' }}>
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

          <div className="relative" style={{ height, left: '-20px' }}>
            <svg className="absolute inset-0 w-full h-full overflow-visible">
              <line x1={axisX} y1={0} x2={axisX} y2={height} stroke="#bdbec2" strokeWidth="0.5" />

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

              {(() => {
                const h = time.getHours();
                const nowMin = h * 60 + time.getMinutes();
                if (nowMin >= dayStart && nowMin <= dayEnd) {
                  return <circle cx={axisX} cy={Math.round((nowMin - dayStart) * pxPerMin)} r={5} fill="#1f2937" />;
                }
                return null;
              })()}

              {evts.map((e, i) => {
                const r = yRanges[i];
                const col = columns.get(e.id) || 0;
                const dx = col * TICK_SHIFT;
                const tickX = axisX + dx;

                const lblCol = labelCols.get(e.id) || 0;
                const labelLeft = labelOffsetLeft + lblCol * (labelColWidth + labelColGap);

                return (
                  <g key={e.id}>
                    <line x1={tickX} y1={r.y1} x2={tickX} y2={r.y2} stroke="#111827" strokeWidth={3.5} strokeLinecap="butt" />
                    <line x1={tickX} y1={r.y1} x2={labelLeft} y2={r.y1} stroke="#d1d5db" strokeWidth="0.6" />
                  </g>
                );
              })}
            </svg>

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
                      {`${Math.floor(e.start / 60) % 12 || 12}:${String(e.start % 60).padStart(2, '0')}–${
                        Math.floor(e.end / 60) % 12 || 12
                      }:${String(e.end % 60).padStart(2, '0')} ${e.where ? `· ${e.where}` : ''}`}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {showDensity && (
          <div className="mt-2">
            <svg className="w-full h-16" viewBox={`0 0 ${buckets.length} 24`}>
              <g transform="translate(16,0)">
                <line x1="0" y1="23" x2={buckets.length - 32} y2="23" stroke="#e5e7eb" strokeWidth="0.6" />
                <polyline
                  fill="none"
                  stroke="#111827"
                  strokeWidth=".6"
                  points={buckets
                    .map((v, i) => `${i},${23 - (v / Math.max(1, maxBucket)) * 20}`)
                    .join(" ")}
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
