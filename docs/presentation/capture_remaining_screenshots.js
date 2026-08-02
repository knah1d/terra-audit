const puppeteer = require("puppeteer-core");
const fs = require("fs");
const path = require("path");

const OUT = path.join(__dirname, "assets", "demo_steps");
fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function openPage(browser) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000, deviceScaleFactor: 1 });
  await page.goto("http://127.0.0.1:8501", { waitUntil: "networkidle2", timeout: 60000 });
  await sleep(7000);
  await page.addStyleTag({ content: `
    header[data-testid="stHeader"] { display: none !important; }
    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
  ` });
  return page;
}

async function clickText(page, text) {
  const result = await page.evaluate((text) => {
    const candidates = [...document.querySelectorAll("button,[role=tab],label")]
      .filter((el) => (el.innerText || el.textContent || "").trim().includes(text));
    const el = candidates.sort((a, b) => (a.innerText || "").length - (b.innerText || "").length)[0];
    if (!el) return null;
    el.click();
    return (el.innerText || el.textContent || "").trim();
  }, text);
  if (!result) throw new Error(`Could not click: ${text}`);
  await sleep(3800);
}

async function scrollToText(page, text, offset = 105) {
  const result = await page.evaluate(({ text, offset }) => {
    const candidates = [...document.querySelectorAll("h1,h2,h3,h4,h5,p,div,span")]
      .filter((el) => (el.innerText || "").trim().includes(text));
    const el = candidates.sort((a, b) => (a.innerText || "").length - (b.innerText || "").length)[0];
    if (!el) return false;
    el.scrollIntoView({ block: "start", behavior: "instant" });
    const scroller = document.querySelector("section.main") || document.querySelector('[data-testid="stAppViewContainer"]');
    if (scroller) scroller.scrollBy(0, -offset);
    return true;
  }, { text, offset });
  if (!result) throw new Error(`Could not find: ${text}`);
  await sleep(900);
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(OUT, name), fullPage: false });
  console.log(`captured ${name}`);
}

async function captureRice(browser) {
  const page = await openPage(browser);
  await clickText(page, "F-101 — Ovi-01");
  await clickText(page, "Statistical Signal Analytics");
  await clickText(page, "Run Analytics Engine");
  await scrollToText(page, "AWD EVENTS");
  await shot(page, "step05_rice_analytics_results.png");
  await scrollToText(page, "Compliance Audit Trail Ledger");
  await shot(page, "step06_rice_observation_ledger.png");
  await clickText(page, "Carbon Asset Ledger");
  await scrollToText(page, "Carbon Compliance Ledger");
  await shot(page, "step07_vm0051_inputs.png");
  await clickText(page, "Calculate Carbon Credits");
  await scrollToText(page, "Baseline Emissions");
  await shot(page, "step08_vm0051_results.png");
  await scrollToText(page, "Step-by-Step Audit Trail");
  await shot(page, "step09_vm0051_audit_trail.png");
  await scrollToText(page, "Export Evidence Package");
  await shot(page, "step10_vm0051_evidence_exports.png");
  await page.close();
}

async function captureAlm(browser) {
  const page = await openPage(browser);
  await clickText(page, "F-102 — new");
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, "step11_cropland_methodology_routing.png");
  await clickText(page, "Practice & Soil Data");
  await scrollToText(page, "Practice Schedule");
  await shot(page, "step12_alm_practice_schedule.png");
  await scrollToText(page, "Soil Organic Carbon Samples");
  await shot(page, "step13_alm_soc_samples.png");
  await clickText(page, "Carbon Asset Ledger");
  await scrollToText(page, "Carbon Compliance Ledger");
  await shot(page, "step14_vm0042_inputs.png");
  await clickText(page, "Calculate Carbon Credits");
  await scrollToText(page, "NET REDUCTIONS");
  await shot(page, "step15_vm0042_results.png");
  await scrollToText(page, "Step-by-Step Audit Trail");
  await shot(page, "step16_vm0042_audit_trail.png");
  await scrollToText(page, "Export Evidence Package");
  await shot(page, "step17_vm0042_evidence_exports.png");
  await page.close();
}

async function captureAi(browser) {
  const page = await openPage(browser);
  await clickText(page, "F-101 — Ovi-01");
  await clickText(page, "AI Validation");
  await scrollToText(page, "Model Training Pipeline");
  await shot(page, "step18_ai_training_pipeline.png");
  await clickText(page, "Run Validation");
  await scrollToText(page, "Model Comparison");
  await shot(page, "step19_ai_model_comparison.png");
  await page.close();
}

async function capturePortfolio(browser) {
  const page = await openPage(browser);
  await clickText(page, "Portfolio");
  await scrollToText(page, "Portfolio Overview");
  await shot(page, "step20_portfolio_overview.png");
  await scrollToText(page, "All Registered Fields");
  await shot(page, "step21_registered_fields.png");
  await page.close();
}

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: "/usr/bin/google-chrome",
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--hide-scrollbars"],
  });
  try {
    await captureRice(browser);
    await captureAlm(browser);
    await captureAi(browser);
    await capturePortfolio(browser);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
