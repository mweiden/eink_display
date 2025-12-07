import Fastify from "fastify";
import puppeteer from "puppeteer";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);

//const { default: TufteDayCalendar } = require("./TufteDayCalendar.js")
const TufteDayCalendar = require("./dist/TufteDayCalendar.cjs").default;
const chromium = require("@sparticuz/chromium");

const BASE_CSS = `
:root { color-scheme: light; }
html,body { margin: 0; padding: 0; background: #ffffff; }
.relative { position: relative; }
.absolute { position: absolute; }
.inset-0 { top: 0; right: 0; bottom: 0; left: 0; }
.bg-white { background-color: #ffffff; }
.border { border-width: 1px; border-style: solid; border-color: #d1d5db; }
.border-black { border-color: #000000; }
.text-neutral-900 { color: #111827; }
.text-neutral-700 { color: #374151; }
.text-neutral-600 { color: #4b5563; }
.antialiased { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
.flex { display: flex; }
.grid { display: grid; }
.items-center { align-items: center; }
.select-none { user-select: none; -webkit-user-select:none; -ms-user-select:none; }
.text-right { text-align: right; }
.font-medium { font-weight: 500; }
.leading-tight { line-height: 1.2; }
.leading-none { line-height: 1; }

/* Escaped arbitrary value utilities */
.text-\$begin:math:display$32px\\$end:math:display$ { font-size: 32px; }
.text-\$begin:math:display$24px\\$end:math:display$ { font-size: 24px; }
.text-\$begin:math:display$20px\\$end:math:display$ { font-size: 20px; }
.text-\$begin:math:display$15px\\$end:math:display$ { font-size: 15px; }
.text-\$begin:math:display$14px\\$end:math:display$ { font-size: 14px; }
.text-\$begin:math:display$13px\\$end:math:display$ { font-size: 13px; }
.text-\$begin:math:display$12px\\$end:math:display$ { font-size: 12px; }
.text-\$begin:math:display$10px\\$end:math:display$ { font-size: 10px; }

/* Safe font-size utilities: escaped class selector + exact token match */
.text-\[32px\], [class~="text-[32px]"] { font-size: 32px; }
.text-\[24px\], [class~="text-[24px]"] { font-size: 24px; }
.text-\[20px\], [class~="text-[20px]"] { font-size: 20px; }
.text-\[15px\], [class~="text-[15px]"] { font-size: 15px; }
.text-\[14px\], [class~="text-[14px]"] { font-size: 14px; }
.text-\[13px\], [class~="text-[13px]"] { font-size: 13px; }
.text-\[12px\], [class~="text-[12px]"] { font-size: 12px; }
.text-\[10px\], [class~="text-[10px]"] { font-size: 10px; }
.text-\[9px\],  [class~="text-[9px]"]  { font-size: 9px;  }

.top-3 { top: 0.75rem; }
.right-3 { right: 0.75rem; }
.px-2 { padding-left: 0.5rem; padding-right: 0.5rem; }
.pr-1 { padding-right: 0.25rem; }
.pl-2 { padding-left: 0.5rem; }
.mt-2 { margin-top: 0.5rem; }
.w-full { width: 100%; }
.h-full { height: 100%; }
.h-16 { height: 4rem; }
.overflow-visible { overflow: visible; }

.ml-\$begin:math:display$2px\\$end:math:display$ { margin-left: 2px; }
.mr-\$begin:math:display$3px\\$end:math:display$ { margin-right: 3px; }
.tracking-tight { letter-spacing: -0.01em; }
.translate-y-\$begin:math:display$-5px\\$end:math:display$ { transform: translateY(-5px); }
.translate-y-\$begin:math:display$5px\\$end:math:display$ { transform: translateY(5px); }
`;

const fastify = Fastify({ logger: true });

const executablePath =
  process.env.PUPPETEER_EXECUTABLE_PATH || process.env.CHROMIUM_PATH || null;

let browser;
let page;
async function ensureBrowser({ width = 480, height = 800, dpr = 2 } = {}) {
  if (!browser) {
    const launchOptions = {
      headless: "new",
      args: ["--no-sandbox", "--disable-gpu", "--font-render-hinting=none"],
    };
    if (executablePath) {
      launchOptions.executablePath = executablePath;
    } else {
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
    width = 480,
    height = 800,
    dpr = 2,
    format = "png",
  } = request.body || {};

  return serialize(async () => {
    const { page } = await ensureBrowser({ width, height, dpr });

    const html = renderToStaticMarkup(
      React.createElement(TufteDayCalendar, {
        events,
        ...(dayStart != null ? { dayStart } : {}),
        ...(dayEnd != null ? { dayEnd } : {}),
        showDensity,
      })
    );

    const pageHTML = `
      <!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <style>${BASE_CSS}</style>
        </head>
        <body>${html}</body>
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
