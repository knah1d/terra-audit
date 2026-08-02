const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Kazi Nahid";
pptx.company = "Institute of Information Technology, University of Dhaka";
pptx.subject = "SE801 Project Midterm Presentation";
pptx.title = "Terra-Audit — SE801 Midterm Presentation";
pptx.lang = "en-US";
pptx.theme = {
  headFontFace: "Aptos Display",
  bodyFontFace: "Aptos",
  lang: "en-US",
};
pptx.defineSlideMaster({
  title: "CONTENT",
  background: { color: "F6F7F1" },
  objects: [
    { rect: { x: 0, y: 0, w: 10.9, h: 0.11, fill: { color: "2F6B3B" }, line: { color: "2F6B3B" } } },
    { rect: { x: 10.9, y: 0, w: 2.433, h: 0.11, fill: { color: "B08A4F" }, line: { color: "B08A4F" } } },
    { text: { text: "TERRA-AUDIT  •  SE801 MIDTERM", options: { x: 0.55, y: 7.17, w: 5.2, h: 0.16, fontFace: "Aptos", fontSize: 8.5, color: "6B7A89", margin: 0, charSpacing: 0.7 } } },
    { text: { text: "IIT • UNIVERSITY OF DHAKA", options: { x: 9.2, y: 7.17, w: 3.1, h: 0.16, fontFace: "Aptos", fontSize: 8.5, color: "6B7A89", align: "right", margin: 0, charSpacing: 0.7 } } },
  ],
  slideNumber: { x: 12.48, y: 7.14, w: 0.52, h: 0.2, color: "3E7C42", fontFace: "Aptos", fontSize: 9, align: "right", margin: 0 },
});

const C = {
  navy: "163B27",
  navy2: "214A32",
  green: "2F6B3B",
  greenDark: "1F5630",
  mint: "E2EEDF",
  blue: "527A68",
  blueSoft: "E7EFE9",
  amber: "B08A4F",
  amberSoft: "F2EAD9",
  olive: "6F7D43",
  red: "956156",
  redSoft: "F0E5E1",
  ink: "24332A",
  gray: "5F6D63",
  light: "F6F7F1",
  line: "D6DED4",
  white: "FFFFFF",
};
const S = pptx.ShapeType;
const root = path.resolve(__dirname, "..", "..");
const docsDir = path.join(root, "docs");
const asset = (name) => path.join(__dirname, "assets", name);
const diagram = (name) => path.join(docsDir, "diagrams", name);
const fieldPhoto = asset("rice_fields_cover_v2.png");

