import Fastify from "fastify";
import puppeteer from "puppeteer";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createRequire } from "node:module";
import TufteDayCalendar from "./dist/TufteDayCalendar.cjs";

const require = createRequire(import.meta.url);
const chromium = require("@sparticuz/chromium");

const fastify = Fastify({ logger: true });

const executablePath =
  process.env.PUPPETEER_EXECUTABLE_PATH || process.env.CHROMIUM_PATH || null;

let browser;
let page;
async function ensureBrowser({ width = 800, height = 480, dpr = 2 } = {}) {
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

let renderChain = Promise.resolve();
function serialize(fn) {
  const next = renderChain.then(fn, fn);
  renderChain = next.catch(() => {});
  return next;
}

fastify.get("/health", async () => ({ ok: true }));

fastify.post("/render", async (request, reply) => {
  const {
    events = [],
    dayStart,
    dayEnd,
    showDensity = false,
    width = 800,
    height = 480,
    dpr = 2,
    format = "png",
    currentMinutes,
    currentSeconds,
  } = request.body || {};

  return serialize(async () => {
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
    const buffer = await page.screenshot({
      fullPage: false,
      type: isPNG ? "png" : "jpeg",
      quality: isPNG ? undefined : 90,
      captureBeyondViewport: false,
      omitBackground: false,
    });

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
