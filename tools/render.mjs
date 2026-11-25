// Render the SVG deliverable to PNG + PDF and measure text fit with a real browser.
// No npm dependencies: uses Edge/Chrome + the DevTools Protocol over Node's global WebSocket.
//
// Usage:
//   node tools/render.mjs [--root .] [--browser "C:/path/msedge.exe"]
//
// Outputs:
//   diagram/resource-onboarding-swimlane.png
//   diagram/resource-onboarding-swimlane.pdf
//   artifacts/render-report.json

import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import http from "node:http";
import net from "node:net";

const __dirname = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
function argValue(name, fallback) {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}
const ROOT = resolve(argValue("--root", join(__dirname, "..")));
const SVG = join(ROOT, "diagram", "resource-onboarding-swimlane.svg");
const HTML = join(ROOT, "artifacts", "render.html");
const PNG = join(ROOT, "diagram", "resource-onboarding-swimlane.png");
const PDF = join(ROOT, "diagram", "resource-onboarding-swimlane.pdf");
const REPORT = join(ROOT, "artifacts", "render-report.json");

const CANVAS_W = 3000;
const CANVAS_H = 2050;
const SCALE = 2;

const CANDIDATES = [
  process.env.EDGE_PATH,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
].filter(Boolean);

const browser = argValue("--browser", CANDIDATES.find((p) => existsSync(p)) || "");
if (!browser) {
  console.error("E-BROWSER: Edge/Chrome not found. Set EDGE_PATH or pass --browser.");
  process.exit(2);
}

function freePort() {
  return new Promise((res, rej) => {
    const s = net.createServer();
    s.listen(0, "127.0.0.1", () => {
      const p = s.address().port;
      s.close(() => res(p));
    });
    s.on("error", rej);
  });
}

function getJSON(url) {
  return new Promise((res, rej) => {
    http.get(url, (r) => {
      let d = "";
      r.on("data", (c) => (d += c));
      r.on("end", () => {
        try { res(JSON.parse(d)); } catch (e) { rej(e); }
      });
    }).on("error", rej);
  });
}

async function waitForDevtools(port, timeoutMs = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      return await getJSON(`http://127.0.0.1:${port}/json/version`);
    } catch {
      await new Promise((r) => setTimeout(r, 250));
    }
  }
  throw new Error("E-CDP: devtools endpoint did not appear");
}

