"use strict";

const $ = id => document.getElementById(id);
const canvas = $("figure");
const state = {
  cases: [], runs: [], selected: null, case: null, data: null,
  view: "geometry", page: 0, log: "reference", attempt: 0,
  yaw: -.65, elevation: .47, zoom: 1, drag: null, hit: [], transform: null,
};
const pageSize = 5;
const splits = {train: "Training", validation: "Validation", test: "Test", edge: "Stress"};
const colors = {mint: "#75dfbf", orange: "#ff8056", text: "#d6e0ea", dim: "#8a9daf"};
const mono = '"IBM Plex Mono", "JetBrains Mono", "Adwaita Mono", monospace';

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

async function api(path) {
  const response = await fetch(path, {cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function fmt(value, digits = 3, unit = "") {
  return Number.isFinite(value) ? value.toFixed(digits) + unit : "—";
}
function count(value) {
  return Number.isFinite(value) ? value.toLocaleString("en-US") : "—";
}

function metric(id, main, suffix) {
  $(id).replaceChildren(document.createTextNode(main), node("small", suffix));
}

function splitPill(key) {
  return node("span", splits[key] || key, "split-pill " + (splits[key] ? key : ""));
}

function renderCatalogue() {
  const needle = $("search").value.trim().toLowerCase();
  const filter = $("split-filter").value;
  const rows = state.cases.filter(row =>
    (!filter || row.split === filter) && (!needle || row.id.toLowerCase().includes(needle))
  );
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  state.page = Math.max(0, Math.min(pages - 1, state.page));
  const start = state.page * pageSize;
  const elements = rows.slice(start, start + pageSize).map(row => {
    const tr = node("tr", undefined, row.id === state.selected ? "selected" : "");
    const button = node("button", row.id);
    button.type = "button";
    button.setAttribute("aria-label", "Inspect " + row.id);
    if (row.id === state.selected) button.setAttribute("aria-current", "true");
    button.disabled = !row.attempts;
    button.addEventListener("click", () => selectCase(row.id, true));
    const id = node("td");
    id.append(button);
    const split = node("td");
    split.append(splitPill(row.split));
    const badge = node("td");
    badge.append(node("span", row.status === "ok" ? "Accepted" : row.status === "failed" ? "Rejected" : row.phase || "Pending",
                      row.status === "ok" ? "pass" : "pass bad"));
    tr.append(id, split, node("td", fmt(row.ro, 3, " mm")), node("td", fmt(row.gap, 3, " mm")),
              node("td", fmt(row.re, 1)), node("td", fmt(row.flow, 4, "%")),
              node("td", fmt(row.gradient, 4, "%")), badge);
    return tr;
  });
  if (!elements.length) {
    const tr = node("tr");
    const cell = node("td", "No cases match this filter.");
    cell.colSpan = 8;
    tr.append(cell);
    elements.push(tr);
  }
  $("case-rows").replaceChildren(...elements);
  $("case-count").textContent = `${rows.length} OF ${state.cases.length} CASES`;
  $("page-range").textContent = rows.length ? `${start + 1}–${Math.min(start + pageSize, rows.length)} OF ${rows.length}` : "0 CASES";
  $("previous").disabled = state.page === 0;
  $("next").disabled = state.page >= pages - 1;
}

function renderInspector(detail) {
  const row = state.cases.find(item => item.id === detail.id);
  $("case-id").textContent = detail.id;
  $("case-split").replaceWith(Object.assign(splitPill(detail.split), {id: "case-split"}));
  $("case-attempts").textContent = `${detail.attempts.length} ${detail.attempts.length === 1 ? "ATTEMPT" : "ATTEMPTS"}`;
  $("radius").textContent = fmt(detail.request.outer_radius_mm, 3, " mm");
  $("gap").textContent = fmt(detail.request.gap_mm, 3, " mm");
  $("voxel").textContent = fmt(detail.request.voxel_size_mm, 3, " mm");
  $("reynolds").textContent = fmt(detail.physical.ReynoldsNumber, 1);
  $("case-flow").textContent = fmt(detail.report.Q_field_err_pct, 4, "%");
  $("case-gradient").textContent = fmt(detail.report.dpL_err_pct, 4, "%");
  $("case-cells").textContent = count(detail.report.mesh?.cells);
  $("case-source").textContent = detail.provenance.openfoam_version
    ? `OPENFOAM ${detail.provenance.openfoam_version.toUpperCase()} · ${(detail.provenance.git_commit || "").slice(0,7)}`
    : "—";
  $("case-status").textContent = row?.status === "ok" ? "Accepted" : row?.status === "failed" ? "Rejected" : detail.phase || "Pending";
  $("case-status").classList.toggle("bad", row?.status !== "ok");
  $("case-status").hidden = false;
  $("view-caption").textContent = detail.meta.query_rows
    ? `${detail.id} · ${count(detail.meta.query_rows)} CFD SAMPLES` : detail.id;
  $("logs-case").textContent = detail.id;
  $("artifact-path").textContent = detail.artifact;
  $("checks").hidden = !detail.checks.length;
  $("checks").open = false;
  $("check-list").replaceChildren(...detail.checks.map(check => {
    const item = node("li", undefined, check.passed ? "" : "bad");
    item.append(node("span", check.passed ? "✓" : "×"), document.createTextNode(check.name),
                node("small", check.detail));
    return item;
  }));
  const attempts = detail.attempts.map((trial, i) => {
    const label = `Attempt ${i + 1} · ${fmt(trial.voxel, 3, " mm")}${trial.selected ? " · Selected" : ""}`;
    const option = node("option", label);
    option.value = i;
    option.selected = trial.selected;
    return option;
  });
  $("attempt").replaceChildren(...attempts);
  state.attempt = Math.max(0, detail.attempts.findIndex(trial => trial.selected));
}

let selection = 0;
let logRequest = 0;
async function selectCase(id, reveal = false) {
  const row = state.cases.find(item => item.id === id);
  if (!row?.attempts) return;
  const version = ++selection;
  state.selected = id;
  state.case = state.data = null;
  $("case-id").textContent = id;
  $("case-status").hidden = true;
  $("point-detail").hidden = true;
  $("view-error").textContent = "Loading case artifacts…";
  $("view-error").hidden = false;
  renderCatalogue();
  draw();
  if (reveal) document.querySelector(".viewer").scrollIntoView({block: "start"});
  const base = "/api/cases/" + encodeURIComponent(id);
  const details = api(base);
  const field = api(base + "/view").catch(error => ({error: error.message}));
  try {
    const detail = await details;
    if (version !== selection) return;
    state.case = detail;
    renderInspector(detail);
    refreshLog();
    const payload = await field;
    if (version !== selection) return;
    if (payload.error) throw new Error(payload.error);
    state.data = payload;
    $("view-error").hidden = true;
    setView(state.view);
  } catch (error) {
    if (version === selection) $("view-error").textContent = error.message;
  }
}

async function refreshLog(live = false) {
  if (!state.case) return;
  const panel = $("log-text");
  const stickToEnd = !live || panel.scrollHeight - panel.scrollTop - panel.clientHeight < 30;
  const tag = ++logRequest;
  const attempt = state.case.attempts[state.attempt];
  $("attempt-reason").hidden = !attempt?.reason;
  $("attempt-reason").textContent = attempt?.reason || "";
  const endpoint = `/api/cases/${encodeURIComponent(state.selected)}/attempts/${state.attempt}/${state.log}`;
  if (!live) panel.textContent = "Loading log…";
  try {
    const data = await api(endpoint);
    if (tag !== logRequest) return;
    panel.textContent = data.text || "This attempt has no log for the selected stage.";
    if (stickToEnd) panel.scrollTop = panel.scrollHeight;
  } catch (error) {
    if (tag === logRequest) $("log-text").textContent = error.message;
  }
}

function plotContext(target) {
  const w = target.clientWidth;
  const h = target.clientHeight;
  const scale = Math.min(window.devicePixelRatio || 1, 2);
  if (!w || !h) return null;
  if (target.width !== Math.round(w * scale) || target.height !== Math.round(h * scale)) {
    target.width = Math.round(w * scale);
    target.height = Math.round(h * scale);
  }
  const ctx = target.getContext("2d");
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return {ctx, w, h};
}

function segment(ctx, a, b) {
  ctx.beginPath();
  ctx.moveTo(a[0], a[1]);
  ctx.lineTo(b[0], b[1]);
  ctx.stroke();
}

function frame({ctx, w, h}) {
  const glow = ctx.createRadialGradient(w * .53, h * .48, 0, w * .53, h * .48, Math.max(w, h) * .65);
  glow.addColorStop(0, "#132536");
  glow.addColorStop(1, "#090e14");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "#35506488";
  for (let x = 16; x < w; x += 20) {
    for (let y = 15; y < h; y += 20) ctx.fillRect(x, y, 1, 1);
  }
}

function geometry(plot, data) {
  const {ctx, w, h} = plot;
  const radius = data.radius_mm;
  const length = data.length_mm;
  const ca = Math.cos(state.yaw), sa = Math.sin(state.yaw);
  const ce = Math.cos(state.elevation), se = Math.sin(state.elevation);
  const factor = Math.min(w / (radius * 2.9), h * .72 / (length * ce + radius * 2 * Math.abs(se))) * state.zoom;
  const project = (x, y, z) => {
    const a = x * ca - y * sa;
    const b = x * sa + y * ca;
    const c = z - length / 2;
    return [w * .51 + a * factor, h * .52 - (c * ce + b * se) * factor, b * ce - c * se];
  };
  const footprint = radius * 1.34;
  ctx.strokeStyle = "#36536a55";
  ctx.lineWidth = 1;
  for (let i = -4; i <= 4; i++) {
    const p = footprint * i / 4;
    segment(ctx, project(p, -footprint, 0), project(p, footprint, 0));
    segment(ctx, project(-footprint, p, 0), project(footprint, p, 0));
  }
  const points = data.surface.map(p => {
    const pos = project(...p);
    return {p: pos, flow: false};
  });
  state.hit = data.points.map(p => ({p: project(p[0], p[1], p[2]), flow: true, sample: p}));
  points.push(...state.hit);
  points.sort((a, b) => a.p[2] - b.p[2]);
  const maxVelocity = Math.max(...data.cfd.map(p => p[1]));
  for (const point of points) {
    const [x,y,depth] = point.p;
    if (point.flow) {
      const ratio = Math.min(1, Math.max(0, point.sample[3] / maxVelocity));
      ctx.fillStyle = ratio > .7 ? "#ffb285" : ratio > .35 ? "#ff8056" : "#c65e43";
      ctx.fillRect(x - .85, y - .85, 1.7, 1.7);
    } else {
      const front = Math.min(.84, Math.max(.16, .48 + depth / (radius * 3.5)));
      ctx.fillStyle = `rgba(116,193,226,${front})`;
      ctx.fillRect(x - .65, y - .65, 1.3, 1.3);
    }
  }
  ctx.font = `11px ${mono}`;
  ctx.fillStyle = colors.dim;
  ctx.textAlign = "left";
  ctx.fillText(`Ø ${fmt(radius * 2, 2, " mm")}`, 14, h - 18);
  ctx.textAlign = "right";
  ctx.fillText(`L ${fmt(length, 2, " mm")}`, w - 14, h - 18);
  const origin = [42, h - 54];
  for (const [axis, tint, label] of [
    [[1,0,0], colors.orange, "X"], [[0,1,0], "#81a0df", "Y"], [[0,0,1], colors.mint, "Z"],
  ]) {
    const centre = project(0,0,0);
    const tip = project(...axis);
    const end = [origin[0] + (tip[0] - centre[0]) / factor * 21, origin[1] + (tip[1] - centre[1]) / factor * 21];
    ctx.strokeStyle = tint;
    ctx.fillStyle = tint;
    segment(ctx, origin, end);
    ctx.textAlign = "center";
    ctx.fillText(label, end[0], end[1] - 3);
  }
}

function line(ctx, points, X, Y, color) {
  if (!points.length) return;
  ctx.beginPath();
  points.forEach(([x, y], index) => index ? ctx.lineTo(X(x), Y(y)) : ctx.moveTo(X(x), Y(y)));
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.stroke();
}

function graphAxes({ctx, w, h}, x0, x1, y0, y1, xLabel, yLabel) {
  const bounds = {left: 61, top: 47, width: w - 83, height: h - 101};
  const X = v => bounds.left + (v - x0) / (x1 - x0 || 1) * bounds.width;
  const Y = v => bounds.top + (y1 - v) / (y1 - y0 || 1) * bounds.height;
  ctx.font = `11px ${mono}`;
  for (let i = 0; i <= 4; i++) {
    const x = x0 + (x1 - x0) * i / 4;
    const y = y0 + (y1 - y0) * i / 4;
    ctx.strokeStyle = "#35475580";
    ctx.lineWidth = 1;
    segment(ctx, [X(x), Y(y0)], [X(x), Y(y1)]);
    segment(ctx, [X(x0), Y(y)], [X(x1), Y(y)]);
    ctx.fillStyle = colors.dim;
    ctx.textAlign = "center";
    ctx.fillText(fmt(x, x1 - x0 > 20 ? 0 : 2), X(x), Y(y0) + 18);
    ctx.textAlign = "right";
    ctx.fillText(fmt(y, y1 - y0 > 5 ? 0 : 2), X(x0) - 9, Y(y) + 4);
  }
  ctx.fillStyle = colors.text;
  ctx.textAlign = "center";
  ctx.fillText(xLabel, (X(x0) + X(x1)) / 2, h - 10);
  ctx.save();
  ctx.translate(13, (Y(y0) + Y(y1)) / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(yLabel, 0, 0);
  ctx.restore();
  return {X, Y, bounds};
}

function velocity(plot, data) {
  const {ctx} = plot;
  const exact = data.analytic;
  const max = 1.08 * Math.max(...exact.map(p => p[1]), ...data.cfd.map(p => p[1]));
  const {X, Y} = graphAxes(plot, exact[0][0], exact.at(-1)[0], 0, max, "Radius (mm)", "Axial velocity (mm/s)");
  line(ctx, exact, X, Y, colors.mint);
  state.hit = data.cfd.map(p => {
    const pos = [X(p[0]), Y(p[1])];
    ctx.beginPath();
    ctx.fillStyle = colors.orange;
    ctx.arc(...pos, 2.45, 0, Math.PI * 2);
    ctx.fill();
    return {p: pos, sample: p, reference: p[2]};
  });
}

function slice(plot, data) {
  const {ctx, w, h} = plot;
  const extent = Math.min(w - 100, h - 80);
  const left = (w - extent) / 2, top = (h - extent) / 2 + 8;
  const grid = data.plane;
  const pixel = extent / grid.length;
  for (let y = 0; y < grid.length; y++) {
    for (let x = 0; x < grid[y].length; x++) {
      const v = Math.min(1, Math.abs(grid[y][x]) / data.voxel_mm);
      ctx.fillStyle = grid[y][x] < 0 ? `rgb(${46 - v*18},${103 - v*32},${142 - v*30})`
        : `rgb(${140 - v*120},${81-v*53},${52-v*17})`;
      ctx.fillRect(left + x * pixel, top + (grid.length - 1 - y) * pixel, pixel + .5, pixel + .5);
    }
  }
  ctx.strokeStyle = "#425668";
  ctx.strokeRect(left, top, extent, extent);
  ctx.fillStyle = colors.text;
  ctx.font = `11px ${mono}`;
  ctx.textAlign = "center";
  ctx.fillText("X (mm)", w / 2, h - 10);
  ctx.save();
  ctx.translate(left - 12, h / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("Y (mm)", 0, 0);
  ctx.restore();
  state.transform = {top, left, pixel};
}

function draw() {
  const plot = plotContext(canvas);
  if (!plot) return;
  frame(plot);
  state.hit = [];
  state.transform = null;
  if (!state.data) return;
  if (state.view === "geometry") geometry(plot, state.data);
  else if (state.view === "velocity") velocity(plot, state.data);
  else slice(plot, state.data);
}

function setView(view) {
  state.view = view;
  for (const button of document.querySelectorAll("[data-view]")) {
    button.setAttribute("aria-pressed", String(button.dataset.view === view));
  }
  canvas.classList.toggle("orbit", view === "geometry");
  $("reset").hidden = view !== "geometry";
  $("point-detail").hidden = true;
  const label = {
    geometry: [`PicoGK frame · CFD ${state.data?.sector_deg ?? 2}°`, "VDB surface", "CFD samples", "Drag to orbit · Scroll to zoom"],
    velocity: ["Central axial station", "Analytical solution", "CFD samples", "Select a sample to inspect"],
    sdf: ["Mid-length section · signed distance", "Solid extent (negative)", "Outside (positive)", "Select a cell to inspect"],
  }[view];
  $("view-badge").textContent = label[0];
  const a = node("span");
  a.append(node("i", "", view === "velocity" ? "mint" : ""), document.createTextNode(label[1]));
  const b = node("span");
  b.append(node("i", "", "orange"), document.createTextNode(label[2]));
  $("legend").replaceChildren(a, b);
  $("controls-hint").textContent = label[3];
  draw();
}

function inspectPoint(event) {
  if (!state.data) return;
  const bounds = canvas.getBoundingClientRect();
  const x = event.clientX - bounds.left, y = event.clientY - bounds.top;
  let text;
  if (state.view === "sdf") {
    const {top,left,pixel} = state.transform;
    const grid = state.data.plane;
    const i = Math.floor((x-left)/pixel), j = grid.length - 1 - Math.floor((y-top)/pixel);
    if (j >= 0 && j < grid.length && i >= 0 && i < grid[j].length) {
      text = `X ${fmt(state.data.plane_x[i], 2)} mm · Y ${fmt(state.data.plane_y[j], 2)} mm · SDF ${fmt(grid[j][i], 4)} mm`;
    }
  } else {
    const nearest = state.hit.reduce((best, point) => {
      const distance = Math.hypot(point.p[0] - x, point.p[1] - y);
      return distance < best.distance ? {point, distance} : best;
    }, {distance: 13});
    const hit = nearest.point;
    if (hit && state.view === "geometry") {
      const [x,y,z,u] = hit.sample;
      text = `CFD · (${fmt(x, 2)}, ${fmt(y, 2)}, ${fmt(z, 2)}) mm · axial velocity ${fmt(u, 3)} mm/s`;
    } else if (hit) {
      text = `Radius ${fmt(hit.sample[0], 3)} mm · CFD ${fmt(hit.sample[1], 3)} mm/s · analytical ${fmt(hit.reference, 3)} mm/s`;
    }
  }
  $("point-detail").hidden = !text;
  $("point-detail").textContent = text || "";
}

let runningMetrics = null;
let comparisonLabel = "Validation";
function drawLoss() {
  const plot = plotContext($("loss-chart"));
  if (!plot) return;
  const {ctx, w} = plot;
  const metrics = runningMetrics || [];
  if (!metrics.length) {
    ctx.font = `12px ${mono}`;
    ctx.fillStyle = colors.dim;
    ctx.fillText("No loss samples published.", 15, 30);
    return;
  }
  const upper = Math.max(...metrics.flatMap(row => [row.train_loss,row.validation_loss]));
  const {X, Y} = graphAxes(plot, metrics[0].step, metrics.at(-1).step, 0, upper * 1.1 || 1, "Step", "Loss");
  line(ctx, metrics.map(r => [r.step,r.train_loss]), X, Y, colors.orange);
  line(ctx, metrics.map(r => [r.step,r.validation_loss]), X, Y, colors.mint);
  ctx.font = `11px ${mono}`;
  ctx.textAlign = "right";
  ctx.fillStyle = colors.orange;
  ctx.fillText("Training", w - 115, 19);
  ctx.fillStyle = colors.mint;
  ctx.fillText(comparisonLabel, w - 14, 19);
}

async function refreshTraining() {
  const menu = $("training-select");
  const id = menu.value;
  if (!id) return;
  try {
    const view = await api("/api/runs/" + encodeURIComponent(id));
    if (menu.value !== id) return;
    $("training-meta").textContent = [view.run.status, view.run.commit, view.run.command].filter(Boolean).join(" · ");
    $("training-log").textContent = view.log || "No log published.";
    runningMetrics = view.metrics;
    comparisonLabel = view.run.split === "reconstruction" ? "Reconstruction" : "Validation";
    drawLoss();
  } catch (error) {
    $("training-meta").textContent = error.message;
  }
}

function updateRunList(runs) {
  state.runs = runs;
  const menu = $("training-select");
  const current = menu.value;
  menu.replaceChildren(...runs.map(run => {
    const option = node("option", `${run.model || run.id} · ${run.status || "recorded"}`);
    option.value = run.id;
    option.selected = run.id === current;
    return option;
  }));
  $("training-empty").hidden = runs.length > 0;
  $("training-live").hidden = !runs.length;
  menu.hidden = !runs.length;
  refreshTraining();
}

let activeCommit = null;
async function showDiff(commit) {
  const panel = $("diff-text");
  activeCommit = commit;
  panel.hidden = false;
  panel.textContent = "Loading " + commit + "…";
  try {
    const diff = await api("/api/commits/" + encodeURIComponent(commit));
    if (activeCommit === commit) panel.textContent = diff.text + (diff.truncated ? "\nOutput limited to 32,000 characters." : "");
  } catch (error) {
    if (activeCommit === commit) panel.textContent = error.message;
  }
}

async function refreshOverview() {
  try {
    const data = await api("/api/overview");
    const previous = state.cases.find(c => c.id === state.selected);
    const changed = JSON.stringify(state.cases) !== JSON.stringify(data.cases);
    state.cases = data.cases;
    const ok = data.cases.filter(c => c.status === "ok");
    const prepared = data.cases.filter(c => c.prepared);
    $("batch-version").textContent = (data.batch.split("-").at(-1) || "").toUpperCase();
    $("connection").classList.remove("offline");
    $("connection").lastElementChild.textContent = "Local data connected";
    $("revision").textContent = data.commits.length ? `SOURCE ${data.commits[0].commit}` : "SOURCE REVISION UNAVAILABLE";
    metric("accepted", String(ok.length), `/ ${data.cases.length}`);
    metric("prepared", String(prepared.length), `/ ${data.cases.length}`);
    metric("flow", fmt(Math.max(...ok.map(c => c.flow ?? -Infinity)), 4), "%");
    metric("gradient", fmt(Math.max(...ok.map(c => c.gradient ?? -Infinity)), 4), "%");
    if (data.grid.length) $("prepared-sub").textContent = "SDF " + data.grid.join(" × ");
    if (changed) renderCatalogue();
    $("commits").replaceChildren(...data.commits.map(commit => {
      const li = node("li");
      const button = node("button");
      button.type = "button";
      button.setAttribute("aria-label", "Inspect commit " + commit.commit);
      button.title = commit.time;
      button.append(node("code", commit.commit));
      button.addEventListener("click", () => showDiff(commit.commit));
      li.append(button, node("span", commit.subject));
      return li;
    }));
    updateRunList(data.runs);
    if (!state.selected) {
      const start = prepared.find(c => c.id === "ann-7939f294") || prepared[0] || ok[0];
      if (start) selectCase(start.id);
    } else {
      const current = state.cases.find(c => c.id === state.selected);
      if (current && (previous?.status !== current.status || previous?.attempts !== current.attempts)) {
        selectCase(current.id);
      } else if (current?.status === "pending") {
        if (current.phase) $("case-status").textContent = current.phase;
        refreshLog(true);
      }
    }
  } catch (error) {
    $("connection").classList.add("offline");
    $("connection").lastElementChild.textContent = "Local data unavailable";
    $("revision").textContent = error.message;
  }
}

canvas.addEventListener("keydown", e => {
    if (state.view !== "geometry") return;
    const actions = {ArrowLeft: [-.15,0], ArrowRight: [.15,0], ArrowUp: [0,.12], ArrowDown: [0,-.12]};
    if (!actions[e.key]) return;
    e.preventDefault();
    state.yaw += actions[e.key][0];
    state.elevation = Math.max(-1.2, Math.min(1.2, state.elevation + actions[e.key][1]));
    draw();
});
canvas.addEventListener("pointerdown", e => {
  if (state.view !== "geometry") return;
  state.drag = {x: e.clientX, y: e.clientY, moved: false};
  canvas.setPointerCapture(e.pointerId);
  canvas.classList.add("grabbing");
});
canvas.addEventListener("pointermove", e => {
  if (!state.drag) return;
  const dx = e.clientX - state.drag.x, dy = e.clientY - state.drag.y;
  state.drag.moved ||= Math.abs(dx) + Math.abs(dy) > 2;
  state.drag.x = e.clientX;
  state.drag.y = e.clientY;
  state.yaw += dx * .009;
  state.elevation = Math.max(-1.2, Math.min(1.2, state.elevation + dy * .009));
  draw();
});
canvas.addEventListener("pointerup", e => {
  if (!state.drag?.moved) inspectPoint(e);
  state.drag = null;
  canvas.classList.remove("grabbing");
});
canvas.addEventListener("pointercancel", () => {
  state.drag = null;
  canvas.classList.remove("grabbing");
});
canvas.addEventListener("wheel", event => {
  if (state.view !== "geometry") return;
  event.preventDefault();
  state.zoom = Math.min(2.3, Math.max(.52, state.zoom * Math.exp(-event.deltaY * .001)));
  draw();
}, {passive: false});
$("reset").addEventListener("click", () => {
  Object.assign(state, {yaw: -.65, elevation: .47, zoom: 1});
  draw();
});
for (const button of document.querySelectorAll("[data-view]")) {
  button.addEventListener("click", () => setView(button.dataset.view));
}
for (const button of document.querySelectorAll("[data-log]")) {
  button.addEventListener("click", () => {
    state.log = button.dataset.log;
    for (const item of document.querySelectorAll("[data-log]")) {
      item.setAttribute("aria-pressed", String(item === button));
    }
    refreshLog();
  });
}
$("attempt").addEventListener("change", () => {
  state.attempt = Number($("attempt").value);
  refreshLog();
});
$("training-select").addEventListener("change", refreshTraining);
for (const key of ["search","split-filter"]) {
  $(key).addEventListener(key === "search" ? "input" : "change", () => {
    state.page = 0;
    renderCatalogue();
  });
}
$("previous").addEventListener("click", () => { state.page--; renderCatalogue(); });
$("next").addEventListener("click", () => { state.page++; renderCatalogue(); });
window.addEventListener("hashchange", () => {
  for (const link of document.querySelectorAll("nav a")) {
    link.classList.toggle("nav-active", link.hash === (location.hash || "#overview"));
  }
});
new ResizeObserver(draw).observe($("viewport"));
new ResizeObserver(drawLoss).observe($("loss-chart"));
setView("geometry");
refreshOverview();
setInterval(() => { if (!document.hidden) refreshOverview(); }, 8000);
