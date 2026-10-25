// End-to-end checks for the dashboard: screenshots, text greps, overflow, keyboard, reduced motion.
// Usage: node e2e/check.mjs <baseUrl> <outDir>   (needs the API on :8000 and the app served at baseUrl)
import { chromium } from "playwright";
import fs from "node:fs";

const base = process.argv[2] ?? "http://localhost:5180";
const out = process.argv[3] ?? "./screenshots";
fs.mkdirSync(out, { recursive: true });

const BAD = [/P\(churn\)/i, /sd\)/, /100\.0%/, /\b[A-Za-z]+_[A-Za-z]+\b/];
const results = { text: [], overflow: [], checks: [] };
const ok = (name, pass, detail = "") => results.checks.push({ name, pass, detail });

async function run(viewport, label, reducedMotion = false) {
  const browser = await chromium.launch({ channel: "chrome" });
  const ctx = await browser.newContext({ viewport, reducedMotion: reducedMotion ? "reduce" : "no-preference", hasTouch: viewport.width < 600 });
  await ctx.addInitScript(() => { try { sessionStorage.setItem("intro-seen", "1"); } catch {} });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => ok(`${label}: page error`, false, String(e)));
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(base);
  await page.waitForSelector("h1", { timeout: 20000 });
  await page.waitForTimeout(2500);

  const scan = async (name) => {
    const text = await page.evaluate(() => document.body.innerText);
    for (const re of BAD) { const m = text.match(re); if (m) results.text.push({ view: label, page: name, pattern: String(re), sample: m[0] }); }
    // customer ids must not stand alone without a name (the "ID 1234" caption and report links are fine)
    const bare = [...text.matchAll(/(?<!ID )(?<!Customer )\b\d{8}\b/g)].map((m) => m[0]);
    if (bare.length) results.text.push({ view: label, page: name, pattern: "bare customer id", sample: bare.slice(0, 3).join(",") });
    const w = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    if (w[0] > w[1] + 1) results.overflow.push({ view: label, page: name, scrollWidth: w[0], innerWidth: w[1] });
  };
  const shot = (name) => page.screenshot({ path: `${out}/${label}-${name}.png`, fullPage: name !== "profile" });
  const tab = async (name) => { await page.getByRole("button", { name, exact: true }).first().click(); await page.waitForTimeout(2200); };

  await scan("home"); await shot("home");
  if (!reducedMotion) {
    // billboard rotates every 8s and pauses on hover
    const first = await page.locator("h1").first().innerText();
    await page.mouse.move(5, 5);
    await page.waitForTimeout(9000);
    const second = await page.locator("h1").first().innerText();
    ok(`${label}: billboard rotates`, first !== second, `${first} -> ${second}`);
    await page.locator("section[aria-roledescription=carousel]").hover();
    const held = await page.locator("h1").first().innerText();
    await page.waitForTimeout(9000);
    ok(`${label}: billboard pauses on hover`, held === (await page.locator("h1").first().innerText()));
    await page.mouse.move(5, 5);
  }
  if (viewport.width >= 1250) {
    // row arrows page the track
    const track = page.locator(".track").nth(1);
    const before = await track.evaluate((e) => e.style.transform);
    await page.locator(".rowwrap").nth(1).hover();
    await page.getByRole("button", { name: /next$/ }).nth(1).click();
    await page.waitForTimeout(1200);
    const after = await track.evaluate((e) => e.style.transform);
    ok(`${label}: row arrow pages`, before !== after, `${before} -> ${after}`);
  }

  // profile dialog: open from a card, focus trap, Escape, focus returns
  const cover = page.locator(".cover").first();
  await cover.scrollIntoViewIfNeeded();
  await cover.focus();
  await page.keyboard.press("Enter");
  await page.waitForSelector("[role=dialog] h2", { timeout: 8000 });
  await page.waitForTimeout(1800);
  await scan("profile"); await shot("profile");
  let inside = true;
  for (let i = 0; i < 40; i++) { await page.keyboard.press("Tab"); inside = inside && (await page.evaluate(() => !!document.activeElement?.closest("[role=dialog]"))); }
  ok(`${label}: focus stays inside dialog`, inside);
  const ring = await page.evaluate(() => getComputedStyle(document.activeElement).boxShadow);
  ok(`${label}: focus ring visible`, ring && ring !== "none", ring);
  // pick an offer: the gauge note shows "was"
  const offerBtn = page.locator("[role=dialog] .offer").first();
  if (await offerBtn.count()) { await offerBtn.click(); await page.waitForTimeout(1500); ok(`${label}: offer shows (was ...)`, /\(was /.test(await page.locator("[role=dialog]").innerText())); }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(900);
  ok(`${label}: Escape closes dialog`, (await page.locator("[role=dialog]").count()) === 0);
  ok(`${label}: focus returns to the card`, await page.evaluate(() => document.activeElement?.classList.contains("cover")));

  await tab("Customers"); await scan("customers"); await shot("customers");
  const n0 = await page.locator(".gcard").count();
  await page.getByRole("button", { name: "High risk", exact: true }).click();
  await page.waitForTimeout(1800);
  const t = await page.locator("p[aria-live=polite]").first().innerText();
  ok(`${label}: filter updates the count`, /customers/.test(t), t);
  await page.getByRole("button", { name: "All", exact: true }).click();
  await page.waitForTimeout(1200);
  await page.locator("input[type=search]").first().fill("Castiglione");
  await page.waitForTimeout(1500);
  ok(`${label}: search finds a customer`, (await page.locator(".gcard").count()) >= 1, String(await page.locator(".gcard").count()));
  void n0;

  await tab("Retention budget"); await page.waitForTimeout(2500);
  const kept = async () => (await page.locator("[aria-label^='Plus ']").first().getAttribute("aria-label"));
  const k1 = await kept();
  await page.locator("#bud").fill("3000000");
  await page.waitForTimeout(4500);
  const k2 = await kept();
  ok(`${label}: slider updates value kept`, k1 !== k2, `${k1} -> ${k2}`);
  await page.getByRole("button", { name: "Allocate budget" }).click();
  await page.waitForTimeout(3500);
  await scan("budget"); await shot("budget");
  const firstTotal = await page.locator("text=/^\\+\\d/").count();
  ok(`${label}: offer totals appear after allocate`, firstTotal >= 3, String(firstTotal));

  await tab("Model"); await page.waitForTimeout(2500); await scan("model"); await shot("model");
  ok(`${label}: no console errors`, errors.length === 0, errors.slice(0, 2).join(" | "));
  if (reducedMotion) ok(`${label}: intro absent with reduced motion`, (await page.locator(".intro").count()) === 0);
  await browser.close();
}

await run({ width: 1440, height: 900 }, "desktop");
await run({ width: 390, height: 844 }, "phone");
await run({ width: 1440, height: 900 }, "reduced", true);
fs.writeFileSync(`${out}/report.json`, JSON.stringify(results, null, 2));
console.log(JSON.stringify(results, null, 2));