class CDP {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    this.listeners = new Map();
    ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      } else if (msg.method) {
        const arr = this.listeners.get(msg.method) || [];
        arr.forEach((fn) => fn(msg.params, msg.sessionId));
      }
    });
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    this.ws.send(JSON.stringify(payload));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  once(method, sessionId, timeoutMs = 20000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`E-CDP timeout ${method}`)), timeoutMs);
      const fn = (params, sid) => {
        if (sessionId && sid !== sessionId) return;
        clearTimeout(timer);
        const arr = this.listeners.get(method) || [];
        const i = arr.indexOf(fn);
        if (i >= 0) arr.splice(i, 1);
        resolve(params);
      };
      const arr = this.listeners.get(method) || [];
      arr.push(fn);
      this.listeners.set(method, arr);
    });
  }
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function main() {
  mkdirSync(join(ROOT, "artifacts"), { recursive: true });
  const profile = mkdtempSync(join(tmpdir(), "c2267-render-"));
  const port = await freePort();
  const proc = spawn(browser, [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--hide-scrollbars",
    "--force-color-profile=srgb",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "about:blank",
  ], { stdio: ["ignore", "pipe", "pipe"] });
  let stderr = "";
  proc.stderr.on("data", (d) => (stderr += d.toString()));
  proc.on("error", (e) => { console.error("E-SPAWN:", e.message); });

  try {
    const version = await waitForDevtools(port);
    const ws = new WebSocket(version.webSocketDebuggerUrl);
    await new Promise((res, rej) => {
      ws.addEventListener("open", res, { once: true });
      ws.addEventListener("error", rej, { once: true });
    });
    const cdp = new CDP(ws);

    const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });

    await cdp.send("Page.enable", {}, sessionId);
    await cdp.send("Runtime.enable", {}, sessionId);
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: CANVAS_W, height: CANVAS_H, deviceScaleFactor: SCALE, mobile: false,
      screenWidth: CANVAS_W, screenHeight: CANVAS_H,
    }, sessionId);

    const loaded = cdp.once("Page.loadEventFired", sessionId, 30000);
    await cdp.send("Page.navigate", { url: "file:///" + HTML.replace(/\\/g, "/") }, sessionId);
    await loaded;

    // fonts + layout settle
    await cdp.send("Runtime.evaluate", {
      expression: "document.fonts && document.fonts.ready ? document.fonts.ready.then(() => true) : true",
      awaitPromise: true, returnByValue: true,
    }, sessionId);
    await sleep(500);

    const measure = await cdp.send("Runtime.evaluate", {
      expression: `(() => {
        const svg = document.querySelector('svg');
        const vb = svg.viewBox.baseVal;
        const texts = Array.from(document.querySelectorAll('text'));
        const canvasBad = [];
        for (const t of texts) {
          const b = t.getBBox();
          if (b.x < -0.5 || b.y < -0.5 || b.x + b.width > vb.width + 0.5 || b.y + b.height > vb.height + 0.5) {
            canvasBad.push({ text: (t.textContent || '').slice(0, 30), x: +b.x.toFixed(1), y: +b.y.toFixed(1), w: +b.width.toFixed(1), h: +b.height.toFixed(1) });
          }
        }
        const fits = [];
        for (const g of document.querySelectorAll('[data-fit]')) {
          const box = document.getElementById(g.dataset.fit);
          if (!box) { fits.push({ fit: g.dataset.fit, error: 'missing-box' }); continue; }
          const b = g.getBBox();
          const r = box.getBBox();
          const pad = 5;
          const d = {
            left: +(r.x + pad - b.x).toFixed(1),
            top: +(r.y + pad - b.y).toFixed(1),
            right: +((b.x + b.width) - (r.x + r.width - pad)).toFixed(1),
            bottom: +((b.y + b.height) - (r.y + r.height - pad)).toFixed(1),
          };
          if (d.left > 0 || d.top > 0 || d.right > 0 || d.bottom > 0) {
            fits.push({ fit: g.dataset.fit, overflow: d, text: (g.textContent || '').slice(0, 40),
                        box: { x: +r.x.toFixed(1), y: +r.y.toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1) } });
          }
        }
        return JSON.stringify({ texts: texts.length, canvasBad, fits });
      })()`,
      returnByValue: true,
    }, sessionId);
    const measured = JSON.parse(measure.result.value);

    const shot = await cdp.send("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
      fromSurface: true,
      clip: { x: 0, y: 0, width: CANVAS_W, height: CANVAS_H, scale: 1 },
    }, sessionId);
    writeFileSync(PNG, Buffer.from(shot.data, "base64"));

    const pdf = await cdp.send("Page.printToPDF", {
      printBackground: true,
      preferCSSPageSize: true,
      paperWidth: 594 / 25.4,
      paperHeight: 405.9 / 25.4,
      marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0,
      scale: 1,
      transferMode: "ReturnAsBase64",
    }, sessionId);
    writeFileSync(PDF, Buffer.from(pdf.data, "base64"));

    const report = {
      generated_at: new Date().toISOString(),
      browser: browser.split(/[\\/]/).pop(),
      browser_version: version.Browser,
      protocol_version: version["Protocol-Version"],
      canvas: { width: CANVAS_W, height: CANVAS_H, scale: SCALE },
      texts_checked: measured.texts,
      canvas_overflow: measured.canvasBad,
      fit_groups_checked: (await cdp.send("Runtime.evaluate", {
        expression: "document.querySelectorAll('[data-fit]').length", returnByValue: true
      }, sessionId)).result.value,
      overflow: measured.fits,
      png: { path: "diagram/resource-onboarding-swimlane.png", bytes: readFileSync(PNG).length },
      pdf: { path: "diagram/resource-onboarding-swimlane.pdf", bytes: readFileSync(PDF).length },
    };
    writeFileSync(REPORT, JSON.stringify(report, null, 2) + "\n", "utf8");

    console.log(`[render] browser: ${version.Browser}`);
    console.log(`[render] texts=${report.texts_checked} fit_groups=${report.fit_groups_checked}`);
    console.log(`[render] canvas_overflow=${report.canvas_overflow.length} fit_overflow=${report.overflow.length}`);
    if (report.overflow.length) {
      console.log(JSON.stringify(report.overflow.slice(0, 10), null, 2));
    }
    console.log(`[render] png ${report.png.bytes} bytes -> ${PNG}`);
    console.log(`[render] pdf ${report.pdf.bytes} bytes -> ${PDF}`);

    await cdp.send("Browser.close", {}).catch(() => {});
    ws.close();
    process.exitCode = report.overflow.length || report.canvas_overflow.length ? 1 : 0;
  } finally {
    try { proc.kill(); } catch {}
    await sleep(300);
    try { rmSync(profile, { recursive: true, force: true }); } catch {}
  }
}

main().catch((e) => {
  console.error("E-RENDER:", e && e.stack ? e.stack : e);
  process.exit(2);
});
