const puppeteer = require("puppeteer-core");
const fs = require("fs");
const path = require("path");

const OUT = path.join(__dirname, "assets", "demo_steps");
fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function clickText(page, text, tags = "button,[role=tab],label") {
  const clicked = await page.evaluate(({ text, tags }) => {
    const candidates = [...document.querySelectorAll(tags)].filter((el) => {
      const value = (el.innerText || el.textContent || "").trim();
      const style = getComputedStyle(el);
      return value.includes(text) && style.display !== "none" && style.visibility !== "hidden";
    });
    const el = candidates.sort((a, b) => (a.innerText || "").length - (b.innerText || "").length)[0];
    if (!el) return null;
    el.click();
    return (el.innerText || el.textContent || "").trim();
  }, { text, tags });
  if (!clicked) throw new Error(`Could not click: ${text}`);
  await sleep(3200);
}

async function scrollToText(page, text, offset = 105) {
  const found = await page.evaluate(({ text, offset }) => {
    const nodes = [...document.querySelectorAll("h1,h2,h3,h4,h5,p,div,span")]
      .filter((el) => (el.innerText || "").trim().includes(text));
    const el = nodes.sort((a, b) => (a.innerText || "").length - (b.innerText || "").length)[0];
    if (!el) return false;
    const y = el.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({ top: Math.max(0, y), behavior: "instant" });
    return true;
  }, { text, offset });
  if (!found) throw new Error(`Could not find scroll target: ${text}`);
  await sleep(900);
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(OUT, name), fullPage: false });
  console.log(`captured ${name}`);
}

async function main() {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: "/usr/bin/google-chrome",
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--hide-scrollbars"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000, deviceScaleFactor: 1 });
  await page.goto("http://127.0.0.1:8501", { waitUntil: "networkidle2", timeout: 60000 });
  await sleep(7000);
  await page.addStyleTag({ content: `
    header[data-testid="stHeader"] { display: none !important; }
    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
    .stApp { padding-top: 0 !important; }
  ` });

  // Field registry and three geometry-input paths.
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, "step01_field_registry.png");
  await clickText(page, "Upload GeoJSON / KML");
  await shot(page, "step02_upload_boundary.png");
  await clickText(page, "Paste GPS Coordinates");
  const textarea = await page.$("textarea");
  if (!textarea) throw new Error("Coordinate textarea not found");
  await textarea.click({ clickCount: 3 });
  await textarea.type("25.7500, 89.2500\n25.7500, 89.2600\n25.7600, 89.2600\n25.7600, 89.2500\n25.7500, 89.2500");
  await clickText(page, "Parse Coordinates");
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, "step03_geometry_preview_registration.png");
  await page.reload({ waitUntil: "networkidle2", timeout: 60000 });
  await sleep(7000);
  await page.addStyleTag({ content: `\n    header[data-testid="stHeader"] { display: none !important; }\n    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }\n    .stApp { padding-top: 0 !important; }\n  ` });

  // Rice path: controls, cache-backed analytics, chart and ledger.
  await clickText(page, "F-101 — Ovi-01");
  await clickText(page, "Statistical Signal Analytics");
  await scrollToText(page, "Execution Scope");
  await shot(page, "step04_rice_execution_scope.png");
  await clickText(page, "Run Analytics Engine");
  await scrollToText(page, "AWD EVENTS");
  await shot(page, "step05_rice_analytics_results.png");
  await scrollToText(page, "Compliance Audit Trail Ledger");
  await shot(page, "step06_rice_observation_ledger.png");

  // Rice accounting and evidence outputs.
  await clickText(page, "Carbon Asset Ledger");
  await scrollToText(page, "Carbon Compliance Ledger");
  await shot(page, "step07_vm0051_inputs.png");
  await clickText(page, "Calculate Carbon Credits");
  await scrollToText(page, "BASELINE EMISSIONS");
  await shot(page, "step08_vm0051_results.png");
  await scrollToText(page, "Step-by-Step Audit Trail");
  await shot(page, "step09_vm0051_audit_trail.png");
  await scrollToText(page, "Export Evidence Package");
  await shot(page, "step10_vm0051_evidence_exports.png");

  // Cropland routing, practice schedule and SOC evidence.
  await clickText(page, "F-102 — new");
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, "step11_cropland_methodology_routing.png");
  await clickText(page, "Practice & Soil Data");
  await scrollToText(page, "Practice Schedule");
  await shot(page, "step12_alm_practice_schedule.png");
  await scrollToText(page, "Soil Organic Carbon Samples");
  await shot(page, "step13_alm_soc_samples.png");

  // Cropland accounting and evidence outputs.
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

  // AI pipeline and model-comparison output. Existing model artifacts are used.
  await clickText(page, "F-101 — Ovi-01");
  await clickText(page, "AI Validation");
  await scrollToText(page, "Model Training Pipeline");
  await shot(page, "step18_ai_training_pipeline.png");
  await clickText(page, "Run Validation");
  await scrollToText(page, "Model Comparison");
  await shot(page, "step19_ai_model_comparison.png");

  // System-wide portfolio.
  await clickText(page, "Portfolio");
  await scrollToText(page, "Portfolio Overview");
  await shot(page, "step20_portfolio_overview.png");
  await scrollToText(page, "All Registered Fields");
  await shot(page, "step21_registered_fields.png");

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