function pngSize(file) {
  const b = fs.readFileSync(file);
  if (b.toString("ascii", 1, 4) !== "PNG") throw new Error(`Not PNG: ${file}`);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function imageContain(slide, file, x, y, w, h, opts = {}) {
  const d = pngSize(file); const ar = d.w / d.h; const box = w / h;
  let iw = w, ih = h, ix = x, iy = y;
  if (ar > box) { ih = w / ar; iy += (h - ih) / 2; } else { iw = h * ar; ix += (w - iw) / 2; }
  slide.addImage({ path: file, x: ix, y: iy, w: iw, h: ih, ...opts });
}
function imageCrop(slide, file, x, y, w, h) {
  const d = pngSize(file); const ar = d.w / d.h; const box = w / h;
  let sx = 0, sy = 0, sw = d.w, sh = d.h;
  if (ar > box) { sw = d.h * box; sx = (d.w - sw) / 2; } else { sh = d.w / box; sy = (d.h - sh) / 2; }
  slide.addImage({ path: file, x, y, w, h, sizing: "crop", srcRect: { x: sx / d.w * 100, y: sy / d.h * 100, w: sw / d.w * 100, h: sh / d.h * 100 } });
}
function title(slide, kicker, heading, sub = "") {
  slide.addText(kicker.toUpperCase(), { x: 0.6, y: 0.34, w: 3.8, h: 0.22, fontSize: 10, bold: true, color: C.greenDark, charSpacing: 1.4, margin: 0 });
  slide.addText(heading, { x: 0.6, y: 0.62, w: 12.05, h: 0.53, fontSize: 27, bold: true, color: C.navy, margin: 0, breakLine: false, fit: "shrink" });
  if (sub) slide.addText(sub, { x: 0.62, y: 1.17, w: 11.75, h: 0.3, fontSize: 12.5, color: C.gray, margin: 0, fit: "shrink" });
}
function card(slide, x, y, w, h, heading, body, color = C.green, number = "") {
  slide.addShape(S.roundRect, { x, y, w, h, rectRadius: 0.045, fill: { color: "FAFBF7" }, line: { color: C.line, width: 0.7 } });
  slide.addShape(S.rect, { x, y, w: 0.055, h, fill: { color }, line: { color } });
  if (number) {
    slide.addShape(S.ellipse, { x: x + 0.25, y: y + 0.22, w: 0.47, h: 0.47, fill: { color }, line: { color } });
    slide.addText(number, { x: x + 0.25, y: y + 0.29, w: 0.47, h: 0.2, fontSize: 11, bold: true, color: C.white, align: "center", margin: 0 });
  }
  const tx = x + (number ? 0.88 : 0.28);
  slide.addText(heading, { x: tx, y: y + 0.2, w: w - (tx - x) - 0.2, h: 0.3, fontSize: 15, bold: true, color: C.navy, margin: 0, fit: "shrink" });
  slide.addText(body, { x: x + 0.28, y: y + 0.67, w: w - 0.52, h: h - 0.83, fontSize: 11.5, color: C.gray, margin: 0.02, breakLine: false, valign: "top", fit: "shrink" });
}
function bullets(slide, items, x, y, w, lineH = 0.55, color = C.green) {
  items.forEach((item, i) => {
    const yy = y + i * lineH;
    slide.addShape(S.ellipse, { x, y: yy + 0.09, w: 0.13, h: 0.13, fill: { color }, line: { color } });
    slide.addText(item, { x: x + 0.24, y: yy, w: w - 0.24, h: lineH - 0.03, fontSize: 13, color: C.ink, margin: 0, breakLine: false, fit: "shrink", valign: "mid" });
  });
}
function callout(slide, x, y, w, h, text, color = C.amber, soft = C.amberSoft) {
  slide.addShape(S.roundRect, { x, y, w, h, rectRadius: 0.06, fill: { color: soft }, line: { color, width: 1 } });
  slide.addText(text, { x: x + 0.18, y: y + 0.13, w: w - 0.36, h: h - 0.25, fontSize: 11.5, bold: true, color: C.ink, margin: 0, valign: "mid", fit: "shrink" });
}
function sourceLink(slide, text, filePath, x = 7.3, y = 6.82, w = 5.35) {
  const url = `file://${filePath}`;
  slide.addText(text, { x, y, w, h: 0.18, fontSize: 8.5, color: C.blue, align: "right", margin: 0, italic: true, hyperlink: { url }, fit: "shrink" });
}
function notes(slide, text) { slide.addNotes(text); }
function addImagePanel(slide, file, x, y, w, h, label = "") {
  slide.addShape(S.roundRect, { x, y, w, h, rectRadius: 0.035, fill: { color: C.white }, line: { color: C.line, width: 0.65 } });
  imageContain(slide, file, x + 0.12, y + 0.12, w - 0.24, h - (label ? 0.48 : 0.24));
  if (label) slide.addText(label, { x: x + 0.16, y: y + h - 0.3, w: w - 0.32, h: 0.18, fontSize: 9.5, color: C.gray, margin: 0, align: "center", fit: "shrink" });
}

// 1 — Cover
{
  const slide = pptx.addSlide();
  imageCrop(slide, fieldPhoto, 0, 0, 13.333, 7.5);
  slide.addShape(S.rect, { x: 0, y: 0, w: 13.333, h: 7.5, fill: { color: C.navy, transparency: 38 }, line: { color: C.navy, transparency: 100 } });
  slide.addShape(S.rect, { x: 0, y: 0, w: 13.333, h: 0.12, fill: { color: C.amber }, line: { color: C.amber } });
  slide.addShape(S.roundRect, { x: 0.62, y: 0.4, w: 2.0, h: 0.88, rectRadius: 0.035, fill: { color: C.white, transparency: 3 }, line: { color: C.white, transparency: 70 } });
  imageContain(slide, diagram("logo_du_seal.png"), 0.74, 0.5, 0.67, 0.67);
  imageContain(slide, diagram("logo_iit.png"), 1.58, 0.52, 0.67, 0.67);
  slide.addText("INSTITUTE OF INFORMATION TECHNOLOGY  •  UNIVERSITY OF DHAKA", { x: 2.92, y: 0.69, w: 6.7, h: 0.24, fontSize: 10.2, bold: true, color: "EFF5EC", charSpacing: 0.5, margin: 0, fit: "shrink" });
  slide.addText("SE801 PROJECT MIDTERM REPORT", { x: 0.72, y: 1.6, w: 5.8, h: 0.24, fontSize: 10.5, bold: true, color: "D8C27B", charSpacing: 1.35, margin: 0 });
  slide.addText("TERRA-AUDIT", { x: 0.68, y: 1.96, w: 8.0, h: 0.72, fontSize: 39, bold: true, color: C.white, charSpacing: 0.35, margin: 0 });
  slide.addText("AI-Assisted Digital MRV Platform for AWD Rice Irrigation and Agricultural Land Management Carbon Credits", { x: 0.72, y: 2.76, w: 7.95, h: 1.02, fontSize: 19.2, color: "EEF4EA", margin: 0, fit: "shrink" });
  slide.addShape(S.line, { x: 0.72, y: 4.02, w: 1.4, h: 0, line: { color: C.amber, width: 3 } });
  slide.addShape(S.roundRect, { x: 0.68, y: 4.32, w: 8.25, h: 1.48, rectRadius: 0.045, fill: { color: "102F20", transparency: 16 }, line: { color: "DBE8D6", transparency: 67, width: 0.8 } });
  slide.addText("SUBMITTED AS", { x: 0.94, y: 4.6, w: 1.38, h: 0.18, fontSize: 8.5, bold: true, color: "C7D9C2", charSpacing: 0.8, margin: 0 });
  slide.addText("Technical Report\nSE801 Project Midterm Report", { x: 0.94, y: 4.87, w: 2.2, h: 0.55, fontSize: 11.5, bold: true, color: C.white, margin: 0, fit: "shrink" });
  slide.addText("SUBMITTED BY", { x: 3.37, y: 4.6, w: 1.35, h: 0.18, fontSize: 8.5, bold: true, color: "C7D9C2", charSpacing: 0.8, margin: 0 });
  slide.addText("Kazi Nahid\nBSSE Roll: 1437", { x: 3.37, y: 4.87, w: 1.7, h: 0.55, fontSize: 12, bold: true, color: C.white, margin: 0 });
  slide.addText("SUPERVISED BY", { x: 5.34, y: 4.6, w: 1.45, h: 0.18, fontSize: 8.5, bold: true, color: "C7D9C2", charSpacing: 0.8, margin: 0 });
  slide.addText("Dr. Emon Kumar Dey\nProfessor, Institute of Information Technology\nUniversity of Dhaka", { x: 5.34, y: 4.84, w: 3.3, h: 0.74, fontSize: 10.6, bold: true, color: C.white, margin: 0, fit: "shrink" });
  slide.addText("DATE OF SUBMISSION", { x: 0.72, y: 6.35, w: 1.78, h: 0.18, fontSize: 8.5, bold: true, color: "C7D9C2", charSpacing: 0.8, margin: 0 });
  slide.addText("2 August 2026", { x: 2.58, y: 6.29, w: 2.05, h: 0.28, fontSize: 13.5, bold: true, color: C.white, margin: 0 });
  slide.addText("AGRICULTURAL MRV  •  SATELLITE EVIDENCE  •  TRANSPARENT ACCOUNTING", { x: 0.72, y: 6.88, w: 8.7, h: 0.2, fontSize: 8.8, bold: true, color: "D8C27B", charSpacing: 0.75, margin: 0 });
  notes(slide, "Use the exact cover identity from the V3 report: Kazi Nahid, BSSE Roll 1437, supervised by Dr. Emon Kumar Dey, submitted 2 August 2026. Introduce Terra-Audit as an evidence-first agricultural MRV software project. Sentinel-1 supplies observations; the project contribution is field-specific processing, methodology calculation, persistence, and auditable reporting.");
}

// 2 — Problem
{
  const slide = pptx.addSlide();
  imageCrop(slide, fieldPhoto, 0, 0, 13.333, 7.5);
  slide.addShape(S.rect, { x: 0, y: 0, w: 13.333, h: 7.5, fill: { color: C.navy, transparency: 27 }, line: { color: C.navy, transparency: 100 } });
  slide.addShape(S.rect, { x: 0, y: 0, w: 13.333, h: 0.11, fill: { color: C.amber }, line: { color: C.amber } });
  slide.addText("PROJECT OVERVIEW", { x: 0.66, y: 0.42, w: 3.2, h: 0.22, fontSize: 10, bold: true, color: "D8C27B", charSpacing: 1.4, margin: 0 });
  slide.addText("Why agricultural carbon MRV is difficult", { x: 0.64, y: 0.74, w: 10.8, h: 0.55, fontSize: 28, bold: true, color: C.white, margin: 0, fit: "shrink" });
  slide.addText("The obstacle is not data availability alone — it is trustworthy interpretation and evidence.", { x: 0.66, y: 1.3, w: 10.8, h: 0.3, fontSize: 12.5, color: "E6EEE3", margin: 0, fit: "shrink" });
  const issues = [
    ["01", "Unverifiable practice records", "Farmer logs are difficult for an auditor to verify consistently across many small plots."],
    ["02", "Expensive field hardware", "Water-level sensors and repeated field visits are costly to deploy and maintain at scale."],
    ["03", "Opaque calculations", "Disconnected spreadsheets hide assumptions, intermediate values, and methodology constraints."]
  ];
  issues.forEach((it,i)=>{
    const x=0.66+i*4.18;
    slide.addShape(S.roundRect,{x,y:2.0,w:3.78,h:2.15,rectRadius:0.045,fill:{color:"F8FAF5",transparency:3},line:{color:"D9E5D5",transparency:20,width:0.7}});
    slide.addText(it[0],{x:x+0.27,y:2.28,w:0.46,h:0.22,fontSize:10.5,bold:true,color:C.greenDark,margin:0});
    slide.addText(it[1],{x:x+0.27,y:2.69,w:3.2,h:0.48,fontSize:16,bold:true,color:C.navy,margin:0,fit:"shrink"});
    slide.addText(it[2],{x:x+0.27,y:3.28,w:3.2,h:0.58,fontSize:11.2,color:C.gray,margin:0,fit:"shrink"});
  });
  slide.addShape(S.roundRect,{x:0.66,y:4.62,w:12.0,h:1.22,rectRadius:0.045,fill:{color:"102F20",transparency:13},line:{color:"D9E5D5",transparency:60,width:0.7}});
  slide.addText("TERRA-AUDIT RESPONSE",{x:0.98,y:4.9,w:2.15,h:0.2,fontSize:9.5,bold:true,color:"D8C27B",charSpacing:1.0,margin:0});
  slide.addText("Connect field evidence → methodology logic → auditor-ready outputs in one traceable workflow.",{x:0.98,y:5.2,w:10.9,h:0.34,fontSize:18.5,bold:true,color:C.white,margin:0,fit:"shrink"});
  slide.addText("Output is an auditable estimate — not an issued Verra credit.",{x:0.68,y:6.35,w:11.95,h:0.3,fontSize:12,bold:true,color:"F0F4EC",align:"center",margin:0});
  slide.addText("TERRA-AUDIT  •  SE801 MIDTERM",{x:0.66,y:7.14,w:4.5,h:0.16,fontSize:8.5,color:"D5E0D1",margin:0,charSpacing:0.7});
  slide.addText("2",{x:12.72,y:7.14,w:0.25,h:0.16,fontSize:9,color:"D8C27B",align:"right",margin:0});
  notes(slide, "Explain that raw satellite observations and methodology PDFs already exist, but they do not form a usable MRV workflow by themselves. The engineering contribution is converting evidence into a field-specific, reproducible calculation with limitations disclosed. Do not claim formal verification or issuance.");
}

// 3 — Dual-path overview
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "Project overview", "One platform, two methodology paths", "Shared field management and evidence reporting; different data and quantification workflows.");
  slide.addShape(S.roundRect, { x: 0.7, y: 1.72, w: 5.73, h: 4.72, rectRadius: 0.045, fill: { color: "F4F8F1" }, line: { color: "CBD9C6", width: 0.8 } });
  slide.addText("RICE AWD • VM0051", { x: 1.02, y: 2.02, w: 3.1, h: 0.3, fontSize: 16, bold: true, color: C.greenDark, margin: 0 });
  slide.addText("Satellite-driven path", { x: 1.02, y: 2.38, w: 3.2, h: 0.32, fontSize: 22, bold: true, color: C.navy, margin: 0 });
  bullets(slide, ["Field boundary + monitoring window", "Sentinel-1 VV/VH time series", "Flooded-state and drydown heuristic", "VM0051 QA3 carbon calculation", "PDF / JSON / time-series evidence"], 1.02, 2.95, 4.8, 0.57, C.green);
  slide.addShape(S.roundRect, { x: 6.9, y: 1.72, w: 5.73, h: 4.72, rectRadius: 0.045, fill: { color: "F7F5ED" }, line: { color: "DDD4BC", width: 0.8 } });
  slide.addText("CROPLAND ALM • VM0042", { x: 7.22, y: 2.02, w: 3.7, h: 0.3, fontSize: 16, bold: true, color: C.olive, margin: 0 });
  slide.addText("Practice & soil-data path", { x: 7.22, y: 2.38, w: 4.5, h: 0.32, fontSize: 22, bold: true, color: C.navy, margin: 0 });
  bullets(slide, ["Baseline vs. project practices", "SOC laboratory measurements", "Livestock and crop-yield evidence", "Scoped VM0042 calculation", "PDF / JSON / practice-SOC export"], 7.22, 2.95, 4.8, 0.57, C.olive);
  slide.addShape(S.chevron, { x: 6.37, y: 3.42, w: 0.38, h: 0.78, fill: { color: C.navy, transparency: 8 }, line: { color: C.navy } });
  notes(slide, "The key architecture choice is to share field management, persistence, and reporting while keeping methodology-specific evidence and calculations separate. Rice uses SAR; cropland ALM uses practices and SOC measurements. This avoids pretending that one data source can satisfy every methodology.");
}

