const COLORS = {reference: "var(--ref)", nothing: "var(--nothing)", stop_early: "var(--early)", naive: "var(--naive)"};
const LABELS = {reference: "Reference desk (scripted)", nothing: "Do nothing", stop_early: "Stop early (3 h)", naive: "Naive script"};
const FM_TEXT = {
  never_handled: "Had a problem while the desk was on duty, a legal fix existed, never touched.",
  cascade_blind: "Fixed once, broke again after a later alert, left broken.",
  ignored_notice: "Rebooked through a flight a published closure notice had already doomed.",
  procrastinated: "Desk waited; by the time it acted the best option was 2+ h worse.",
  worse_choice: "Picked an itinerary 3+ h later than the best legal one at that moment.",
  priority_inversion: "Medical / minor / deadline group lost value while seats on its route went to lower priority.",
  harmful_churn: "Moved a healthy booking and made it worse.",
  denied_boarding: "Groups offloaded from an oversold flight.",
  stopped_early: "Alerts that fired after the desk ended its shift.",
};
const AGENT_COLORS = ["#f59e0b", "#fb923c", "#facc15", "#f97316", "#fbbf24", "#ea580c"];
let DATA, EXPL, seed;
const $ = (s) => document.querySelector(s);
const tip = $("#tip");
function showTip(e, html) { tip.innerHTML = html; tip.style.display = "block"; tip.style.left = (e.clientX + 14) + "px"; tip.style.top = (e.clientY + 14) + "px"; }
function hideTip() { tip.style.display = "none"; }
const color = (r, i) => r.kind === "agent" ? AGENT_COLORS[i % AGENT_COLORS.length] : COLORS[r.label];
const label = (r) => r.kind === "agent" ? r.label : LABELS[r.label];
const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;

async function main() {
  DATA = await (await fetch("data/runs.json")).json();
  try { EXPL = await (await fetch("data/exploits.json")).json(); } catch { EXPL = null; }
  const seeds = Object.keys(DATA.seeds);
  seed = seeds[0];
  headline();
  const tabs = $("#seedTabs");
  tabs.innerHTML = `<span style="color:var(--muted);font-size:13px;align-self:center;margin-right:4px">Seed</span>` +
    seeds.map(s => `<button data-s="${s}" class="${s === seed ? "on" : ""}">${s}</button>`).join("");
  tabs.onclick = (e) => { const s = e.target.dataset.s; if (!s) return; seed = s; [...tabs.querySelectorAll("button")].forEach(b => b.classList.toggle("on", b.dataset.s === s)); render(); };
  exploits();
  render();
}

function headline() {
  const agentScores = [], byModel = {};
  for (const sd of Object.values(DATA.seeds)) for (const r of sd.runs) if (r.kind === "agent") { agentScores.push(r.score); (byModel[r.model] ||= []).push(r.score); }
  const sd0 = Object.values(DATA.seeds)[0];
  const stats = [];
  for (const [m, s] of Object.entries(byModel)) stats.push([mean(s).toFixed(2), `${m} mean score (${s.length} runs, best ${Math.max(...s).toFixed(2)})`]);
  stats.push(["1.00", "Scripted reference desk, every seed"]);
  stats.push(["0.00", "Do nothing / end shift at once"]);
  stats.push([`${sd0.bookings.toLocaleString()}`, `bookings · ${sd0.flights} flights · 9 alerts`]);
  $("#headline").innerHTML = stats.map(([v, k]) => `<div class="stat"><div class="v">${v}</div><div class="k">${k}</div></div>`).join("");
}

function render() { bars(); curve(); alerts(); failures(); }

