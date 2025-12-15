import fs from "node:fs";
import { google } from "googleapis";
import Fastify from "fastify";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createRequire } from "node:module";
import puppeteer from "puppeteer";

const require = createRequire(import.meta.url);
const TufteDayCalendar = require("./dist/TufteDayCalendar.cjs").default;
const supportsSparticuzChromium = process.platform === "linux" && process.arch === "x64";
let chromium = null;
if (supportsSparticuzChromium) {
  try {
    const chromiumModule = require("@sparticuz/chromium");
    chromium = chromiumModule?.default ?? chromiumModule;
  } catch {
    chromium = null;
  }
} else if (process.platform === "linux") {
  console.warn(
    `Skipping @sparticuz/chromium because it only ships Linux x64 binaries (detected ${process.arch}).`
  );
}

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
let calendarService;
let browserPromise;

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

async function fetchTodaysEvents(referenceDate = new Date()) {
  try {
    const service = await getCalendarService();
    if (!service) {
      return SAMPLE_EVENTS;
    }

    const start = startOfDay(referenceDate);
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

function renderCalendarHtml({
  events,
  dayStart,
  dayEnd,
  showDensity = false,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
  dpr = DEFAULT_DPR,
  currentMinutes,
  currentSeconds,
}) {
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

  return pageHTML;
}

function parseReferenceTime(raw) {
  if (!raw) {
    return null;
  }
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    fastify.log.warn({ raw }, "invalid 'now' query parameter; ignoring");
    return null;
  }
  return parsed;
}

async function getBrowser() {
  if (!browserPromise) {
    browserPromise = buildLaunchOptions()
      .then((launchOptions) => puppeteer.launch(launchOptions))
      .catch((err) => {
        browserPromise = undefined;
        throw err;
      });
  }
  return browserPromise;
}

async function buildLaunchOptions() {
  const defaultArgs = ["--no-sandbox", "--disable-setuid-sandbox"];
  const envExecutable =
    process.env.PUPPETEER_EXECUTABLE_PATH ||
    process.env.CHROMIUM_PATH ||
    process.env.CHROME_PATH;
  const options = {
    args: defaultArgs,
    headless: "new",
  };

  if (chromium && process.platform === "linux") {
    try {
      const executablePath = await chromium.executablePath();
      if (executablePath) {
        options.executablePath = executablePath;
      }
      options.args = chromium.args || options.args;
      options.defaultViewport = chromium.defaultViewport || options.defaultViewport;
      options.headless = chromium.headless ?? options.headless;
      options.headless = chromium.headless ?? options.headless;
    } catch (err) {
      console.warn("Failed to resolve chromium executable", err);
    }
  } else if (chromium && process.platform !== "linux") {
    console.warn(
      "Detected @sparticuz/chromium but skipping because it only supports Linux environments."
    );
  }

  if (!options.executablePath && envExecutable) {
    options.executablePath = envExecutable;
  }

  return options;
}

async function renderPngFromHtml(html, { width = DEFAULT_WIDTH, height = DEFAULT_HEIGHT, dpr = DEFAULT_DPR }) {
  const browser = await getBrowser();
  const page = await browser.newPage();
  try {
    await page.setViewport({ width, height, deviceScaleFactor: dpr });
    await page.setContent(html, { waitUntil: "networkidle0" });
    return await page.screenshot({ type: "png" });
  } finally {
    await page.close();
  }
}

async function closeBrowser() {
  if (!browserPromise) {
    return;
  }
  try {
    const browser = await browserPromise;
    await browser.close();
  } catch (err) {
    fastify.log.warn({ err }, "failed to close browser cleanly");
  } finally {
    browserPromise = undefined;
  }
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

fastify.get("/", async (request, reply) => {
  const query = request.query ?? {};
  const referenceTime = parseReferenceTime(query.now);
  return serialize(async () => {
    const now = referenceTime || new Date();
    const events = await fetchTodaysEvents(now);
    const html = renderCalendarHtml({
      events,
      currentMinutes: now.getHours() * 60 + now.getMinutes(),
      currentSeconds: now.getSeconds(),
    });
    reply.header("Content-Type", "text/html; charset=utf-8").send(html);
  }).catch((err) => {
    fastify.log.error({ err }, "render failed");
    throw err;
  });
});

fastify.get("/png", async (request, reply) => {
  const query = request.query ?? {};
  const referenceTime = parseReferenceTime(query.now);
  const width = Number.parseInt(query.width, 10) || DEFAULT_WIDTH;
  const height = Number.parseInt(query.height, 10) || DEFAULT_HEIGHT;
  const dpr = Number.isNaN(Number.parseFloat(query.dpr))
    ? DEFAULT_DPR
    : Number.parseFloat(query.dpr);

  return serialize(async () => {
    const now = referenceTime || new Date();
    const events = await fetchTodaysEvents(now);
    const html = renderCalendarHtml({
      events,
      currentMinutes: now.getHours() * 60 + now.getMinutes(),
      currentSeconds: now.getSeconds(),
      width,
      height,
      dpr,
    });
    const png = await renderPngFromHtml(html, { width, height, dpr });
    reply.header("Content-Type", "image/png").send(png);
  }).catch((err) => {
    fastify.log.error({ err }, "png render failed");
    throw err;
  });
});

fastify.post("/render", async (request, reply) => {
  const {
    events = [],
    dayStart,
    dayEnd,
    showDensity = false,
    width = DEFAULT_WIDTH,
    height = DEFAULT_HEIGHT,
    dpr = DEFAULT_DPR,
    currentMinutes,
    currentSeconds,
  } = request.body || {};

  return serialize(async () => {
    const html = renderCalendarHtml({
      events,
      dayStart,
      dayEnd,
      showDensity,
      width,
      height,
      dpr,
      currentMinutes,
      currentSeconds,
    });

    reply.header("Content-Type", "text/html; charset=utf-8").send(html);
  }).catch((err) => {
    fastify.log.error({ err }, "render failed");
    throw err;
  });
});

fastify.addHook("onClose", closeBrowser);

const port = process.env.PORT || 3000;
const host = "0.0.0.0";
fastify.listen({ port, host }).then(() => {
  console.log(`Render server listening on http://${host}:${port}`);
});

process.on("SIGINT", () => {
  fastify.close().finally(() => process.exit(0));
});
process.on("SIGTERM", () => {
  fastify.close().finally(() => process.exit(0));
});