// 4 — Functional requirements
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "Requirements", "Functional requirements — organized by capability", "Five capability groups summarize the 18 functional requirements in the V3 report.");
  const groups = [
    ["01", "Field management", "Boundary input • area calculation\nField type • registry management", C.green],
    ["02", "Rice signal analytics", "Cache-first Sentinel-1 workflow\nAWD events and phenology", C.blue],
    ["03", "Carbon accounting", "VM0051 QA3 + scoped VM0042\nDeductions and eligibility checks", C.amber],
    ["04", "AI assistance", "RF / XGBoost experiment\nMetrics + rule-based fallback", C.olive],
    ["05", "Evidence & portfolio", "Evidence exports • history\nCross-field portfolio", C.red],
  ];
  groups.forEach((g, i) => {
    const y = 1.7 + i * 0.98;
    slide.addShape(S.roundRect, { x: 0.72, y, w: 11.9, h: 0.78, rectRadius: 0.04, fill: { color: C.white }, line: { color: C.line } });
    slide.addShape(S.ellipse, { x: 0.96, y: y + 0.15, w: 0.48, h: 0.48, fill: { color: g[3] }, line: { color: g[3] } });
    slide.addText(g[0], { x: 0.96, y: y + 0.24, w: 0.48, h: 0.17, fontSize: 10.5, bold: true, color: C.white, align: "center", margin: 0 });
    slide.addText(g[1], { x: 1.68, y: y + 0.18, w: 2.4, h: 0.28, fontSize: 15, bold: true, color: C.navy, margin: 0 });
    slide.addText(g[2], { x: 4.1, y: y + 0.12, w: 8.05, h: 0.52, fontSize: 11, color: C.gray, margin: 0, breakLine: false, fit: "shrink", valign: "mid" });
  });
  callout(slide, 0.72, 6.65, 11.9, 0.38, "Non-functional priorities: traceability • reliability • cache-first performance • local security posture • maintainability", C.green, C.mint);
  notes(slide, "Do not read all 18 requirements. Explain the five capability groups and give one concrete example from each. If asked about traceability, show that every carbon result exposes factors, intermediate values, deductions, and source evidence.");
}