function bars() {
  const runs = DATA.seeds[seed].runs;
  const order = ["nothing", "stop_early", "naive"];
  const rows = [...runs.filter(r => r.kind === "agent"), ...order.map(o => runs.find(r => r.label === o)), runs.find(r => r.label === "reference")].filter(Boolean);
  const lo = Math.min(0, ...rows.map(r => r.score)), hi = Math.max(1.05, ...rows.map(r => r.score));
  const W = 900, rowH = 30, L = 210, H = rows.length * rowH + 30;
  const x = (v) => L + (v - lo) / (hi - lo) * (W - L - 60);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%">`;
  for (const t of [0, 0.25, 0.5, 0.75, 1]) s += `<line x1="${x(t)}" x2="${x(t)}" y1="0" y2="${H - 20}" stroke="#24314f" ${t === 1 ? 'stroke-dasharray="4 4" stroke="#5eead4"' : ""}/><text x="${x(t)}" y="${H - 4}" text-anchor="middle">${t}</text>`;
  let ai = 0;
  rows.forEach((r, i) => {
    const y = i * rowH + 6, c = r.kind === "agent" ? AGENT_COLORS[ai++ % 6] : COLORS[r.label];
    const fm = Object.entries(r.failure_modes).filter(([, v]) => v.count).map(([k, v]) => `${k}: ${v.count}`).join("<br>") || "none";
    s += `<g onmousemove="showTip(event, '<b>${label(r)}</b><br>score ${r.score.toFixed(3)} · value ${r.value}<br>tool calls ${r.tool_calls}, errors ${r.tool_errors}<br>ended ${r.ended_at} (${r.end_reason})<hr style=&quot;border-color:#24314f&quot;>${fm}')" onmouseleave="hideTip()">
      <text x="${L - 10}" y="${y + 15}" text-anchor="end" style="fill:#e7ecf6;font-family:Inter;font-size:12px">${label(r)}</text>
      <rect x="${x(Math.min(0, r.score))}" y="${y + 3}" width="${Math.max(2, Math.abs(x(r.score) - x(0)))}" height="16" rx="4" fill="${c}"/>
      <text x="${x(Math.max(0, r.score)) + 8}" y="${y + 15}">${r.score.toFixed(2)}</text></g>`;
  });
  $("#scoreBars").innerHTML = s + "</svg>";
}

function curve() {
  const runs = DATA.seeds[seed].runs.filter(r => r.label !== "nothing");
  const tt = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
  const all = runs.flatMap(r => r.curve.map(p => p.value));
  const lo = Math.min(...all), hi = Math.max(...all);
  const W = 900, H = 320, L = 60, B = 30;
  const x = (t) => L + (tt(t) - 360) / (1380 - 360) * (W - L - 20);
  const y = (v) => 10 + (hi - v) / (hi - lo || 1) * (H - B - 10);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%">`;
  for (let h = 6; h <= 23; h += 2) { const t = `${String(h).padStart(2, "0")}:00`; s += `<line x1="${x(t)}" x2="${x(t)}" y1="10" y2="${H - B}" stroke="#1c2742"/><text x="${x(t)}" y="${H - 10}" text-anchor="middle">${t}</text>`; }
  for (const e of DATA.seeds[seed].events) s += `<line x1="${x(e.time)}" x2="${x(e.time)}" y1="10" y2="${H - B}" stroke="#4a3a16" stroke-dasharray="3 3"/><circle cx="${x(e.time)}" cy="14" r="4" fill="#f59e0b" onmousemove="showTip(event, '<b>${e.id} · ${e.time}</b><br>${e.text.replace(/'/g, "&#39;")}')" onmouseleave="hideTip()"/>`;
  let ai = 0, legend = "";
  for (const r of runs) {
    const c = r.kind === "agent" ? AGENT_COLORS[ai++ % 6] : COLORS[r.label];
    const pts = r.curve.filter(p => tt(p.t) <= 1380).map(p => `${x(p.t)},${y(p.value)}`).join(" ");
    s += `<polyline points="${pts}" fill="none" stroke="${c}" stroke-width="${r.label === "reference" ? 3 : 2}" ${r.kind === "scripted" && r.label !== "reference" ? 'stroke-dasharray="5 4"' : ""}/>`;
    legend += `<span><i style="background:${c}"></i>${label(r)}</span>`;
  }
  s += `<text x="8" y="16">value</text></svg>`;
  $("#curve").innerHTML = `<div class="legend">${legend}<span><i style="background:#f59e0b;height:8px;width:8px;border-radius:50%"></i>alert</span></div>` + s;
}

