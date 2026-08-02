const path = require("path");

module.exports = function buildExpandedMidtermSlides(ctx) {
  const {
    pptx, S, C, docsDir, fieldPhoto, title, card, bullets, callout,
    sourceLink, notes, addImagePanel, imageContain, imageCrop,
  } = ctx;

  const asset = (name) => path.join(__dirname, "assets", name);
  const reportFig = (n) => asset(path.join("report_v3", `fig${String(n).padStart(2, "0")}.png`));
  const demo = (n, name) => asset(path.join("demo_steps", `step${String(n).padStart(2, "0")}_${name}.png`));
  const componentSvg = asset("component_architecture.svg");
  const correctedGantt = path.join(docsDir, "diagrams", "fig22_gantt_serial_fixed.png");

  function stepBadge(slide, step, pathLabel) {
    slide.addShape(S.roundRect, {
      x: 10.72, y: 0.38, w: 1.95, h: 0.43, rectRadius: 0.05,
      fill: { color: pathLabel === "CROPLAND" ? C.olive : pathLabel === "AI" ? C.blue : C.green },
      line: { color: pathLabel === "CROPLAND" ? C.olive : pathLabel === "AI" ? C.blue : C.green },
    });
    slide.addText(`STEP ${step}  •  ${pathLabel}`, {
      x: 10.84, y: 0.5, w: 1.72, h: 0.14, fontSize: 8.5, bold: true,
      color: C.white, align: "center", margin: 0, fit: "shrink",
    });
  }

  function actionStrip(slide, userAction, systemWork, caution = "") {
    slide.addShape(S.roundRect, {
      x: 0.65, y: 6.22, w: 5.9, h: 0.65, rectRadius: 0.04,
      fill: { color: C.mint }, line: { color: "B9CEB4", width: 0.7 },
    });
    slide.addText("USER ACTION", {
      x: 0.86, y: 6.37, w: 1.18, h: 0.15, fontSize: 8.5, bold: true,
      color: C.greenDark, charSpacing: 0.8, margin: 0,
    });
    slide.addText(userAction, {
      x: 2.04, y: 6.3, w: 4.25, h: 0.31, fontSize: 10.8, bold: true,
      color: C.ink, margin: 0, fit: "shrink", valign: "mid",
    });
    slide.addShape(S.roundRect, {
      x: 6.78, y: 6.22, w: 5.9, h: 0.65, rectRadius: 0.04,
      fill: { color: caution ? C.amberSoft : C.blueSoft },
      line: { color: caution ? C.amber : "BFD0C6", width: 0.7 },
    });
    slide.addText(caution ? "DISCLOSURE" : "SYSTEM WORK", {
      x: 6.99, y: 6.37, w: 1.3, h: 0.15, fontSize: 8.5, bold: true,
      color: caution ? C.amber : C.blue, charSpacing: 0.8, margin: 0,
    });
    slide.addText(caution || systemWork, {
      x: 8.31, y: 6.3, w: 4.1, h: 0.31, fontSize: 10.8, bold: true,
      color: C.ink, margin: 0, fit: "shrink", valign: "mid",
    });
  }

  function singleDemo({ step, pathLabel, heading, sub, image, label, action, work, caution, note }) {
    const slide = pptx.addSlide("CONTENT");
    title(slide, "Prototype walkthrough", heading, sub);
    stepBadge(slide, step, pathLabel);
    addImagePanel(slide, image, 0.72, 1.52, 11.9, 4.47, label);
    actionStrip(slide, action, work, caution);
    notes(slide, note);
  }

  function doubleDemo({ step, pathLabel, heading, sub, left, right, leftLabel, rightLabel, action, work, caution, note }) {
    const slide = pptx.addSlide("CONTENT");
    title(slide, "Prototype walkthrough", heading, sub);
    stepBadge(slide, step, pathLabel);
    addImagePanel(slide, left, 0.58, 1.52, 6.03, 4.47, leftLabel);
    addImagePanel(slide, right, 6.73, 1.52, 6.03, 4.47, rightLabel);
    actionStrip(slide, action, work, caution);
    notes(slide, note);
  }

  function reportDiagramSlide(kicker, heading, sub, fig, caption, sideCards, note) {
    const slide = pptx.addSlide("CONTENT");
    if (fig === 21) {
      title(slide, kicker, heading);
      slide.addShape(S.roundRect, { x: 0.55, y: 1.28, w: 12.2, h: 5.7, rectRadius: 0.035, fill: { color: C.white }, line: { color: C.line, width: 0.65 } });
      slide.addImage({ path: componentSvg, x: 1.58, y: 1.35, w: 10.14, h: 5.7 });
      notes(slide, note);
      return;
    }
    title(slide, kicker, heading, sub);
    addImagePanel(slide, reportFig(fig), 0.55, 1.48, 9.28, 5.42, caption);
    sideCards.forEach((c, i) => card(slide, 10.05, 1.53 + i * 1.66, 2.62, 1.42, c[0], c[1], c[2]));
    sourceLink(slide, "Open complete diagram", reportFig(fig));
    notes(slide, note);
  }

  // 3 — Dual methodology overview
  {
    const slide = pptx.addSlide("CONTENT");
    title(slide, "Project overview", "One platform, two agricultural methodology paths", "Shared field registry, persistence, evidence exports and portfolio; methodology-specific inputs remain separate.");
    const paths = [
      {
        x: 0.68, color: C.green, soft: "F1F7EE", tag: "RICE AWD • VM0051",
        heading: "Satellite evidence path",
        items: ["Boundary and monitoring window", "Sentinel-1 VV/VH observations", "Flooded-state and drydown gate", "VM0051 QA3 / Tier 1 defaults", "PDF • JSON • time-series CSV"],
      },
      {
        x: 6.88, color: C.olive, soft: "F7F5EA", tag: "CROPLAND ALM • VM0042",
        heading: "Practice and soil path",
        items: ["Baseline and project schedules", "Lab-measured SOC samples", "Yield, fuel and livestock inputs", "Scoped VM0042 quantification", "PDF • JSON • practice/SOC CSV"],
      },
    ];
    paths.forEach((p) => {
      slide.addShape(S.roundRect, { x: p.x, y: 1.66, w: 5.77, h: 4.9, rectRadius: 0.06, fill: { color: p.soft }, line: { color: p.color, transparency: 45 } });
      slide.addText(p.tag, { x: p.x + 0.32, y: 2.0, w: 4.7, h: 0.22, fontSize: 11, bold: true, color: p.color, charSpacing: 0.7, margin: 0 });
      slide.addText(p.heading, { x: p.x + 0.32, y: 2.37, w: 4.9, h: 0.4, fontSize: 22, bold: true, color: C.navy, margin: 0, fit: "shrink" });
      bullets(slide, p.items, p.x + 0.36, 3.0, 4.95, 0.57, p.color);
    });
    callout(slide, 3.37, 6.72, 6.6, 0.35, "Architecture rule: share infrastructure — never silently share methodology assumptions.", C.green, C.mint);
    notes(slide, "Start with the routing decision. Rice uses SAR-derived evidence; cropland ALM uses practice schedules and SOC measurements. Both paths share field identity, persistence, reporting, calculation history and portfolio aggregation.");
  }

  // 4 — Requirements
  {
    const slide = pptx.addSlide("CONTENT");
    title(slide, "Requirements", "Eighteen functional requirements — grouped for the defense", "FR1–FR18 are organized into six capability groups for readability.");
    const groups = [
      ["FR1–2, 12, 17", "FIELD & ROUTING", "Register geometry • choose methodology • select/delete • edit field metadata", C.green],
      ["FR3–5", "RICE EVIDENCE", "Retrieve/cache Sentinel-1 • smooth and detect AWD • infer season dates", C.blue],
      ["FR6, 13–14", "ALM EVIDENCE", "Practice/SOC schedules • livestock inputs • production-decline leakage screen", C.olive],
      ["FR7–8", "ACCOUNTING", "VM0051 QA3 calculation • scoped VM0042 calculation and deductions", C.amber],
      ["FR9–10", "AI ASSISTANCE", "Optional RF/XGBoost detector • validation dashboard and fallback", C.blue],
      ["FR11, 15–16, 18", "AUDITABILITY", "PDF/JSON/CSV evidence • history • portfolio • export completeness disclosure", C.red],
    ];
    groups.forEach((g, i) => {
      const col = i % 2, row = Math.floor(i / 2);
      const x = 0.68 + col * 6.15, y = 1.55 + row * 1.64;
      slide.addShape(S.roundRect, { x, y, w: 5.82, h: 1.35, rectRadius: 0.05, fill: { color: C.white }, line: { color: C.line } });
      slide.addShape(S.rect, { x, y, w: 0.09, h: 1.35, fill: { color: g[3] }, line: { color: g[3] } });
      slide.addText(g[0], { x: x + 0.28, y: y + 0.2, w: 1.25, h: 0.2, fontSize: 10, bold: true, color: g[3], margin: 0 });
      slide.addText(g[1], { x: x + 1.52, y: y + 0.2, w: 3.7, h: 0.2, fontSize: 11, bold: true, color: C.navy, charSpacing: 0.6, margin: 0 });
      slide.addText(g[2], { x: x + 0.28, y: y + 0.61, w: 5.18, h: 0.47, fontSize: 11.2, color: C.gray, margin: 0, fit: "shrink" });
    });
    callout(slide, 0.68, 6.6, 11.97, 0.43, "NFR focus: traceability • cache-first reliability • local prototype security disclosure • maintainable field-type registry.", C.green, C.mint);
    notes(slide, "Do not read all eighteen requirements. Explain the six capability groups and give one example from each. State that FR18 is not fully complete because the current CSV does not include livestock data; PDF and JSON remain the complete audit formats.");
  }

  reportDiagramSlide("System modeling", "Use case diagram — complete system scope", "Level-1 view of actors, system capabilities and supporting services.", 2, "Level-1 use case diagram", [
    ["Actors", "Project developer, researcher and auditor use different parts of the workflow.", C.green],
    ["External service", "Earth Engine supplies observations; it does not perform Terra-Audit accounting.", C.blue],
    ["Method split", "Rice and cropland evidence paths converge at calculation and reporting.", C.amber],
  ], "Walk from the actors to field management, evidence collection, analysis, methodology calculation and reporting. Point out that the system supports two field types without merging their evidence assumptions.");

  reportDiagramSlide("System modeling", "Activity diagram — end-to-end control flow", "Top-level flow from field selection to evidence export.", 12, "Top-level activity flow", [
    ["Start", "Register or select a field and validate its geometry.", C.green],
    ["Branch", "Route by field type to SAR analytics or practice/SOC validation.", C.blue],
    ["Finish", "Calculate, disclose limitations and export evidence.", C.amber],
  ], "Explain the happy path first. Then point out that validation failures, missing evidence and methodology constraints are visible outcomes rather than hidden exceptions.");

  reportDiagramSlide("Software design", "Component architecture — extensible by field type", "A clean view of routing, methodology paths and shared services.", 21, "Terra-Audit component architecture", [
    ["Presentation", "Streamlit tabs, forms, maps, charts and download controls.", C.green],
    ["Domain", "Evidence processors, methodology engines and AI assistance.", C.blue],
    ["Infrastructure", "Earth Engine, SQLite, model artifacts and report generation.", C.amber],
  ], "This is the strongest software-engineering slide. Explain the registry dispatch: field type selects the correct evidence processor and methodology engine while reporting and persistence stay shared.");

  reportDiagramSlide("Data modeling", "ER diagram — evidence remains linked to each field", "Core entities preserve field identity, evidence provenance and calculation history.", 20, "Entity relationship diagram", [
    ["Stable identity", "field_id connects methodology evidence and calculation history.", C.green],
    ["Window-safe cache", "Rice observations are keyed by field and monitoring window.", C.blue],
    ["Audit history", "Prior calculation runs remain available for inspection.", C.amber],
  ], "Explain why this is not just storage. The schema keeps evidence tied to a field and preserves previous calculations. Rice time series, ALM schedules, SOC samples and livestock records remain separate because their provenance differs.");

  // 9 — Demo roadmap
  {
    const slide = pptx.addSlide("CONTENT");
    title(slide, "Prototype walkthrough", "Defense roadmap — show the project as one evidence chain", "The next slides use real screenshots from the running local application.");
    const stages = [
      ["01", "REGISTER", "Boundary + field type", C.green],
      ["02", "COLLECT", "SAR or ALM evidence", C.blue],
      ["03", "VALIDATE", "Rules + optional AI", C.olive],
      ["04", "CALCULATE", "VM0051 / VM0042", C.amber],
      ["05", "EXPLAIN", "Audit trail + warnings", C.red],
      ["06", "EXPORT", "PDF • JSON • CSV", C.green],
      ["07", "REVIEW", "History + portfolio", C.blue],
    ];
    stages.forEach((st, i) => {
      const x = 0.48 + i * 1.82;
      slide.addShape(S.roundRect, { x, y: 2.14, w: 1.47, h: 2.3, rectRadius: 0.06, fill: { color: C.white }, line: { color: st[3], width: 1.1 } });
      slide.addShape(S.ellipse, { x: x + 0.46, y: 2.47, w: 0.55, h: 0.55, fill: { color: st[3] }, line: { color: st[3] } });
      slide.addText(st[0], { x: x + 0.46, y: 2.62, w: 0.55, h: 0.16, fontSize: 10, bold: true, color: C.white, align: "center", margin: 0 });
      slide.addText(st[1], { x: x + 0.15, y: 3.28, w: 1.17, h: 0.2, fontSize: 10.5, bold: true, color: C.navy, align: "center", margin: 0, fit: "shrink" });
      slide.addText(st[2], { x: x + 0.16, y: 3.72, w: 1.15, h: 0.42, fontSize: 9.5, color: C.gray, align: "center", margin: 0, fit: "shrink" });
      if (i < stages.length - 1) slide.addShape(S.chevron, { x: x + 1.53, y: 3.01, w: 0.22, h: 0.42, fill: { color: C.line }, line: { color: C.line } });
    });
    callout(slide, 1.42, 5.18, 10.5, 0.68, "Presentation rule: for every screen, explain the user action, the software work, and the evidence or limitation produced.", C.green, C.mint);
    notes(slide, "Use this slide to orient the teacher. The demo is not a tour of buttons. It is an evidence chain: create a spatial asset, collect methodology-specific evidence, validate it, calculate, expose the audit trail, export and review at portfolio level.");
  }

  singleDemo({
    step: 1, pathLabel: "SHARED", heading: "Register and select a field",
    sub: "The sidebar is the persistent project registry and the starting point for either methodology.",
    image: demo(1, "field_registry"), label: "Real application screen — field registry and selected field",
    action: "Choose an existing field or start registration.",
    work: "Load geometry, metadata, field type and stored evidence by field_id.",
    note: "Show the registered fields and select one. Explain that field_type is more than a label: the registry uses it to route the user to rice AWD or cropland ALM components.",
  });

  doubleDemo({
    step: 2, pathLabel: "SHARED", heading: "Create a valid spatial boundary",
    sub: "Terra-Audit supports file upload and direct coordinate input; geometry is validated before persistence.",
    left: demo(2, "upload_boundary"), right: demo(3, "geometry_preview_registration"),
    leftLabel: "Upload GeoJSON / KML", rightLabel: "Paste coordinates and preview the polygon",
    action: "Upload a boundary or paste latitude/longitude pairs.",
    work: "Parse safely, validate the polygon and compute area before save.",
    note: "Explain that this is your work, not Sentinel output. Terra-Audit accepts several boundary formats, handles malformed input without crashing, calculates area and persists the spatial asset used by later evidence retrieval.",
  });

  doubleDemo({
    step: 3, pathLabel: "CROPLAND", heading: "Route the workflow by agricultural project type",
    sub: "Selecting Cropland ALM changes the available evidence and calculation components.",
    left: demo(11, "cropland_methodology_routing"), right: reportFig(11),
    leftLabel: "Real UI — Cropland ALM field selected", rightLabel: "Cropland ALM use case",
    action: "Select rice_awd or cropland_alm_vm0042 during registration.",
    work: "Dispatch the correct tabs, validators, engine and report content.",
    note: "Use this slide to explain the extensibility contribution. The same application hosts two methodology paths, but it does not pretend that Sentinel-1 is evidence for cropland SOC accounting.",
  });

  singleDemo({
    step: 4, pathLabel: "RICE", heading: "Define the rice monitoring window",
    sub: "The execution scope is explicit so cached observations remain reproducible.",
    image: demo(4, "rice_execution_scope"), label: "Real application screen — selected field and monitoring window",
    action: "Select dates and run the signal analytics workflow.",
    work: "Check SQLite first; call Earth Engine only on a cache miss.",
    note: "Explain the cache-first design. It makes repeated demonstrations reliable, reduces external calls and keeps each field/window data set separate. Sentinel supplies VV/VH observations; Terra-Audit controls spatial extraction, windowing and persistence.",
  });

  doubleDemo({
    step: 5, pathLabel: "RICE", heading: "Interpret Sentinel-1 as auditable AWD evidence",
    sub: "The application turns a time series into flooded states, drydown events and an observation ledger.",
    left: demo(5, "rice_analytics_results"), right: demo(6, "rice_observation_ledger"),
    leftLabel: "Signal analytics and detected events", rightLabel: "Observation-level evidence ledger",
    action: "Review the chart, derived season and detected AWD events.",
    work: "Smooth VV/VH, apply the transparent gate and retain each observation.",
    note: "This is a central contribution. Raw VV and VH are not carbon credits. Terra-Audit smooths signals, calculates z-scores, identifies flooded and drydown states, derives season dates with fallback and exposes the underlying ledger for audit.",
  });

  doubleDemo({
    step: 6, pathLabel: "RICE", heading: "Calculate the VM0051 rice estimate",
    sub: "Inputs and intermediate values remain visible before the final estimate.",
    left: demo(7, "vm0051_inputs"), right: demo(8, "vm0051_results"),
    leftLabel: "VM0051 inputs populated from field and analytics", rightLabel: "Calculated baseline, project and deduction values",
    action: "Review assumptions, then run the rice accounting engine.",
    work: "Apply QA3 / Tier 1 regional defaults, uncertainty and N₂O deductions.",
    caution: "Known UI defect: the visible “Tier 2” label should read QA3 / Tier 1 regional defaults.",
    note: "Describe the implemented calculation correctly as VM0051 QA3 using Tier 1 regional defaults. Do not repeat the incorrect Tier 2 label visible in the current UI. Show how area, season, events, factors and deductions lead to the final estimate.",
  });

  singleDemo({
    step: 7, pathLabel: "RICE", heading: "Expose the VM0051 audit trail",
    sub: "A reviewer can reconstruct the estimate from disclosed equations and intermediate values.",
    image: demo(9, "vm0051_audit_trail"), label: "Real application screen — VM0051 equations, factors and audit steps",
    action: "Open the methodology audit section and inspect each step.",
    work: "Present equations, factor choices, deductions and final floor-at-zero logic.",
    note: "This is where you answer what your work is. The platform does not merely display a number. It makes the accounting path reconstructable, including factors, intermediate emissions, uncertainty and penalties.",
  });

  singleDemo({
    step: 8, pathLabel: "RICE", heading: "Export the rice evidence package",
    sub: "The calculation can leave the dashboard as auditor-readable and machine-readable evidence.",
    image: demo(10, "vm0051_evidence_exports"), label: "Real application screen — VM0051 PDF, JSON and time-series downloads",
    action: "Download the report, audit JSON and observation CSV.",
    work: "Bind current inputs, outputs and observation provenance into export files.",
    note: "Explain why there are multiple formats. PDF supports human review, JSON supports exact reconstruction and integration, and CSV exposes the rice time series used by the detector. Terra-Audit estimates and documents; it does not issue Verra credits.",
  });

  singleDemo({
    step: 9, pathLabel: "CROPLAND", heading: "Record baseline and project management practices",
    sub: "Cropland ALM uses explicit practice evidence rather than the rice SAR detector.",
    image: demo(12, "alm_practice_schedule"), label: "Real application screen — baseline/project practice schedule",
    action: "Enter crop, tillage, residue, fertilizer, fuel and yield data.",
    work: "Validate completeness and persist evidence separately by scenario and year.",
    note: "Explain the baseline-versus-project structure. The platform stores the management evidence needed by VM0042 and keeps it distinct from the rice time series. Livestock inputs are supported, but the current sample project contains no livestock records.",
  });

  singleDemo({
    step: 10, pathLabel: "CROPLAND", heading: "Attach laboratory SOC measurements",
    sub: "SOC samples are recorded by scenario, sampling year and soil layer.",
    image: demo(13, "alm_soc_samples"), label: "Real application screen — complete SOC sample cells",
    action: "Enter replicate SOC values for baseline and project sampling cells.",
    work: "Check sample completeness and prepare soil-stock change inputs.",
    note: "Emphasize that these are manually entered laboratory measurements, not invented satellite estimates. The application validates the sample structure before allowing the SOC quantification path to proceed.",
  });

  doubleDemo({
    step: 11, pathLabel: "CROPLAND", heading: "Calculate the scoped VM0042 estimate",
    sub: "The engine combines soil stock change with non-CO₂ sources and risk deductions.",
    left: demo(14, "vm0042_inputs"), right: demo(15, "vm0042_results"),
    leftLabel: "VM0042 verification and risk inputs", rightLabel: "VM0042 component results and final estimate",
    action: "Review the verification period and risk inputs, then calculate.",
    work: "Combine SOC, fertilizer, residue, fuel, burning and supported livestock terms.",
    note: "Explain the calculation as a scoped implementation. The engine handles SOC stock change, selected N2O and CH4 terms, fossil fuel CO2, uncertainty and non-permanence buffer. Do not claim complete methodology conformity where leakage data are missing.",
  });

  singleDemo({
    step: 12, pathLabel: "CROPLAND", heading: "Keep VM0042 uncertainty and gaps visible",
    sub: "The audit view discloses screening status and avoids silently treating missing evidence as zero.",
    image: demo(16, "vm0042_audit_trail"), label: "Real application screen — VM0042 audit trail and limitation messages",
    action: "Inspect component equations, uncertainty and leakage disclosures.",
    work: "Expose included sources, deductions and unquantified leakage categories.",
    caution: "A displayed estimate is not formal eligibility; incomplete leakage evidence remains disclosed.",
    note: "This slide demonstrates conservative software behavior. Missing or incomplete leakage evidence is surfaced to the user. The prototype provides an estimate with disclosures; it does not certify a project or issue credits.",
  });

  singleDemo({
    step: 13, pathLabel: "CROPLAND", heading: "Export the cropland evidence package",
    sub: "VM0042 outputs use the same audit pattern while preserving methodology-specific evidence.",
    image: demo(17, "vm0042_evidence_exports"), label: "Real application screen — VM0042 evidence downloads",
    action: "Download the PDF report, audit JSON and practice/SOC CSV.",
    work: "Serialize scenario inputs, results, factors and warnings by field.",
    caution: "Current CSV scope is practice/SOC only; livestock is included in PDF/JSON, not the CSV.",
    note: "Be precise about export completeness. The PDF and JSON include material inputs. The CSV currently covers practice and SOC data only; this is tracked under FR18 and should not be described as a complete evidence CSV.",
  });

  doubleDemo({
    step: 14, pathLabel: "AI", heading: "Train and compare the experimental AWD classifiers",
    sub: "The engineering pipeline works; the current metrics measure rule agreement, not independent field accuracy.",
    left: demo(18, "ai_training_pipeline"), right: demo(19, "ai_model_comparison"),
    leftLabel: "Training controls and saved model artifacts", rightLabel: "RF/XGBoost comparison and explicit label warning",
    action: "Train RF/XGBoost from cached rice observations and compare metrics.",
    work: "Build leakage-safe features, persist artifacts and retain rule fallback.",
    caution: "Labels come from the threshold gate; no independent irrigation ground truth is available yet.",
    note: "Be fully honest. This is an experimental extension, not a validated agronomic AI result. The current data set is small and labels originate from the rule-based gate, so the metrics show agreement with that rule. Your defensible work is the training/evaluation/persistence pipeline and transparent fallback.",
  });

  doubleDemo({
    step: 15, pathLabel: "SHARED", heading: "Review the project portfolio and registered assets",
    sub: "The final view connects methodology results back to persistent fields and calculation history.",
    left: demo(20, "portfolio_overview"), right: demo(21, "registered_fields"),
    leftLabel: "Portfolio summary by methodology", rightLabel: "Registered fields and field metadata",
    action: "Compare latest field results and inspect the asset registry.",
    work: "Aggregate latest stored runs without replacing the underlying history.",
    note: "End the demo here. The portfolio proves that the prototype is a project system rather than a one-off notebook: it manages multiple fields, two methodology types and persistent calculation history. Values shown are local prototype estimates, not issued credits.",
  });

  // Progress
  {
    const slide = pptx.addSlide("CONTENT");
    title(slide, "Implementation progress", "What is working at the midterm checkpoint", "Conservative status: implemented does not automatically mean independently validated.");
    const rows = [
      ["Field registry, geometry parsing and routing", "IMPLEMENTED", C.green],
      ["Sentinel-1 cache and transparent AWD gate", "IMPLEMENTED • MANUAL CHECK", C.green],
      ["VM0051 and scoped VM0042 engines", "AUTOMATED TESTS", C.blue],
      ["PDF/JSON evidence and methodology CSVs", "PARTIAL CSV SCOPE", C.amber],
      ["Calculation history and portfolio", "IMPLEMENTED • TESTS PENDING", C.amber],
      ["RF/XGBoost pipeline and saved artifacts", "EXPERIMENTAL", C.olive],
      ["Independent AWD ground-truth validation", "NOT COMPLETED", C.red],
    ];
    rows.forEach((r, i) => {
      const y = 1.55 + i * 0.7;
      slide.addShape(S.roundRect, { x: 0.72, y, w: 11.9, h: 0.54, rectRadius: 0.035, fill: { color: i % 2 ? "F9FAF7" : C.white }, line: { color: C.line, transparency: 35 } });
      slide.addText(r[0], { x: 1.0, y: y + 0.14, w: 7.45, h: 0.22, fontSize: 12.8, color: C.ink, margin: 0, fit: "shrink" });
      slide.addShape(S.roundRect, { x: 9.05, y: y + 0.1, w: 3.15, h: 0.34, rectRadius: 0.04, fill: { color: r[2] }, line: { color: r[2] } });
      slide.addText(r[1], { x: 9.18, y: y + 0.18, w: 2.89, h: 0.14, fontSize: 9.2, bold: true, color: C.white, align: "center", margin: 0, fit: "shrink" });
    });
    callout(slide, 1.25, 6.67, 10.85, 0.38, "Strongest verified area: accounting-engine regression tests. Largest evidence gap: independent AWD ground truth.", C.green, C.mint);
    notes(slide, "Use status language exactly. The accounting engines have automated regression coverage. Several UI, persistence and reporting components are implemented but need broader automated system tests. The AI pipeline is experimental.");
  }

  // Challenges
  {
    const slide = pptx.addSlide("CONTENT");
    title(slide, "Challenges and next work", "Known risks — and the engineering response", "A credible capstone makes uncertainty visible and testable.");
    const items = [
      ["Independent AWD truth", "Collect irrigation/field observations and validate by field and season.", C.red],
      ["Small drydown class", "Expand seasons and use grouped validation to prevent leakage.", C.amber],
      ["Earth Engine dependency", "Cache-first operation, readable errors and documented authentication.", C.blue],
      ["VM0042 scope gaps", "Implement, quantify or explicitly block each applicable leakage category.", C.olive],
      ["Local-only deployment", "Add authentication, backups and hosted persistence before deployment.", C.green],
      ["Known label/export defects", "Correct VM0051 wording and complete livestock CSV coverage.", C.red],
    ];
    items.forEach((it, i) => {
      const col = i % 2, row = Math.floor(i / 2), x = 0.67 + col * 6.15, y = 1.55 + row * 1.66;
      slide.addShape(S.roundRect, { x, y, w: 5.82, h: 1.38, rectRadius: 0.06, fill: { color: C.white }, line: { color: C.line } });
      slide.addShape(S.rect, { x, y, w: 0.09, h: 1.38, fill: { color: it[2] }, line: { color: it[2] } });
      slide.addText(it[0], { x: x + 0.3, y: y + 0.22, w: 5.18, h: 0.27, fontSize: 14, bold: true, color: C.navy, margin: 0, fit: "shrink" });
      slide.addText(it[1], { x: x + 0.3, y: y + 0.62, w: 5.18, h: 0.5, fontSize: 11.2, color: C.gray, margin: 0, fit: "shrink" });
    });
    notes(slide, "Choose the two most important risks: independent ground truth and methodology completeness. Explain concrete next steps rather than claiming that the limitations are already solved.");
  }

  // Corrected timeline
  {
    const slide = pptx.addSlide("CONTENT");
    title(slide, "Timeline", "Progress against the project plan", "Corrected Gantt chart with the 2 August 2026 midterm checkpoint.");
    addImagePanel(slide, correctedGantt, 0.56, 1.45, 12.2, 5.47, "Corrected project Gantt chart");
    sourceLink(slide, "Open corrected Gantt chart", correctedGantt);
    notes(slide, "Explain progress against plan rather than reading every date. The midterm checkpoint falls during methodology audit and documentation. Remaining work is final integration, hardening, evidence review and final submission.");
  }

  // Closing
  {
    const slide = pptx.addSlide();
    imageCrop(slide, fieldPhoto, 0, 0, 13.333, 7.5);
    slide.addShape(S.rect, { x: 0, y: 0, w: 13.333, h: 7.5, fill: { color: C.navy, transparency: 22 }, line: { color: C.navy, transparency: 100 } });
    slide.addShape(S.rect, { x: 0, y: 0, w: 8.7, h: 7.5, fill: { color: "102F20", transparency: 5 }, line: { color: "102F20", transparency: 100 } });
    slide.addText("FIELD  →  EVIDENCE  →  ACCOUNTING", { x: 0.74, y: 1.03, w: 5.7, h: 0.24, fontSize: 10.5, bold: true, color: "D8C27B", charSpacing: 1.25, margin: 0 });
    slide.addText("Terra-Audit turns agricultural evidence into a reproducible carbon estimate.", { x: 0.72, y: 1.5, w: 7.45, h: 1.45, fontSize: 30, bold: true, color: C.white, margin: 0, fit: "shrink" });
    const end = ["Field-specific evidence processing", "Transparent methodology calculations", "Persistent audit trail and exports"];
    end.forEach((t, i) => {
      slide.addShape(S.roundRect, { x: 0.75, y: 3.35 + i * 0.75, w: 6.55, h: 0.56, rectRadius: 0.05, fill: { color: C.navy2, transparency: 8 }, line: { color: "A8C39D", transparency: 50 } });
      slide.addShape(S.ellipse, { x: 1.0, y: 3.52 + i * 0.75, w: 0.22, h: 0.22, fill: { color: i === 1 ? C.amber : C.green }, line: { color: i === 1 ? C.amber : C.green } });
      slide.addText(t, { x: 1.45, y: 3.49 + i * 0.75, w: 5.42, h: 0.22, fontSize: 14.5, bold: true, color: C.white, margin: 0, fit: "shrink" });
    });
    slide.addText("AI remains experimental. The core contribution is the modular, auditable MRV workflow.", { x: 0.76, y: 5.85, w: 7.1, h: 0.45, fontSize: 15.5, color: "E3ECE0", italic: true, margin: 0, fit: "shrink" });
    slide.addText("QUESTIONS?", { x: 0.72, y: 6.55, w: 4.2, h: 0.55, fontSize: 28, bold: true, color: "D8C27B", margin: 0 });
    notes(slide, "Close with the exact contribution. Sentinel-1 provides observations. Terra-Audit contributes field management, evidence processing, methodology calculations, persistence, audit trails, exports and an extensible architecture. It does not issue credits, and the AI extension is not independently validated.");
  }

  function figureGrid(heading, sub, figures, note) {
    const slide = pptx.addSlide("CONTENT");
    title(slide, "Appendix • Detailed diagrams", heading, sub);
    const count = figures.length;
    const cols = count <= 2 ? count : count === 3 ? 3 : 2;
    const rows = Math.ceil(count / cols);
    const left = 0.56, top = 1.5, totalW = 12.2, totalH = 5.35, gapX = 0.2, gapY = 0.18;
    const w = (totalW - gapX * (cols - 1)) / cols;
    const h = (totalH - gapY * (rows - 1)) / rows;
    figures.forEach((f, i) => {
      const col = i % cols, row = Math.floor(i / cols);
      addImagePanel(slide, reportFig(f[0]), left + col * (w + gapX), top + row * (h + gapY), w, h, `Figure ${f[0]} — ${f[1]}`);
    });
    notes(slide, note);
  }

  figureGrid("System scope diagrams", "Use these only if the examiner asks for the less-detailed system boundary.", [
    [1, "Level-0 use case"], [2, "Level-1 use case"],
  ], "Appendix reference. Figure 1 summarizes the system boundary; Figure 2 decomposes the main capabilities.");

  figureGrid("Field-management diagrams", "Registration is decomposed into field management, geometry input and persistence.", [
    [3, "Field management"], [4, "Geometry input"], [5, "Field registration"],
  ], "Appendix reference. These diagrams support detailed questions about geometry formats, area computation, validation and database persistence.");

  figureGrid("Rice evidence-engine diagrams", "Satellite acquisition and signal interpretation are separate responsibilities.", [
    [6, "Satellite data engine"], [7, "Signal analytics"],
  ], "Appendix reference. Explain that the data engine retrieves and caches observations, while the analytics component interprets them.");

  figureGrid("Calculation, reporting and AI diagrams", "Detailed use cases for the calculation, reporting, AI and cropland subsystems.", [
    [8, "Carbon estimation"], [9, "Evidence reporting"], [10, "AI validation"], [11, "Cropland ALM"],
  ], "Appendix reference. Use one relevant diagram if the examiner asks about a particular subsystem; do not attempt to explain all four at once.");

  figureGrid("Detailed activity diagrams — evidence collection", "Subsystem flows for field management, geometry, satellite and signal analytics.", [
    [13, "Field management activity"], [14, "Geometry activity"], [15, "Satellite activity"], [16, "Signal analytics activity"],
  ], "Appendix reference. These activity diagrams show validations and controlled failure paths in the evidence-collection workflow.");

  figureGrid("Detailed activity diagrams — calculation and audit", "Subsystem flows for carbon estimation, evidence reporting and AI validation.", [
    [17, "Carbon estimation activity"], [18, "Evidence reporting activity"], [19, "AI validation activity"],
  ], "Appendix reference. These diagrams support questions about calculation decisions, export generation and AI fallback behavior.");
};