// 5 — Use case
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "System modeling", "Use case diagram — who uses which capability?", "The Level-1 view keeps the complete system visible without overwhelming the audience.");
  addImagePanel(slide, asset("use_case_level1.png"), 0.55, 1.55, 9.15, 5.28, "Level-1 use case decomposition from the V3 technical report");
  card(slide, 9.93, 1.55, 2.82, 1.42, "Primary actors", "Project developer\nResearcher\nAuditor", C.green);
  card(slide, 9.93, 3.17, 2.82, 1.42, "External support", "Google Earth Engine\nSQLite project store\nModel artifacts", C.blue);
  card(slide, 9.93, 4.79, 2.82, 1.42, "Core split", "Rice → SAR analytics\nALM → practice/SOC entry", C.amber);
  sourceLink(slide, "Complete diagram: docs/presentation/assets/use_case_level1.png", path.join(docsDir, "presentation", "assets", "use_case_level1.png"));
  notes(slide, "Walk from actors on the left, through Terra-Audit capabilities, to supporting systems on the right. Emphasize that auditors consume evidence rather than operate every analytical function. The newer Cropland ALM use case is explicitly present in the V3 report.");
}

// 6 — Activity
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "System modeling", "Activity diagram — end-to-end workflow", "A top-level sequence for the defense; detailed subflows remain in the report.");
  addImagePanel(slide, asset("activity_top_level.png"), 0.75, 1.52, 5.05, 5.35, "Top-level Terra-Audit activity flow");
  const flow = [
    ["1", "Register field", C.green], ["2", "Choose evidence path", C.blue], ["3", "Analyze / validate", C.amber], ["4", "Calculate credits", C.olive], ["5", "Export evidence", C.red]
  ];
  flow.forEach((f, i) => {
    const y = 1.72 + i * 0.92;
    slide.addShape(S.ellipse, { x: 6.25, y, w: 0.48, h: 0.48, fill: { color: f[2] }, line: { color: f[2] } });
    slide.addText(f[0], { x: 6.25, y: y + 0.11, w: 0.48, h: 0.18, fontSize: 11, bold: true, color: C.white, align: "center", margin: 0 });
    slide.addText(f[1], { x: 6.95, y: y + 0.05, w: 4.2, h: 0.28, fontSize: 17, bold: true, color: C.navy, margin: 0 });
    if (i < flow.length - 1) slide.addShape(S.line, { x: 6.49, y: y + 0.49, w: 0, h: 0.42, line: { color: C.line, width: 2, beginArrowType: "none", endArrowType: "triangle" } });
  });
  callout(slide, 6.25, 6.15, 6.15, 0.58, "Failure paths remain visible: invalid geometry, missing evidence, untrained AI model, or ineligible calculation.", C.amber, C.amberSoft);
  sourceLink(slide, "Complete diagram: docs/presentation/assets/activity_top_level.png", path.join(docsDir, "presentation", "assets", "activity_top_level.png"));
  notes(slide, "Explain the happy path in under one minute. Then point out that controlled failure is part of the design: invalid inputs return messages, cache misses trigger retrieval, untrained AI falls back, and methodology constraints can block issuance.");
}

