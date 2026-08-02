const puppeteer = require("puppeteer-core");
const path = require("path");
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const OUT = path.join(__dirname, "assets", "demo_steps");

async function openPage(browser) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000 });
  await page.goto("http://127.0.0.1:8501", { waitUntil: "networkidle2", timeout: 60000 });
  await sleep(6500);
  await page.addStyleTag({ content: `header[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {display:none!important;}` });
  return page;
}

async function click(page, text) {
  const ok = await page.evaluate((text) => {
    const all = [...document.querySelectorAll("button,[role=tab],label")]
      .filter((el) => (el.innerText || "").includes(text));
    const el = all.sort((a, b) => (a.innerText || "").length - (b.innerText || "").length)[0];
    if (!el) return false;
    el.click(); return true;
  }, text);
  if (!ok) throw new Error(`click failed: ${text}`);
  await sleep(3800);
}

async function focus(page, text) {
  const ok = await page.evaluate((text) => {
    const all = [...document.querySelectorAll("h1,h2,h3,h4,h5,p,div,span")]
      .filter((el) => (el.innerText || "").trim().includes(text));
    const el = all.sort((a, b) => (a.innerText || "").length - (b.innerText || "").length)[0];
    if (!el) return false;
    el.scrollIntoView({ block: "start", behavior: "instant" });
    const scroller = document.querySelector("section.main") || document.querySelector('[data-testid="stAppViewContainer"]');
    if (scroller) scroller.scrollBy(0, -90);
    return true;
  }, text);
  if (!ok) throw new Error(`focus failed: ${text}`);
  await sleep(1000);
}

async function save(page, name) {
  await page.screenshot({ path: path.join(OUT, name), fullPage: false });
  console.log(name);
}

async function rice(browser, target, name) {
  const page = await openPage(browser);
  await click(page, "F-101 — Ovi-01");
  await click(page, "Statistical Signal Analytics");
  await click(page, "Run Analytics Engine");
  await click(page, "Carbon Asset Ledger");
  await click(page, "Calculate Carbon Credits");
  await focus(page, target); await save(page, name); await page.close();
}

async function practice(browser, target, name) {
  const page = await openPage(browser);
  await click(page, "F-102 — new"); await click(page, "Practice & Soil Data");
  await focus(page, target); await save(page, name); await page.close();
}

async function alm(browser, target, name) {
  const page = await openPage(browser);
  await click(page, "F-102 — new"); await click(page, "Carbon Asset Ledger");
  await click(page, "Calculate Carbon Credits");
  await focus(page, target); await save(page, name); await page.close();
}

async function ai(browser, target, name, validate = false) {
  const page = await openPage(browser);
  await click(page, "F-101 — Ovi-01"); await click(page, "AI Validation");
  if (validate) await click(page, "Run Validation");
  await focus(page, target); await save(page, name); await page.close();
}

async function portfolio(browser, target, name) {
  const page = await openPage(browser);
  await click(page, "Portfolio"); await focus(page, target); await save(page, name); await page.close();
}

(async () => {
  const browser = await puppeteer.launch({ headless: true, executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox", "--disable-dev-shm-usage", "--hide-scrollbars"] });
  const jobs = {
    "08": () => rice(browser, "BASELINE EMISSIONS", "step08_vm0051_results.png"),
    "09": () => rice(browser, "Step-by-Step Audit Trail", "step09_vm0051_audit_trail.png"),
    "10": () => rice(browser, "Export Evidence Package", "step10_vm0051_evidence_exports.png"),
    "12": () => practice(browser, "Practice Schedule", "step12_alm_practice_schedule.png"),
    "13": () => practice(browser, "Soil Organic Carbon Samples", "step13_alm_soc_samples.png"),
    "15": () => alm(browser, "NET REDUCTIONS", "step15_vm0042_results.png"),
    "16": () => alm(browser, "Step-by-Step Audit Trail", "step16_vm0042_audit_trail.png"),
    "17": () => alm(browser, "Export Evidence Package", "step17_vm0042_evidence_exports.png"),
    "18": () => ai(browser, "Model Training Pipeline", "step18_ai_training_pipeline.png", false),
    "19": () => ai(browser, "Model Comparison", "step19_ai_model_comparison.png", true),
    "20": () => portfolio(browser, "Portfolio Overview", "step20_portfolio_overview.png"),
    "21": () => portfolio(browser, "All Registered Fields", "step21_registered_fields.png"),
  };
  const key = process.argv[2];
  if (!jobs[key]) throw new Error("Unknown capture job: " + key);
  try { await jobs[key](); } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exit(1); });
