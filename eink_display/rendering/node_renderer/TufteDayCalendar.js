import React from "react";

const DISPLAY_W = 800;
const DISPLAY_H = 480;
const PADDING_X = 36;
const INFO_HEIGHT = 100;
const FOOTER_HEIGHT = 50;
const TIMELINE_HEIGHT = DISPLAY_H - INFO_HEIGHT - FOOTER_HEIGHT;
const LANE_HEIGHT = 40;
const LANE_GAP = 12;
const GRID_TOP_OFFSET = 90;
const GRID_BOTTOM_PADDING = 34;

const sampleEvents = [
  { title: "Design Review", where: "MTV–Aristotle", start: minutes(9, 0), end: minutes(9, 45) },
  { title: "Rachel / Matt", where: "MTV–Descartes", start: minutes(11, 0), end: minutes(11, 30) },
  { title: "Team Lunch", where: "Cafeteria", start: minutes(13, 0), end: minutes(14, 0) },
  { title: "Recruiting Sync", where: "MTV–DaVinci", start: minutes(13, 45), end: minutes(14, 30) },
  { title: "Luke / Matt", where: "MTV–Descartes", start: minutes(16, 0), end: minutes(16, 35) },
  { title: "Kevin / Matt", where: "MTV–Descartes", start: minutes(16, 30), end: minutes(17, 0) },
];

function minutes(h, m = 0) {
  return h * 60 + m;
}

function formatClockParts(date) {
  const h = date.getHours();
  const suffix = h >= 12 ? "PM" : "AM";
  const displayHour = (h % 12) || 12;
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return { time: `${displayHour}:${minutes}`, suffix };
}

function formatHourTick(totalMinutes) {
  const h = Math.floor(totalMinutes / 60);
  const suffix = h >= 12 ? "PM" : "AM";
  const display = (h % 12) || 12;
  return `${display}${suffix}`;
}

function formatHourMinute(totalMinutes) {
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  const suffix = h >= 12 ? "PM" : "AM";
  const display = (h % 12) || 12;
  return `${display}:${String(m).padStart(2, "0")} ${suffix}`;
}

function formatHourMinuteRange(start, end) {
  return `${formatHourMinute(start)} – ${formatHourMinute(end)}`;
}

function assignLanes(events) {
  const laneEnds = [];
  const laneMap = new Map();
  for (const evt of events) {
    let lane = 0;
    while (lane < laneEnds.length && laneEnds[lane] > evt.start) {
      lane += 1;
    }
    if (lane === laneEnds.length) {
      laneEnds.push(evt.end);
    } else {
      laneEnds[lane] = evt.end;
    }
    laneMap.set(evt.id, lane);
  }
  return { laneMap, laneCount: laneEnds.length };
}

const EventList = ({ label, items }) => (
  <div style={{ paddingRight: "24px" }}>
    <div style={{ fontSize: 16, fontWeight: 700, lineHeight: 1.2 }}>{label}:</div>
    {items.length === 0 ? (
      <div style={{ fontSize: 14, lineHeight: 1.2, color: "#4b5563" }}>None scheduled</div>
    ) : (
      <ul style={{ paddingLeft: 0, margin: "6px 0 0 0", listStyle: "none" }}>
        {items.map((evt) => (
          <li key={evt.id} style={{ fontSize: 14, lineHeight: 1.2, color: "#111827" }}>
            <div>
              <span style={{ paddingRight: "6px" }}>•</span>
              <span>{evt.title}</span>
            </div>
            {evt.where ? (
              <div style={{ fontSize: 14, color: "#4b5563", lineHeight: 1.2, marginLeft: "14px" }}>{evt.where}</div>
            ) : null}
            <div style={{ fontSize: 14, color: "#4b5563", lineHeight: 1.2, marginLeft: "14px" }}>
              {formatHourMinuteRange(evt.start, evt.end)}
            </div>
          </li>
        ))}
      </ul>
    )}
  </div>
);