// 7 — ER
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "Data modeling", "ER diagram — evidence stays linked to the field", "Six core tables shown in the V3 report; current database also includes the AI dataset table.");
  addImagePanel(slide, asset("er_six_tables.png"), 0.55, 1.48, 9.35, 5.42, "Current report ERD: field, rice cache, ALM evidence, livestock, SOC, and credit history");
  card(slide, 10.13, 1.55, 2.58, 1.45, "Shared parent", "fields links both methodology paths through a stable field_id.", C.green);
  card(slide, 10.13, 3.22, 2.58, 1.45, "Window safety", "Rice observations use field + date + exact window as a composite key.", C.blue);
  card(slide, 10.13, 4.89, 2.58, 1.45, "Audit history", "credit_history preserves prior calculations instead of showing only the latest result.", C.amber);
  sourceLink(slide, "Complete diagram: docs/presentation/assets/er_six_tables.png", path.join(docsDir, "presentation", "assets", "er_six_tables.png"));
  notes(slide, "The database is more than storage: it preserves traceability and prevents one monitoring window from overwriting another. Mention that rice observations and ALM evidence are intentionally separate because the methodologies require different inputs.");
}

// 8 — Architecture
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "Software design", "Component architecture — extensible by field type", "The registry dispatches the correct evidence processor and methodology engine.");
  addImagePanel(slide, diagram("fig32.png"), 0.55, 1.48, 8.25, 5.42, "Component diagram — application, registry, methodology paths, AI, reporting, and external services");
  card(slide, 9.08, 1.52, 3.58, 1.32, "Presentation", "Streamlit app, map, forms, charts, portfolio, downloads", C.green);
  card(slide, 9.08, 3.02, 3.58, 1.32, "Domain", "AWD gate / ALM validator + VM0051 / VM0042 engines", C.blue);
  card(slide, 9.08, 4.52, 3.58, 1.32, "Infrastructure", "Earth Engine, SQLite cache/evidence, model artifacts, report generation", C.amber);
  callout(slide, 9.08, 6.03, 3.58, 0.64, "Design decision: share infrastructure, not methodology assumptions.", C.green, C.mint);
  sourceLink(slide, "Complete diagram: docs/diagrams/fig32.png", diagram("fig32.png"));
  notes(slide, "This is the strongest software-engineering slide. Explain the registry pattern: field type maps to a detector or validator and a methodology engine. Adding VM0042 did not require replacing the rice workflow. External data sources and domain calculations remain separated.");
}

