import fs from "node:fs";
import { google } from "googleapis";
import Fastify from "fastify";
import puppeteer from "puppeteer";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const TufteDayCalendar = require("./dist/TufteDayCalendar.cjs").default;
const chromium = require("@sparticuz/chromium");

const DEFAULT_WIDTH = 800;
const DEFAULT_HEIGHT = 480;
const DEFAULT_DPR = 2;

const calendarIds = (process.env.CALENDAR_IDS || "")
  .split(",")
  .map((id) => id.trim())
  .filter(Boolean);
const credentialsPath = process.env.GOOGLE_CREDENTIALS_PATH;
const timeZone = process.env.TIMEZONE || process.env.TZ || "UTC";
if (!process.env.TZ) {
  process.env.TZ = timeZone;
}

const SAMPLE_EVENTS = [
  { title: "Design Review", where: "PA–Waverly", start: 9 * 60, end: 9 * 60 + 45 },
  { title: "John / Matt", where: "PA–University", start: 11 * 60, end: 11 * 60 + 30 },
  { title: "Team Lunch", where: "Cafeteria", start: 13 * 60, end: 14 * 60 },
  { title: "Pickup visitor", where: "PA-FrontDesk", start: 13 * 60, end: 13 * 60 + 15 },
  { title: "Recruiting Sync", where: "PA–Cowper", start: 13 * 60 + 45, end: 14 * 60 + 30 },
  { title: "Dave / Matt", where: "PA–Alma", start: 16 * 60, end: 16 * 60 + 30 },
  { title: "Jennifer / Matt", where: "PA–Middlefield", start: 16 * 60 + 30, end: 17 * 60 },
];

const fastify = Fastify({ logger: true });

const executablePath =
  process.env.PUPPETEER_EXECUTABLE_PATH || process.env.CHROMIUM_PATH || null;

let browser;
let page;
let calendarService;

async function ensureBrowser({ width = DEFAULT_WIDTH, height = DEFAULT_HEIGHT, dpr = DEFAULT_DPR } = {}) {
  if (!browser) {
    const launchOptions = {
      headless: "new",
      args: ["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"],
    };

    if (executablePath) {
      launchOptions.executablePath = executablePath;
    } else if (process.platform === "linux") {
      launchOptions.executablePath = await chromium.executablePath();
      launchOptions.args = chromium.args;
      launchOptions.headless = chromium.headless;
    }
    browser = await puppeteer.launch(launchOptions);
  }
  if (!page) {
    page = await browser.newPage();
  }
  await page.setViewport({ width, height, deviceScaleFactor: dpr });
  return { browser, page };
}

function minutesSinceMidnight(date) {
  return date.getHours() * 60 + date.getMinutes();
}

function startOfDay(reference) {
  const start = new Date(reference);
  start.setHours(0, 0, 0, 0);
  return start;
}

function endOfDay(start) {
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return end;
}

async function getCalendarService() {
  if (!credentialsPath || calendarIds.length === 0) {
    return null;
  }

  if (calendarService) {
    return calendarService;
  }

  if (!fs.existsSync(credentialsPath)) {
    fastify.log.warn({ credentialsPath }, "Google credentials not found; falling back to sample events");
    return null;
  }

  const auth = new google.auth.GoogleAuth({
    keyFile: credentialsPath,
    scopes: ["https://www.googleapis.com/auth/calendar.readonly"],
  });

  calendarService = google.calendar({ version: "v3", auth });
  return calendarService;
}

function parseDate(value) {
  if (!value) return null;
  if (value.dateTime) {
    return new Date(value.dateTime);
  }
  if (value.date) {
    return new Date(`${value.date}T00:00:00`);
  }
  return null;
}

function normalizeEvent(raw, fallbackStart) {
  const start = parseDate(raw.start) || fallbackStart;
  const end = parseDate(raw.end) || fallbackStart;

  if (!start || !end) {
    return null;
  }

  return {
    title: raw.summary || "Untitled Event",
    where: raw.location || "",
    start: minutesSinceMidnight(start),
    end: minutesSinceMidnight(end),
  };
}