const TufteDayCalendar = ({
  events = sampleEvents,
  dayStart = minutes(6, 0),
  dayEnd = minutes(21, 0),
  currentMinutes,
  currentSeconds,
}) => {
  const now = new Date();
  if (currentMinutes != null) {
    now.setHours(Math.floor(currentMinutes / 60), currentMinutes % 60, currentSeconds ?? 0, 0);
  } else if (currentSeconds != null) {
    now.setSeconds(currentSeconds);
  }
  const nowMinutes = currentMinutes ?? now.getHours() * 60 + now.getMinutes();
  const timeParts = formatClockParts(now);
  const secondsValue = currentSeconds ?? now.getSeconds();

  const evts = [...events]
    .map((evt, idx) => ({ id: idx, ...evt }))
    .sort((a, b) => a.start - b.start || a.end - b.end);

  const { laneMap, laneCount } = assignLanes(evts);
  const totalMinutes = dayEnd - dayStart;
  const timelineWidth = DISPLAY_W - PADDING_X * 2;
  const pxPerMinute = timelineWidth / totalMinutes;

  const hours = [];
  for (let m = Math.ceil(dayStart / 60) * 60; m <= dayEnd; m += 60) {
    hours.push(m);
  }

  const nowEvents = evts.filter((evt) => evt.start <= nowMinutes && evt.end > nowMinutes);
  const nextThreshold = nowEvents.length
    ? Math.max(...nowEvents.map((evt) => evt.end))
    : nowMinutes;
  const futureEvents = evts.filter((evt) => evt.start >= nextThreshold);
  let nextEvents = [];
  if (futureEvents.length) {
    const minStart = futureEvents[0].start;
    nextEvents = futureEvents.filter((evt) => evt.start === minStart);
  }

  const lanesUsed = laneCount || 1;
  const lanesHeight = lanesUsed * LANE_HEIGHT + (lanesUsed - 1) * LANE_GAP;
  const usableHeight = Math.max(0, TIMELINE_HEIGHT - GRID_TOP_OFFSET - GRID_BOTTOM_PADDING);
  const laneAreaTop = Math.max(0, (usableHeight - lanesHeight) / 2);

  const segments = evts
    .map((evt) => {
      const start = Math.max(evt.start, dayStart);
      const end = Math.min(evt.end, dayEnd);
      if (end <= start) {
        return null;
      }
      const x = (start - dayStart) * pxPerMinute + 1;
      const width = Math.max(4, (end - start) * pxPerMinute - 2);
      const lane = laneMap.get(evt.id) || 0;
      const y = laneAreaTop + lane * (LANE_HEIGHT + LANE_GAP);
      return { id: evt.id, x, width, y };
    })
    .filter(Boolean);

  const showCurrent = nowMinutes >= dayStart && nowMinutes <= dayEnd;
  const currentX = (nowMinutes - dayStart) * pxPerMinute;
  const seconds = now.getSeconds();
  const dotHigh = secondsValue >= 30;

  return (
    <div
      style={{
        width: DISPLAY_W,
        height: DISPLAY_H,
        fontFamily: "Geneva, 'Helvetica Neue', Arial, sans-serif",
        backgroundColor: "#fff",
        color: "#111827",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          padding: "28px 36px 0 36px",
        }}
      >
        <div style={{ flex: "1 1 0" }}>
          <EventList label="Now" items={nowEvents} />
        </div>
        <div style={{ flex: "1 1 0", paddingLeft: "24px" }}>
          <EventList label="Next" items={nextEvents} />
        </div>
        <div style={{ minWidth: "170px", textAlign: "right" }}>
          <div
            style={{
              fontSize: 32,
              fontWeight: 500,
              letterSpacing: "-0.01em",
              lineHeight: 1,
              display: "flex",
              justifyContent: "flex-end",
              alignItems: "center",
              gap: 2,
            }}
          >
            <span>{timeParts.time}</span>
            <span
              style={{
                display: "inline-block",
                width: 6,
                fontSize: 12,
                lineHeight: 1,
                transform: `translateY(${dotHigh ? "-9px" : "9px"})`,
              }}
            >
              ●
            </span>
            <span style={{ paddingLeft: "4px", fontSize: 32 }}>{timeParts.suffix}</span>
          </div>
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: PADDING_X,
          top: INFO_HEIGHT + 55,
          width: timelineWidth,
          height: TIMELINE_HEIGHT,
        }}
      >
        <div style={{ position: "absolute", left: 0, top: 66, right: 0, bottom: 34 }}>
          {hours.map((minute) => {
            const offset = (minute - dayStart) * pxPerMinute;
            return (
              <React.Fragment key={minute}>
                <div
                  style={{
                    position: "absolute",
                    left: offset,
                    top: 0,
                    bottom: 32,
                    width: 1,
                    background: "repeating-conic-gradient(#fff 0% 25%, #000 0% 50%) 0 0 / 2px 2px",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: offset - 20,
                    bottom: 0,
                    width: 40,
                    textAlign: "center",
                    fontSize: 13,
                    color: "#374151",
                  }}
                >
                  {formatHourTick(minute)}
                </div>
              </React.Fragment>
            );
          })}

          {showCurrent && (
            <>
              <div
                style={{
                  position: "absolute",
                  left: currentX,
                  top: 0,
                  bottom: 32,
                  width: 2,
                  backgroundColor: "#000",
                  zIndex: 2,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: currentX - 4,
                  top: -8,
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  backgroundColor: "#000",
                  zIndex: 2,
                }}
              />
            </>
          )}

          {segments.map((seg) => (
            <div
              key={seg.id}
              style={{
                position: "absolute",
                left: seg.x,
                top: seg.y,
                width: seg.width,
                height: LANE_HEIGHT,
                borderRadius: 10,
                background: "repeating-conic-gradient(#fff 0% 25%, #000 0% 50%) 0 0 / 2px 2px",
                zIndex: 1,
                //border: "1px solid black",
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default TufteDayCalendar;