// 9 — AI
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "AI engineering", "Experimental AWD classifier pipeline", "Implemented infrastructure; independent agronomic validation is not complete.");
  const nodes = [
    ["Cached\nVV / VH", C.blue], ["Threshold\nlabels", C.amber], ["Leakage-safe\nfeatures", C.green], ["RF /\nXGBoost", C.olive], ["Out-of-fold\nmetrics", C.red], ["Prediction +\nconfidence", C.navy]
  ];
  nodes.forEach((n, i) => {
    const x = 0.55 + i * 2.08;
    slide.addShape(S.roundRect, { x, y: 1.75, w: 1.62, h: 1.02, rectRadius: 0.06, fill: { color: n[1] }, line: { color: n[1] } });
    slide.addText(n[0], { x: x + 0.12, y: 1.99, w: 1.38, h: 0.5, fontSize: 14, bold: true, color: C.white, align: "center", margin: 0, fit: "shrink", valign: "mid" });
    if (i < nodes.length - 1) slide.addShape(S.chevron, { x: x + 1.68, y: 2.05, w: 0.32, h: 0.42, fill: { color: C.line }, line: { color: C.line } });
  });
  slide.addShape(S.roundRect, { x: 0.62, y: 3.25, w: 5.95, h: 2.56, rectRadius: 0.07, fill: { color: C.white }, line: { color: C.line } });
  slide.addText("WHAT IS IMPLEMENTED", { x: 0.92, y: 3.58, w: 2.6, h: 0.22, fontSize: 11, bold: true, color: C.greenDark, charSpacing: 1, margin: 0 });
  bullets(slide, ["Dataset and leakage-safe feature pipeline", "RF / XGBoost training and persistence", "Optional inference with threshold fallback"], 0.95, 3.98, 5.1, 0.43, C.green);
  slide.addShape(S.roundRect, { x: 6.83, y: 3.25, w: 5.88, h: 2.56, rectRadius: 0.07, fill: { color: C.redSoft }, line: { color: C.red } });
  slide.addText("WHAT IS NOT YET PROVEN", { x: 7.13, y: 3.58, w: 3.3, h: 0.22, fontSize: 11, bold: true, color: C.red, charSpacing: 1, margin: 0 });
  bullets(slide, ["Labels originate from the threshold gate", "No independent irrigation ground truth", "Metrics show rule agreement — not field accuracy"], 7.15, 3.98, 5.05, 0.43, C.red);
  callout(slide, 2.15, 6.2, 9.05, 0.52, "Defense wording: AI is an experimental extension; the working baseline is the transparent rule-based detector.", C.amber, C.amberSoft);
  notes(slide, "Be fully honest: do not claim a scientifically validated trained model. The code and saved artifacts demonstrate engineering capability, but current labels come from the threshold rule and there is no independent ground truth. The defensible result is the pipeline plus a transparent fallback.");
}

// 10 — Demo field + analytics
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "Working prototype", "Demo 1 — field registration and SAR analytics", "Screenshots captured from the running local prototype using cached project data.");
  addImagePanel(slide, asset("demo_spatial.png"), 0.55, 1.55, 5.95, 4.68, "Spatial Asset Inspection — registered field and map");
  addImagePanel(slide, asset("demo_analytics.png"), 6.83, 1.55, 5.95, 4.68, "Signal Analytics — cache-backed execution and chart");
  callout(slide, 0.73, 6.42, 5.55, 0.43, "1  Draw / upload / paste → validate → compute area → save", C.green, C.mint);
  callout(slide, 7.01, 6.42, 5.55, 0.43, "2  Select window → cache hit → analyze VV/VH → mark events", C.blue, C.blueSoft);
  notes(slide, "Demonstrate the core workflow live if possible. The left screenshot shows a real registered field. The right screenshot uses cached observations, so the demo does not depend on a live Earth Engine call. Explain that Sentinel provides VV/VH, while Terra-Audit performs the field extraction, smoothing, event interpretation, and persistence.");
}

// 11 — Demo carbon + portfolio
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "Working prototype", "Demo 2 — carbon ledger and portfolio evidence", "Calculated values remain inspectable and prior runs remain visible.");
  addImagePanel(slide, asset("demo_carbon.png"), 0.55, 1.55, 5.95, 4.72, "VM0051 ledger — inputs, intermediate values, and history");
  addImagePanel(slide, asset("demo_portfolio.png"), 6.83, 1.55, 5.95, 4.72, "Portfolio — latest issuance and totals across field types");
  callout(slide, 0.74, 6.42, 12.0, 0.43, "Evidence outputs: methodology-specific PDF + audit JSON + CSV; CSV completeness remains a tracked limitation for livestock data.", C.amber, C.amberSoft);
  notes(slide, "Walk through one calculation rather than reading the dashboard. Show how area, season length, AWD events, factors, deductions, and final issuance connect. Then show the portfolio as evidence that calculation history is persisted. The UI currently contains a known Tier 2 label defect; describe the implemented pathway correctly as VM0051 QA3 / Tier 1 regional defaults.");
}