async function fetchTodaysEvents() {
  try {
    const service = await getCalendarService();
    if (!service) {
      return SAMPLE_EVENTS;
    }

    const now = new Date();
    const start = startOfDay(now);
    const end = endOfDay(start);

    const events = [];

    for (const calendarId of calendarIds) {
      const response = await service.events.list({
        calendarId,
        timeMin: start.toISOString(),
        timeMax: end.toISOString(),
        singleEvents: true,
        orderBy: "startTime",
        timeZone,
      });

      const items = response.data.items || [];
      for (const item of items) {
        const normalized = normalizeEvent(item, start);
        if (normalized) {
          events.push(normalized);
        }
      }
    }

    events.sort((a, b) => a.start - b.start || a.end - b.end || a.title.localeCompare(b.title));
    return events;
  } catch (err) {
    fastify.log.error({ err }, "Failed to fetch Google Calendar events; using sample data");
    return SAMPLE_EVENTS;
  }
}

async function renderCalendarImage({
  events,
  dayStart,
  dayEnd,
  showDensity = false,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  dpr = DEFAULT_DPR,
  format = "png",
  currentMinutes,
  currentSeconds,
}) {
  const { page } = await ensureBrowser({ width, height, dpr });

  const props = {
    events,
    ...(dayStart != null ? { dayStart } : {}),
    ...(dayEnd != null ? { dayEnd } : {}),
    showDensity,
    ...(currentMinutes != null ? { currentMinutes } : {}),
    ...(currentSeconds != null ? { currentSeconds } : {}),
  };

  const html = renderToStaticMarkup(React.createElement(TufteDayCalendar, props));

  const pageHTML = `
      <!doctype html>
      <html>
        <head><meta charset="utf-8" /></head>
        <body style="margin:0;background:#fff;font-family:Geneva, 'Helvetica Neue', Arial, sans-serif;">${html}</body>
      </html>`;

  await page.setViewport({ width, height, deviceScaleFactor: dpr });
  await page.setContent(pageHTML, { waitUntil: "networkidle0" });

  const isPNG = format === "png";
  return page.screenshot({
    fullPage: false,
    type: isPNG ? "png" : "jpeg",
    quality: isPNG ? undefined : 90,
    captureBeyondViewport: false,
    omitBackground: false,
  });
}

let renderChain = Promise.resolve();
function serialize(fn) {
  const next = renderChain.then(fn, fn);
  renderChain = next.catch(() => {});
  return next;
}

fastify.get("/health", async () => ({
  ok: true,
  calendars: calendarIds.length,
  liveData: Boolean(credentialsPath && calendarIds.length > 0),
}));

fastify.get("/", async (request, reply) =>
  serialize(async () => {
    const events = await fetchTodaysEvents();
    const buffer = await renderCalendarImage({ events, format: "png" });
    reply.header("Content-Type", "image/png").send(buffer);
  }).catch((err) => {
    fastify.log.error({ err }, "render failed");
    throw err;
  })
);

fastify.post("/render", async (request, reply) => {
  const {
    events = [],
    dayStart,
    dayEnd,
    showDensity = false,
    width = DEFAULT_WIDTH,
    height = DEFAULT_HEIGHT,
    dpr = DEFAULT_DPR,
    format = "png",
    currentMinutes,
    currentSeconds,
  } = request.body || {};

  return serialize(async () => {
    const buffer = await renderCalendarImage({
      events,
      dayStart,
      dayEnd,
      showDensity,
      width,
      height,
      dpr,
      format,
      currentMinutes,
      currentSeconds,
    });

    const isPNG = format === "png";
    reply.header("Content-Type", isPNG ? "image/png" : "image/jpeg").send(buffer);
  }).catch((err) => {
    fastify.log.error({ err }, "render failed");
    throw err;
  });
});

const port = process.env.PORT || 3000;
const host = "0.0.0.0";
fastify.listen({ port, host }).then(() => {
  console.log(`Render server listening on http://${host}:${port}`);
});

async function shutdown() {
  try {
    if (page) await page.close();
    if (browser) await browser.close();
    await fastify.close();
  } catch (err) {
    console.error("Error during shutdown", err);
  }
}

process.on("SIGINT", () => {
  shutdown().finally(() => process.exit(0));
});
process.on("SIGTERM", () => {
  shutdown().finally(() => process.exit(0));
});
