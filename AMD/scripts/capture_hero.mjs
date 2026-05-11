/**
 * Headless screenshot for the VesperGrid submission cover image.
 *
 * Pre-requisites (run in two separate terminals before this script):
 *   1) npm run api                                # FastAPI on :8742
 *   2) npm --prefix apps/console run dev          # Vite on :5173 (proxies /api -> 8742)
 *
 * Then:
 *   npx playwright install chromium
 *   node scripts/capture_hero.mjs
 *
 * Output:
 *   submission/hero_screenshot.png            (full page, 1920 wide)
 *   submission/hero_above_fold.png            (1920x1200 viewport-only)
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const URL = process.env.HERO_URL ?? "http://localhost:5173";
const OUT_DIR = resolve("submission");
mkdirSync(OUT_DIR, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1920, height: 1200 },
  deviceScaleFactor: 2, // crisp on hi-dpi judging displays
  colorScheme: "dark",
});
const page = await context.newPage();

console.log(`[hero] navigating to ${URL}`);
await page.goto(URL, { waitUntil: "networkidle", timeout: 30_000 });

// Wait for the scenario to render: the hero band + an evidence row.
await page.waitForSelector(".hero-status", { timeout: 15_000 });
await page.waitForSelector(".evidence-row", { timeout: 15_000 });

// Lock the source-lineage story on SRC-VID-2217 (Gate 4 CCTV contradiction).
// Evidence rows render the source UUID as a small pill -> click the row whose
// text contains "SRC-VID-2217".
const target = page.locator(".evidence-row", { hasText: "SRC-VID-2217" }).first();
await target.scrollIntoViewIfNeeded();
await target.click();

// Wait for the SourcePreview thumbnail image to load.
await page
  .waitForSelector('img.source-thumb[src*="cctv_gate4"]', { timeout: 10_000 })
  .catch(() => console.warn("[hero] thumbnail did not appear within 10s"));

// Tiny settle for transitions.
await page.waitForTimeout(800);

const aboveFoldPath = resolve(OUT_DIR, "hero_above_fold.png");
const lineagePath   = resolve(OUT_DIR, "hero_source_lineage.png");
const fullPath      = resolve(OUT_DIR, "hero_full_page.png");

console.log(`[hero] capturing above-fold 1920x1200 -> ${aboveFoldPath}`);
await page.screenshot({ path: aboveFoldPath, fullPage: false });

// Scroll so SourcePreview thumbnail is the visual centerpiece. The component
// lives in the left column, just under the EvidenceRail. We scroll to it,
// nudge a bit so the hero band is also still partly visible.
const sourcePreview = page.locator(".source-preview").first();
if (await sourcePreview.count()) {
  await sourcePreview.scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollBy(0, -120));
  await page.waitForTimeout(400);
  console.log(`[hero] capturing source-lineage hero -> ${lineagePath}`);
  await page.screenshot({ path: lineagePath, fullPage: false });
}

// Reset scroll for the full-page sweep.
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(300);
console.log(`[hero] capturing full-page -> ${fullPath}`);
await page.screenshot({ path: fullPath, fullPage: true });

await browser.close();
console.log("[hero] done.");