// 12 — Progress
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "Implementation progress", "What is working at the midterm checkpoint", "Conservative status: implemented does not automatically mean independently validated.");
  const rows = [
    ["Field registration, geometry, SQLite registry", "IMPLEMENTED", C.green],
    ["Sentinel-1 retrieval, cache, AWD threshold analytics", "IMPLEMENTED", C.green],
    ["VM0051 and scoped VM0042 calculation engines", "UNIT-TESTED", C.blue],
    ["PDF / JSON evidence; practice-SOC CSV", "PARTIAL", C.amber],
    ["Credit history and portfolio", "IMPLEMENTED • TESTS PENDING", C.amber],
    ["AI pipeline and model artifacts", "EXPERIMENTAL", C.olive],
    ["Independent AWD ground-truth validation", "NOT STARTED", C.red],
  ];
  rows.forEach((r, i) => {
    const y = 1.56 + i * 0.7;
    slide.addShape(S.roundRect, { x: 0.72, y, w: 11.9, h: 0.54, rectRadius: 0.035, fill: { color: i % 2 ? "F9FAFB" : C.white }, line: { color: C.line, transparency: 35 } });
    slide.addText(r[0], { x: 1.0, y: y + 0.14, w: 7.2, h: 0.22, fontSize: 13, color: C.ink, margin: 0, fit: "shrink" });
    slide.addShape(S.roundRect, { x: 9.08, y: y + 0.1, w: 3.1, h: 0.34, rectRadius: 0.04, fill: { color: r[2], transparency: 8 }, line: { color: r[2] } });
    slide.addText(r[1], { x: 9.2, y: y + 0.18, w: 2.86, h: 0.14, fontSize: 9.5, bold: true, color: C.white, align: "center", margin: 0, fit: "shrink" });
  });
  callout(slide, 1.55, 6.72, 10.1, 0.34, "Current strength: accounting-engine tests. Current gap: system-wide UI, database, reporting, caching, and AI validation coverage.", C.green, C.mint);
  notes(slide, "Use conservative language. The two calculation engines have automated tests according to the V3 report. Other modules are implemented but not equivalently tested. This distinction shows engineering maturity and helps answer questions about evidence for completion.");
}

// 13 — Challenges
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "Challenges & future work", "Known risks — and the response to each", "A credible capstone explains uncertainty instead of hiding it.");
  const items = [
    ["No independent AWD ground truth", "Collect field/irrigation observations and validate by field/season.", C.red],
    ["Small, imbalanced drydown class", "Expand seasons and use grouped validation, not observation-level leakage.", C.amber],
    ["Earth Engine dependency", "Cache-first workflow, graceful errors, and documented setup.", C.blue],
    ["Incomplete VM0042 leakage scope", "Implement, bound, or block each applicable category explicitly.", C.olive],
    ["Local-only deployment", "Add authentication, backups, access controls, and hosted persistence later.", C.green],
    ["VM0051 UI/report label defect", "Replace “Tier 2” with the implemented QA3 / Tier 1 regional-default wording.", C.red],
  ];
  items.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2); const x = 0.67 + col * 6.15, y = 1.55 + row * 1.66;
    slide.addShape(S.roundRect, { x, y, w: 5.82, h: 1.38, rectRadius: 0.06, fill: { color: C.white }, line: { color: C.line } });
    slide.addShape(S.rect, { x, y, w: 0.09, h: 1.38, fill: { color: it[2] }, line: { color: it[2] } });
    slide.addText(it[0], { x: x + 0.3, y: y + 0.22, w: 5.18, h: 0.27, fontSize: 14, bold: true, color: C.navy, margin: 0, fit: "shrink" });
    slide.addText(it[1], { x: x + 0.3, y: y + 0.62, w: 5.18, h: 0.5, fontSize: 11.3, color: C.gray, margin: 0, fit: "shrink" });
  });
  notes(slide, "Choose two challenges to explain deeply rather than reading six. The most important are ground truth and methodology completeness. If asked whether AI works, say the pipeline works but independent accuracy is not yet established. If asked whether credits are valid, say the prototype estimates and documents; it does not issue credits.");
}