function alerts() {
  const sd = DATA.seeds[seed], agents = sd.runs.filter(r => r.kind === "agent");
  const head = agents.map((r, i) => `<th>${r.label}</th>`).join("");
  const rows = sd.events.map((e, k) => {
    const cells = agents.map((r, i) => {
      const c = r.coherence[k], v = c && c.recovered;
      if (v === null || v === undefined) return `<td class="n" style="color:var(--muted)">n/a</td>`;
      const pct = Math.max(0, Math.min(1.2, v));
      const col = v >= 0.9 ? "var(--good)" : v >= 0.5 ? "var(--agent)" : "var(--bad)";
      return `<td><div class="bar"><span style="width:${pct / 1.2 * 100}%;background:${col}"></span></div><div class="n" style="text-align:left;margin-top:3px">${(v * 100).toFixed(0)}%</div></td>`;
    }).join("");
    const hit = sd.runs.find(r => r.label === "reference").coherence[k].bookings_hit;
    return `<tr class="alertrow"><td>${e.time}</td><td>${e.text}<div style="color:var(--muted);font-size:12px;margin-top:3px">${hit} bookings hit</div></td>${cells}</tr>`;
  }).join("");
  $("#alerts").innerHTML = agents.length ? `<table><tr><th>Time</th><th>Alert</th>${head}</tr>${rows}</table>` : `<p class="sub">No agent runs for this seed yet.</p>`;
}

function failures() {
  const agents = Object.values(DATA.seeds).flatMap(sd => sd.runs.filter(r => r.kind === "agent"));
  const ref = Object.values(DATA.seeds).map(sd => sd.runs.find(r => r.label === "reference"));
  const naive = Object.values(DATA.seeds).map(sd => sd.runs.find(r => r.label === "naive"));
  const sum = (rs, k, f) => rs.reduce((a, r) => a + (r.failure_modes[k] ? r.failure_modes[k][f] : 0), 0);
  const keys = Object.keys(FM_TEXT).sort((a, b) => sum(agents, b, "value_lost") - sum(agents, a, "value_lost"));
  $("#failures").innerHTML = keys.map(k => `<div class="fm"><h3>${k}</h3><p>${FM_TEXT[k]}</p>
    <div class="row"><span>Agent runs (avg per run)</span><b>${agents.length ? (sum(agents, k, "count") / agents.length).toFixed(1) : "–"}</b></div>
    <div class="row"><span>Agent value lost (avg)</span><b>${agents.length ? (sum(agents, k, "value_lost") / agents.length).toFixed(1) : "–"}</b></div>
    <div class="row"><span>Naive script (avg)</span><b>${(sum(naive, k, "count") / naive.length).toFixed(1)}</b></div>
    <div class="row"><span>Reference (avg)</span><b>${(sum(ref, k, "count") / ref.length).toFixed(1)}</b></div></div>`).join("");
}

function exploits() {
  if (!EXPL) { $("#exploits").innerHTML = "<p class='sub'>Run python -m opsdesk.exploits to fill this table.</p>"; return; }
  const rows = Object.entries(EXPL).map(([k, v]) => {
    const m = mean(v), ok = k === "reference" || k === "reference_but_never_end" ? "" : m < 0.5 ? "pill" : "";
    return `<tr><td style="font-family:'IBM Plex Mono'">${k}</td>${v.map(s => `<td class="n">${s.toFixed(3)}</td>`).join("")}<td class="n"><b>${m.toFixed(3)}</b></td></tr>`;
  }).join("");
  $("#exploits").innerHTML = `<table><tr><th>Attempt</th>${EXPL.reference.map((_, i) => `<th style="text-align:right">seed ${i + 1}</th>`).join("")}<th style="text-align:right">mean</th></tr>${rows}</table>`;
}
main();