// 14 — Timeline
{
  const slide = pptx.addSlide("CONTENT"); title(slide, "Timeline", "Progress against plan", "Midterm checkpoint: 2 August 2026 • final submission plan through 4 September 2026.");
  addImagePanel(slide, asset("gantt.png"), 0.7, 1.55, 8.9, 5.24, "Project timeline from the V3 technical report");
  slide.addShape(S.line, { x: 10.15, y: 1.78, w: 0, h: 4.7, line: { color: C.line, width: 2 } });
  const milestones = [
    ["NOW", "Methodology audit & documentation", C.green],
    ["NEXT", "Final integration & system hardening", C.blue],
    ["FINAL", "Report, evidence audit & defense", C.amber],
  ];
  milestones.forEach((m, i) => {
    const y = 1.83 + i * 1.43;
    slide.addShape(S.ellipse, { x: 9.95, y: y + 0.12, w: 0.4, h: 0.4, fill: { color: m[2] }, line: { color: C.white, width: 1.5 } });
    slide.addText(m[0], { x: 10.58, y, w: 1.0, h: 0.22, fontSize: 10, bold: true, color: m[2], charSpacing: 0.7, margin: 0 });
    slide.addText(m[1], { x: 10.58, y: y + 0.32, w: 2.05, h: 0.62, fontSize: 13, bold: true, color: C.navy, margin: 0, fit: "shrink" });
  });
  sourceLink(slide, "Complete timeline: docs/presentation/assets/gantt.png", path.join(docsDir, "presentation", "assets", "gantt.png"));
  notes(slide, "Explain progress against plan, not every date. The next priorities are system-level tests, export completeness, grouped AI validation, final end-to-end evidence audit, and correcting known labels. Keep the timeline realistic and state which activities are planned rather than complete.");
}

// 15 — Closing
{
  const slide = pptx.addSlide();
  imageCrop(slide, fieldPhoto, 0, 0, 13.333, 7.5);
  slide.addShape(S.rect, { x: 0, y: 0, w: 13.333, h: 7.5, fill: { color: C.navy, transparency: 20 }, line: { color: C.navy, transparency: 100 } });
  slide.addShape(S.rect, { x: 0, y: 0, w: 8.6, h: 7.5, fill: { color: "102F20", transparency: 7 }, line: { color: "102F20", transparency: 100 } });
  slide.addShape(S.rect, { x: 0, y: 0, w: 10.8, h: 0.13, fill: { color: C.green }, line: { color: C.green } });
  slide.addShape(S.rect, { x: 10.8, y: 0, w: 2.533, h: 0.13, fill: { color: C.amber }, line: { color: C.amber } });
  slide.addShape(S.roundRect, { x: 0.68, y: 0.5, w: 1.78, h: 0.92, rectRadius: 0.04, fill: { color: C.white, transparency: 4 }, line: { color: C.white, transparency: 70 } });
  imageContain(slide, diagram("logo_du_seal.png"), 0.78, 0.58, 0.68, 0.68);
  imageContain(slide, diagram("logo_iit.png"), 1.58, 0.6, 0.68, 0.68);
  slide.addText("FIELD  →  EVIDENCE  →  ACCOUNTING", { x: 0.72, y: 1.72, w: 4.5, h: 0.24, fontSize: 10.5, bold: true, color: "D8C27B", charSpacing: 1.25, margin: 0 });
  slide.addText("From agricultural evidence to a reproducible carbon estimate.", { x: 0.72, y: 2.12, w: 7.45, h: 1.05, fontSize: 31, bold: true, color: C.white, margin: 0, fit: "shrink" });
  const end = ["Field-specific evidence processing", "Transparent methodology engines", "Persistent audit trail and exports"];
  end.forEach((t, i) => {
    const x = 0.75 + i * 4.12;
    slide.addShape(S.roundRect, { x, y: 3.55, w: 3.58, h: 1.18, rectRadius: 0.06, fill: { color: C.navy2, transparency: 8 }, line: { color: "A8C39D", transparency: 38 } });
    slide.addShape(S.ellipse, { x: x + 0.24, y: 3.94, w: 0.3, h: 0.3, fill: { color: i === 1 ? C.amber : C.green }, line: { color: i === 1 ? C.amber : C.green } });
    slide.addText(t, { x: x + 0.7, y: 3.78, w: 2.55, h: 0.55, fontSize: 14.5, bold: true, color: C.white, margin: 0, fit: "shrink", valign: "mid" });
  });
  slide.addText("AI remains experimental. The core contribution is the auditable, modular MRV workflow.", { x: 0.78, y: 5.28, w: 7.45, h: 0.5, fontSize: 16, color: "E3ECE0", italic: true, margin: 0, fit: "shrink" });
  slide.addText("QUESTIONS?", { x: 0.72, y: 6.08, w: 4.2, h: 0.55, fontSize: 28, bold: true, color: "D8C27B", margin: 0 });
  slide.addText("Source: Terra-Audit_SE801_Midterm_Report_V3.docx", { x: 0.75, y: 7.04, w: 4.9, h: 0.18, fontSize: 8.5, color: "D5E0D1", margin: 0 });
  notes(slide, "Close with the defensible contribution: Terra-Audit does not create Sentinel data and does not issue credits. It transforms field-specific evidence into transparent methodology calculations and audit artifacts through an extensible software architecture. Invite questions and answer limitations directly.");
}

// Slides 3 onward are maintained in a separate module so the expanded defense
// narrative can be regenerated without disturbing the verified cover design.
pptx._slides = pptx._slides.slice(0, 2);
require("./expanded_midterm_slides")({
  pptx, S, C, docsDir, fieldPhoto, title, card, bullets, callout,
  sourceLink, notes, addImagePanel, imageContain, imageCrop,
});

const output = path.join(docsDir, "Terra-Audit_SE801_Midterm_Presentation.pptx");
pptx.writeFile({ fileName: output });
console.log(`Wrote ${output}`);
