// CFturbo · Controlador — lógica de la página (módulo ES, sin build). Ver agents/out/ux_1.md y ux_2.md.
// Secciones: utilidades · parámetros y opciones · proyecto base · sondeo · galería · corrida activa (A) ·
// comparación (B) · dock · chat · visor 3D · miniaturas · tema/atajos · arranque.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';

const $ = id => document.getElementById(id);
const LS = {  // localStorage puede fallar (modo privado): nunca debe tumbar la página
  get(k, d = null) { try { const v = localStorage.getItem(k); return v ?? d; } catch { return d; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} },
};
const st = {
  projects: [], project: null, info: null, runs: [], run: null, runB: null, pinned: false,
  meshes: new Map(), showCaps: false, chatting: false, session: null, status: {},
  filter: 'all', tab: LS.get('cft_tab', 'chat'), lastName: null, prevStatus: new Map(),
  online: true, failures: 0, retryAt: 0, lastMsg: '', loadedKey: '', overlayB: LS.get('cft_overlay_b') === '1',
  compact: LS.get('cft_density') === 'list', view: null,
};
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// Separador decimal: coma en TODA la interfaz (tabla, placeholders, comparar, duraciones). Los inputs aceptan coma o punto.
const fmt = (x, d = 1) => x == null || x === '' || isNaN(+x) ? '–' : (+x).toFixed(d).replace('.', ',');
const fmtIn = (x, d = 1) => x == null || x === '' || isNaN(+x) ? '' : (+x).toFixed(d).replace('.', ',');
const parseNum = v => { const s = String(v).trim().replace(',', '.'); return s === '' ? null : +s; };
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const fdate = iso => { const d = new Date(iso); return isNaN(d) ? '' : `${d.getDate()} ${MESES[d.getMonth()]} ${iso.slice(11, 16)}`; };
const elapsed = iso => Math.max(0, Math.round((Date.now() - new Date(iso)) / 1000));
const plural = (n, s, p = s + 's') => `${n} ${n === 1 ? s : p}`;
const TAG = { running: 'Corriendo', ok: 'OK', warn: 'Con avisos', error: 'Error' };
const tag = r => `<span class="tag ${esc(r?.status)}">${TAG[r?.status] || esc(r?.status || '')}</span>`;
// «★ como X» solo si la versión X existe de verdad en la galería (D-N6)
const versionExists = id => !!id && st.runs.some(x => x.saved && x.id === id);
function savedTag(r, short = false) {
  if (r?.saved) return '<span class="tag saved">★ Guardada</span>';
  if (!versionExists(r?.saved_as_version)) return '';
  const v = esc(r.saved_as_version);
  return `<span class="tag saved" title="Guardada como versions/${v}">${short ? '★' : '★ como ' + v}</span>`;
}
const runLabel = r => r ? (r.saved ? r.id : r.name) : '';
const api = async (url, body, timeoutMs = 0) => {
  const ctl = timeoutMs ? new AbortController() : null, t = ctl && setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const opt = body === undefined ? {} : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) };
    const r = await fetch(url, ctl ? { ...opt, signal: ctl.signal } : opt);
    if (!r.ok) { let d = r.status; try { d = (await r.json()).detail || d; } catch {} const e = new Error(d); e.status = r.status; throw e; }
    return r.json();
  } finally { clearTimeout(t); }
};

// ---------------------------------------------------------------- avisos flotantes
let toastT = 0;
function toast(text, kind = '') {
  const t = $('toast'); t.className = kind; t.textContent = text;
  clearTimeout(toastT); toastT = setTimeout(() => { t.textContent = ''; }, 6000);
}
function runMsg(text, kind = '', keepMs = 0) {
  const m = $('runmsg'); m.className = kind; m.textContent = text;
  m.dataset.keep = keepMs ? Date.now() + keepMs : 0;
}

// ---------------------------------------------------------------- parámetros y opciones
const PARAMS = [
  { key: 'Q_m3h', sym: 'Q', label: 'Caudal Q', unit: 'm³/h', from: i => i?.design_point?.Q_m3h, d: 1 },
  { key: 'H_m', sym: 'H', label: 'Altura H', unit: 'm', from: i => i?.design_point?.H_m, d: 1 },
  { key: 'n_rpm', sym: 'n', label: 'Velocidad n', unit: 'rpm', from: i => i?.design_point?.n_rpm, d: 0 },
  { key: 'd2_mm', sym: 'd2', label: 'Diámetro de salida d2', unit: 'mm', from: i => i?.dims?.d2_mm, d: 1 },
  { key: 'b2_mm', sym: 'b2', label: 'Ancho de salida b2', unit: 'mm', from: i => i?.dims?.b2_mm, d: 2 },
  { key: 'dS_mm', sym: 'dS', label: 'Diámetro de succión dS', unit: 'mm', from: i => i?.dims?.dS_mm, d: 1 },
  { key: 'dH_mm', sym: 'dH', label: 'Diámetro de cubo dH', unit: 'mm', from: i => i?.dims?.dH_mm, d: 1 },
  { key: 'Psi', sym: 'ψ', label: 'Coeficiente de presión ψ', unit: '', from: i => i?.dims?.Psi, d: 3 },
  { key: 'nBl', sym: 'z', label: 'Número de álabes', unit: 'álabes', from: i => i?.dims?.nBl, d: 0 },
  { key: 'volute_d_out_mm', sym: 'dV', label: 'Diámetro de salida de la voluta', unit: 'mm', from: i => i?.dims?.volute_d_out_mm, d: 1 },
];
// nombre por defecto: <proyecto>_<n> con n = siguiente libre (no «v2» fijo)
function defaultName() {
  const p = (st.project || 'corrida').replace(/[^A-Za-z0-9_-]+/g, '_'), rx = new RegExp('^' + p + '_(\\d+)$');
  const n = Math.max(0, ...st.runs.map(r => +(rx.exec(r.name || '') || [0, 0])[1])) + 1;
  return `${p}_${n}`;
}
const fromRun = () => $('fromrun').checked && !!st.run;
const paramInputs = () => [...$('params').querySelectorAll('input')];
function renderParams() {
  const base = st.info, run = st.run?.info, src = fromRun() ? run : base;
  $('runcol').textContent = st.run ? runLabel(st.run) : 'Corrida'; $('runcol').title = st.run ? runLabel(st.run) : '';
  const tb = $('params').querySelector('tbody');
  const prev = Object.fromEntries(paramInputs().map(i => [i.dataset.k, i.value]));
  tb.innerHTML = PARAMS.map(p => {
    const b = p.from(base), r = p.from(run);
    const changed = b != null && r != null && Math.abs(b - r) > 1e-9;
    return `<tr title="${p.label}${p.unit ? ' (' + p.unit + ')' : ''}"><td><b>${p.sym}</b> <span class="mut">${p.unit}</span></td><td class="num">${fmt(b, p.d)}</td><td class="num${changed ? ' changed' : ''}">${fmt(r, p.d)}</td><td><input data-k="${p.key}" type="text" inputmode="decimal" autocomplete="off" aria-label="${p.label} nuevo" value="${esc(prev[p.key] ?? '')}" placeholder="${fmtIn(p.from(src) ?? b, p.d)}"></td></tr>`;
  }).join('') + `<tr title="Velocidad específica nq"><td><b>nq</b></td><td class="num">${fmt(base?.nq?.nq)}</td><td class="num">${fmt(run?.nq?.nq)}</td><td class="num" id="nqcell"></td></tr>`;
  for (const i of paramInputs()) i.addEventListener('input', onEdit);
  onEdit();
}
function paramEdits() {  // solo la tabla; un valor que no es número se marca y no se envía
  const e = {};
  for (const i of paramInputs()) {
    const v = parseNum(i.value), bad = v != null && !isFinite(v);
    i.classList.toggle('bad', bad); i.setAttribute('aria-invalid', String(bad));
    if (v != null && !bad) e[i.dataset.k] = v;
  }
  return e;
}
function edits() {
  const e = paramEdits();
  if ($('autoupd').checked) e.AutoUpdate = true;
  if ($('extoff').checked && !$('extoff').disabled) e.ext_outlet = false;
  return e;
}
function onEdit() {
  for (const i of paramInputs()) i.closest('tr').classList.toggle('edited', i.value.trim() !== '');
  nqNew(); renderFoot();
}
function nqNew() {
  const e = paramEdits(), src = fromRun() && st.run?.info ? st.run.info : st.info;
  const Q = e.Q_m3h ?? src?.design_point?.Q_m3h, H = e.H_m ?? src?.design_point?.H_m, n = e.n_rpm ?? src?.design_point?.n_rpm;
  if (!(Q > 0 && H > 0 && n > 0)) { $('nqnew').textContent = '–'; $('nqtipo').textContent = ''; return; }
  const v = n * Math.sqrt(Q / 3600) / Math.pow(H, .75);
  const tipo = v < 10 ? 'radial muy lenta' : v < 30 ? 'radial lenta' : v < 50 ? 'radial normal' : v < 80 ? 'radial rápida / semiaxial' : v < 160 ? 'flujo mixto' : 'axial';
  $('nqnew').textContent = fmt(v); $('nqtipo').textContent = tipo; const c = $('nqcell'); if (c) c.textContent = fmt(v);
}
// Pie: una línea con lo que se va a lanzar (cambios, origen, AutoUpdate en ámbar). #runmsg queda para resultados.
function renderFoot() {
  const n = Object.keys(paramEdits()).length;
  $('clear').disabled = !n;
  const nopt = ['autoupd', 'extoff'].filter(id => $(id).checked && !$(id).disabled).length + ['exCCM', 'exSTL'].filter(id => $(id).checked).length;
  $('optsum').textContent = `Opciones · ${nopt} activas`;
  const from = fromRun() ? 'desde ' + esc(runLabel(st.run)) : 'desde la base';
  const bits = [n ? plural(n, 'cambio') : 'sin cambios (solo exporta)', from];
  if ($('extoff').checked && !$('extoff').disabled) bits.push('sin extensión CFD');
  if ($('autoupd').checked) bits.push('<b class="warn">AutoUpdate activo</b>');
  $('runsum').innerHTML = bits.join(' · ');
  if (!st.status.running && !(+$('runmsg').dataset.keep > Date.now()) && $('runmsg').className !== 'err') runMsg('');
  $('rname').placeholder = defaultName();
}
$('clear').onclick = () => { for (const i of paramInputs()) i.value = ''; onEdit(); };
for (const id of ['autoupd', 'extoff', 'exCCM', 'exSTL']) $(id).onchange = onEdit;

// «Quitar extensión CFD»: marcada por defecto solo si el origen tiene CFDSetup_RotSym con la extensión activa;
// deshabilitada si no hay CFDSetup_RotSym (ext_outlet daría «parámetro no encontrado»).
function extSource() {
  const r = fromRun() ? st.run : null;
  if (r?.info && 'cfd_ext_outlet' in r.info) return r.info.cfd_ext_outlet;
  if (r?.edits?.ext_outlet === false) return false;  // corrida antigua que ya la quitó
  return st.info?.cfd_ext_outlet;
}
function applyExtDefault() {
  const v = extSource(), cb = $('extoff'), lbl = $('extofflbl');
  cb.disabled = v == null; cb.checked = v === true;
  lbl.classList.toggle('off', v == null);
  lbl.title = v == null ? 'Este proyecto no tiene extensión CFD de salida (CFDSetup_RotSym)' : v ? 'La extensión de salida está activa en el origen' : 'El origen ya no tiene la extensión activa';
  renderFoot();
}

// «Partir de»: control segmentado; la casilla oculta #fromrun sigue siendo la fuente de verdad
function setFrom(run) { $('fromrun').checked = run; renderSeg(); renderParams(); applyExtDefault(); }
function renderSeg() {
  const r = st.run, ok = !!r && r.status !== 'running' && r.status !== 'error';
  if (!ok && $('fromrun').checked) $('fromrun').checked = false;
  $('segrun').disabled = !ok;
  $('segrun').textContent = r ? runLabel(r) : 'Corrida';
  $('segrun').title = !r ? 'Selecciona una corrida en la galería' : !ok ? (r.status === 'running' ? 'Espera a que termine la corrida' : 'Una corrida con error no tiene .cft de salida') : `Partir del .cft que dejó ${runLabel(r)}`;
  $('segbase').setAttribute('aria-pressed', String(!$('fromrun').checked));
  $('segrun').setAttribute('aria-pressed', String($('fromrun').checked));
}
$('segbase').onclick = () => setFrom(false);
$('segrun').onclick = () => setFrom(true);
$('fromrun').onchange = () => { renderSeg(); renderParams(); applyExtDefault(); };

function describeEdits(e) {
  const names = Object.fromEntries(PARAMS.map(p => [p.key, `${p.label}${p.unit && !p.label.includes(p.unit) ? ' ' + p.unit : ''}`]));
  return Object.entries(e).filter(([k]) => k !== 'AutoUpdate' && k !== 'ext_outlet').map(([k, v]) => `${names[k] || k} = ${v}`).join(', ') + (e.ext_outlet === false ? ' (sin extensión CFD)' : '');
}
function sourceProject() {
  if (fromRun() && st.run?.run_dir) return `${st.run.run_dir}\\${st.run.name}_out.cft`;
  return st.project;
}
const exportsSel = () => [$('exCCM').checked && 'StarCCM', $('exSTL').checked && 'OpenFOAM'].filter(Boolean);
async function runNow() {
  if ($('runbtn').disabled) return;
  const e = edits(), ex = exportsSel();
  const body = { project: sourceProject(), edits: e, name: $('rname').value.trim() || defaultName(), exports: ex, save: true };
  $('runbtn').disabled = true; $('runbtn').textContent = 'Lanzando CFturbo…'; runMsg('');
  try {
    await api('/api/run', body);
  } catch (err) {
    runMsg(err.status === 409 ? `CFturbo está ocupado (${String(err.message).replace(/^CFturbo trabajando \((.*)\)$/, '$1')}). Espera a que termine.` : err.status === 404 ? `No encuentro el proyecto de origen: ${err.message}` : `No pude lanzar la corrida: ${err.message}`, 'err');
    $('runbtn').disabled = false; $('runbtn').textContent = '▶ Ejecutar en CFturbo'; return;
  }
  st.lastName = body.name; st.runStart = Date.now(); st.status.running = true;
  runMsg(`«${body.name}»: ${describeEdits(e) || 'sin cambios (solo exportar)'}`, '', 20000);
  st.pinned = false; $('rname').value = '';
  for (const i of paramInputs()) i.value = '';  // evita reenviar cambios viejos sin querer
  if (e.AutoUpdate) { $('autoupd').checked = false; toast('AutoUpdate desactivado tras usarlo (márcalo de nuevo si lo necesitas)', 'warn'); }
  onEdit(); tickClock(); pollNow();
}
$('runbtn').onclick = runNow;
// «Pedir a Claude»: el mismo pedido que Ejecutar (origen, cambios, opciones y exportes), pero con criterio
$('askbtn').onclick = () => {
  const e = edits(), ex = exportsSel(), np = Object.keys(paramEdits()).length;
  const origen = fromRun() ? `la corrida ${runLabel(st.run)} (project = "${sourceProject()}")` : `el proyecto base ${st.project}`;
  const opts = [e.AutoUpdate && 'AutoUpdate=True', e.ext_outlet === false && 'ext_outlet=False', `exports=${JSON.stringify(ex)}`].filter(Boolean).join(', ');
  const txt = np
    ? `Partiendo de ${origen}, aplica ${describeEdits(e)}; opciones: ${opts}. Revisa con criterio de turbomáquinas si los demás parámetros deben acompañar el cambio, corre cft_run (name "${$('rname').value.trim() || defaultName()}") y dame pedido vs realizado, avisos y archivos.`
    : `Revisa ${origen} con criterio de turbomáquinas y propón una mejora concreta; córrela con cft_run partiendo de ese origen (opciones: ${opts}) y explícame qué cambió.`;
  askClaude(txt);
};

// ---------------------------------------------------------------- proyecto base
async function loadProjects() {
  try { st.projects = await api('/api/projects'); }
  catch (e) { $('pinfo').textContent = `No pude listar los proyectos: ${e.message}`; $('pinfo').style.color = 'var(--err)'; return; }
  const sel = $('project');
  if (!st.projects.length) {
    sel.innerHTML = '<option value="">Sin proyectos en projects/</option>'; sel.disabled = true;
    $('pinfo').textContent = 'Crea la bomba base en la GUI de CFturbo y guárdala en projects/<nombre>/<nombre>.cft'; return;
  }
  sel.disabled = false;
  sel.innerHTML = st.projects.map(p => `<option value="${esc(p.name)}">${esc(p.name)}</option>`).join('');
  st.project = st.projects[0].name; await loadInfo();
}
async function loadInfo() {
  if (!st.project) return;
  $('pinfo').className = 'mono mut'; $('pinfo').textContent = 'Leyendo proyecto…';
  try { st.info = await api('/api/project/' + encodeURIComponent(st.project)); }
  catch (e) { $('pinfo').className = 'mono'; $('pinfo').style.color = 'var(--err)'; $('pinfo').textContent = `No pude leer el proyecto: ${e.message}`; return; }
  $('pinfo').style.color = '';
  const dp = st.info.design_point || {};
  $('pinfo').textContent = `${st.info.project_type} · ${(st.info.components || []).map(c => c.caption.replace(/[[\]]/g, '').replace(/_\d+$/, '')).join(' + ')} · ${dp.fluid || ''}`;
  $('pnq').textContent = st.info.nq ? `nq ${fmt(st.info.nq.nq)} · ${st.info.nq.tipo}` : '';
  renderParams(); applyExtDefault();
}
$('project').onchange = e => { st.project = e.target.value; loadInfo(); };

// ---------------------------------------------------------------- sondeo con reconexión
// UNA petición (/api/poll) cada 3 s, con tiempo límite (AbortController) y nunca dos a la vez.
// Si falla: banda roja con cuenta atrás real y reintentos a 4 → 8 → 16 → 30 s (≤ 4 errores de red en 40 s).
const BACKOFF = [4, 8, 16, 30];
let pollT = 0, pollBusy = false;
function schedule(s) { clearTimeout(pollT); pollT = setTimeout(poll, s * 1000); }
function pollNow() { clearTimeout(pollT); poll(); }
async function poll() {
  if (pollBusy) return; pollBusy = true;
  try {
    const j = await api('/api/poll?limit=40', undefined, 8000);
    if (!st.online) goOnline();
    st.status = j.status; $('keepn').textContent = j.status.keep_tmp ?? 8;
    onRuns(j.runs); renderStatus();
    schedule(3);
  } catch {
    st.failures++; goOffline();
  } finally { pollBusy = false; }
}
function goOffline() {
  st.online = false;
  const s = BACKOFF[Math.min(st.failures - 1, BACKOFF.length - 1)];
  st.retryAt = Date.now() + s * 1000;
  $('offline').hidden = false; renderOffline();
  $('status').innerHTML = '<span class="dot off"></span><span>Sin conexión</span>';
  schedule(s);
}
function renderOffline() {
  if (st.online) return;
  const s = Math.max(0, Math.ceil((st.retryAt - Date.now()) / 1000));
  $('offlinetxt').textContent = s ? `Sin conexión con el servidor local. Reintento en ${s} s.` : 'Sin conexión con el servidor local. Reintentando…';
}
function goOnline() {
  const was = st.failures > 0; st.online = true; st.failures = 0; $('offline').hidden = true;
  if (was && !st.projects.length) loadProjects();
  if (was) toast('Conexión recuperada', 'ok');
}
$('retry').onclick = pollNow;

// Corrida en marcha: nombre y segundos. Prioridad: fila «running» del sondeo > candado (running_since) > esta pestaña.
function runningNow() {
  const s = st.status, row = st.runs.find(r => r.status === 'running');
  if (row) return { name: row.name, t: elapsed(row.started) };
  if (!s.running) return null;
  return { name: s.running_name || st.lastName || '', t: s.running_since ? elapsed(s.running_since) : Math.round((Date.now() - (st.runStart || Date.now())) / 1000) };
}
function renderStatus() {
  if (!st.online) return;
  const s = st.status, cur = runningNow();
  const nv = st.runs.filter(r => r.saved).length, nt = st.runs.length - nv;
  const txt = cur ? `CFturbo trabajando · ${cur.name} · ${cur.t} s` : `Listo · ${plural(nt, 'corrida')} · ${nv} versi${nv === 1 ? 'ón' : 'ones'}`;
  const chat = s.chatting || st.chatting;
  $('status').innerHTML = `<span class="dot ${cur ? 'busy' : 'ok'}"></span><span>${esc(txt)}</span>` + (chat ? ' <span class="dot chat"></span><span>Claude trabajando</span>' : '');
  $('runbtn').disabled = !!cur;
  $('runbtn').textContent = cur ? `Corriendo ${cur.name}… ${cur.t} s` : '▶ Ejecutar en CFturbo';
  $('runbtn').title = cur ? 'Una corrida de CFturbo a la vez (una licencia)' : 'Ctrl+Enter';
  $('runbar').classList.toggle('busy', !!(cur || st.selecting));
  renderFoot();
}

function onRuns(runs) {
  notifyFinished(runs);
  st.prevStatus = new Map(runs.map(r => [r.id, r.status]));
  st.runs = runs;
  if (st.runB && !runs.some(r => r.id === st.runB.id)) clearB();
  autoSelect(runs);
  st.known = new Set(runs.map(r => r.id));
  if (!runs.length && st.run) { st.run = null; renderActive(); loadGeometry(null); }
  renderGallery();
}
// toast + mensaje del pie cuando una corrida pasa de «running» a otro estado
function notifyFinished(runs) {
  for (const r of runs) {
    if (st.prevStatus.get(r.id) !== 'running' || r.status === 'running') continue;
    const nw = (r.warnings || []).length;
    const msg = r.status === 'ok' ? `${r.name} terminó: OK` : r.status === 'warn' ? `${r.name} terminó con ${plural(nw, 'aviso')}` : `${r.name} falló: ${(r.errors || [''])[0]}`;
    const kind = r.status === 'error' ? 'err' : r.status === 'warn' ? 'warn' : 'ok';
    toast(msg, kind === 'err' ? 'error' : kind);
    runMsg(msg, kind, 8000);
    if (r.status === 'error' && r.edits?.AutoUpdate && $('autoupd').checked) { $('autoupd').checked = false; onEdit(); }
  }
}
// selección automática: salta a una corrida NUEVA salvo que el usuario haya fijado otra (entonces solo avisa).
// Al abrir la página se elige la última con geometría para que el visor no arranque vacío.
function autoSelect(runs) {
  const cur = st.run && runs.find(r => r.id === st.run.id), first = !st.known;
  const fresh = first ? null : runs.find(r => !st.known.has(r.id) && !r.saved);  // guardar una versión no cuenta
  if (fresh && st.pinned) toast(`Nueva corrida: ${fresh.name} (sigues viendo ${runLabel(st.run)})`);
  if (first && runs.length && !st.run) { st.pinned = false; selectRun((runs.find(r => r.n_stl > 0 && r.status !== 'running') || runs[0]).id); }
  else if (st.run && !cur && runs.length) selectRun(runs[0].id);       // la activa se podó
  else if (fresh && !st.pinned) selectRun(fresh.id);
  else if (!st.run && runs.length && !first && !st.selErr) selectRun(runs[0].id);
  else if (cur && (cur.status !== st.run.status || cur.saved !== st.run.saved || cur.saved_as_version !== st.run.saved_as_version)) selectRun(cur.id);
  else if (cur && cur.thumb !== st.run.thumb) st.run.thumb = cur.thumb;
}

// ---------------------------------------------------------------- galería
const FILTERS = { all: () => true, saved: r => r.saved, tmp: r => !r.saved, warn: r => r.status === 'warn', error: r => r.status === 'error' };
let gallerySig = '';
function thumbHtml(r) {
  if (r.status === 'running') return `<div class="thumb loading" data-started="${esc(r.started)}">Corriendo… ${elapsed(r.started)} s</div>`;
  if (r.status === 'error') return `<div class="thumb err">✕<br>Sin geometría</div>`;
  if (r.thumb) return `<div class="thumb"><img alt="" loading="lazy" src="/files/${encodeURIComponent(r.id)}/thumb.png?v=${r.thumb}"></div>`;
  if (r.n_stl === 0) return `<div class="thumb"><span><span class="ini">${esc(runLabel(r).slice(0, 3))}</span><br>Sin STL para el visor</span></div>`;
  return `<div class="thumb"><span>Sin miniatura<br>se crea al abrirla</span></div>`;
}
function cardHtml(r, focusId) {
  const d = r.info?.dims || {}, a = st.run?.id === r.id, b = st.runB?.id === r.id, nw = (r.warnings || []).length;
  return `<div class="card-run${b ? ' is-b' : ''}${versionExists(r.saved_as_version) ? ' dim' : ''}" role="option" tabindex="${r.id === focusId ? 0 : -1}" aria-selected="${a}" data-id="${esc(r.id)}" title="${esc(runLabel(r))} · ${esc(fdate(r.started || ''))} · clic: ver · Ctrl+clic: comparar como B">
    ${thumbHtml(r)}${r.saved ? '<span class="ribbon" aria-hidden="true">★</span>' : ''}
    ${a ? '<span class="ab">A</span>' : b ? '<span class="ab b">B</span>' : `<button class="cmpbtn" tabindex="-1" title="Comparar con la activa (Ctrl+clic)" aria-label="Comparar ${esc(runLabel(r))} con la activa">⇄</button>`}
    <div class="meta"><span class="name">${esc(runLabel(r))}</span>
      <span class="sub"><span>${esc(fdate(r.started || ''))}</span><span>d2 ${fmt(d.d2_mm)}</span><span>z ${d.nBl ?? '–'}</span></span>
      <span class="row">${tag(r)}${savedTag(r)}${nw ? `<span class="chipw" title="${plural(nw, 'aviso')}">⚠ ${nw}</span>` : ''}</span>
      ${r.status === 'error' && r.errors?.length ? `<span class="errline" title="${esc(r.errors[0])}">${esc(r.errors[0])}</span>` : ''}
    </div></div>`;
}
function renderFilterCounts() {
  for (const el of $('gfilters').querySelectorAll('[data-n]')) el.textContent = st.runs.filter(FILTERS[el.dataset.n]).length;
  const nv = st.runs.filter(r => r.saved).length;
  $('gcount').textContent = `(${st.runs.length})${nv ? ' · ' + nv + ' ★' : ''}`;
}
function renderGallery(force) {
  const list = st.runs.filter(FILTERS[st.filter]);
  const sig = JSON.stringify([st.filter, st.compact, st.run?.id, st.runB?.id, list.map(r => [r.id, r.status, r.thumb, r.saved, versionExists(r.saved_as_version)])]);
  renderFilterCounts();
  if (sig === gallerySig && !force) return;
  gallerySig = sig;
  const g = $('gallery'), focused = document.activeElement?.closest?.('.card-run')?.dataset.id;
  g.classList.toggle('compact', st.compact);
  if (!st.runs.length) { g.innerHTML = `<div class="gallery-empty">Aún no hay corridas. Cambia un parámetro y pulsa «Ejecutar en CFturbo», o pídeselo a Claude en el chat.</div>`; return; }
  if (!list.length) { g.innerHTML = `<div class="gallery-empty">Ninguna corrida con este filtro. <a href="#" id="gall">Ver todas</a></div>`; $('gall').onclick = ev => { ev.preventDefault(); setFilter('all'); }; return; }
  // roving tabindex: una sola tarjeta enfocable (la que tenía el foco, si no la activa, si no la primera)
  const focusId = [focused, st.run?.id].find(id => id && list.some(r => r.id === id)) || list[0].id;
  g.innerHTML = list.map(r => cardHtml(r, focusId)).join('');
  for (const c of g.querySelectorAll('.card-run')) {
    c.onclick = ev => { if (ev.target.closest('.cmpbtn') || ev.ctrlKey || ev.metaKey) setB(c.dataset.id); else pick(c.dataset.id); };
  }
  if (focused) g.querySelector(`.card-run[data-id="${CSS.escape(focused)}"]`)?.focus();
}
function pick(id) { st.pinned = true; if (st.runB?.id === id) clearB(); selectRun(id); }
$('gallery').addEventListener('keydown', ev => {
  const c = ev.target.closest('.card-run'); if (!c) return;
  if (ev.key === 'Enter') { ev.preventDefault(); ev.ctrlKey || ev.metaKey ? setB(c.dataset.id) : pick(c.dataset.id); }
  else if (['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'].includes(ev.key)) {
    ev.preventDefault(); const all = [...$('gallery').querySelectorAll('.card-run')], i = all.indexOf(c);
    const j = ev.key === 'Home' ? 0 : ev.key === 'End' ? all.length - 1 : Math.max(0, Math.min(all.length - 1, i + (ev.key === 'ArrowRight' || ev.key === 'ArrowDown' ? 1 : -1)));
    c.tabIndex = -1; all[j].tabIndex = 0; all[j].focus();
  }
});
function setFilter(f) {
  st.filter = f; for (const b of $('gfilters').querySelectorAll('[data-f]')) b.setAttribute('aria-pressed', String(b.dataset.f === f));
  renderGallery(true);
}
for (const b of $('gfilters').querySelectorAll('[data-f]')) b.onclick = () => setFilter(b.dataset.f);
// densidad (P2-3): tarjetas con miniatura grande o lista compacta; se recuerda
function setDensity(compact) {
  st.compact = compact; LS.set('cft_density', compact ? 'list' : null);
  $('density').setAttribute('aria-pressed', String(compact)); $('density').textContent = compact ? 'Tarjetas' : 'Lista';
  $('density').title = compact ? 'Ver como tarjetas con miniatura' : 'Ver como lista compacta';
  renderGallery(true);
}
$('density').onclick = () => setDensity(!st.compact);

// ---------------------------------------------------------------- corrida activa (A)
let selectSeq = 0;
async function selectRun(id) {
  const seq = ++selectSeq;
  const changing = st.run?.id !== id;
  if (changing) { st.selecting = true; $('runbar').classList.add('busy'); $('vmsg').textContent = 'Cargando corrida…'; }
  let r;
  try { r = await api('/api/runs/' + encodeURIComponent(id), undefined, 10000); }
  catch (e) {
    if (seq !== selectSeq) return;
    st.selecting = false; st.selErr = id; renderStatus();
    const row = st.runs.find(x => x.id === id);
    $('selerrtxt').textContent = `No pude abrir la corrida ${row ? runLabel(row) : id}: ${e.name === 'AbortError' ? 'el servidor tardó demasiado' : e.message}`;
    $('selerr').hidden = false; $('selretry').onclick = () => selectRun(id);
    toast(`No pude abrir la corrida ${row ? runLabel(row) : id}`, 'error');
    if (st.run) $('vmsg').textContent = `${runLabel(st.run)} (sigue la anterior)`;
    renderGallery(true);  // la tarjeta vuelve a marcar la que de verdad está activa
    return;
  }
  if (seq !== selectSeq) return;  // llegó otra selección mientras tanto
  st.selecting = false; st.selErr = null; $('selerr').hidden = true;
  const row = st.runs.find(x => x.id === id) || {};
  r.thumb = row.thumb || 0; r.saved = row.saved ?? r.saved;
  if (!versionExists(r.saved_as_version)) r.saved_as_version = row.saved_as_version ?? null;
  st.run = r;
  renderActive();
  if (changing && fromRun()) applyExtDefault();
  const key = r.id + '|' + r.status;
  if (key !== st.loadedKey) { st.loadedKey = key; loadGeometry(r); }
  if (st.runB) renderCompare();
  renderStatus();
}
function renderActive() {
  renderGallery(); renderSeg(); renderParams();
  renderRunbar(); renderEvents(); renderFiles(); renderSaveBtn();
}
function renderRunbar() {
  const r = st.run;
  $('runtitle').textContent = r ? runLabel(r) : 'Ninguna corrida seleccionada';
  $('runtitle').title = r ? `${runLabel(r)}\n${r.run_dir || ''}` : '';
  $('runtag').innerHTML = r ? tag(r) + savedTag(r, true) : '';
  renderRunMeta();
  const fc = $('followchip'); fc.hidden = !r;
  fc.innerHTML = st.pinned ? 'Fijada<span class="long"> · volver a la última</span>' : 'Siguiendo<span class="long"> la última</span>';
  fc.setAttribute('aria-pressed', String(!st.pinned));
  fc.title = st.pinned ? 'La vista no salta a corridas nuevas. Clic para seguir la última.' : 'La vista salta sola a cada corrida nueva. Clic para fijar esta.';
  $('rethumb').disabled = !canThumb(r);
}
function renderRunMeta() {
  const r = st.run;
  $('runmeta').textContent = !r ? '' : r.status === 'running' ? `Corriendo · ${elapsed(r.started)} s` : `${fdate(r.started || '')}${r.seconds != null ? ' · ' + fmt(r.seconds) + ' s' : ''}`;
  $('runmeta').title = $('runmeta').textContent;
}
function renderEvents() {
  const r = st.run;
  const corr = Object.entries(r?.corrected || {}).map(([k, [a, b]]) => `<div class="msg fix">CFturbo corrigió ${esc(k)}: pedido ${esc(a)} → ${esc(b)}</div>`).join('');
  const uniq = a => [...new Set(a || [])];  // STAR-CCM+ y OpenFOAM repiten el mismo mensaje
  const guide = !r?.errors?.length ? '' : `<div class="msg fix"><b>Qué hacer:</b> ${r.edits?.AutoUpdate
      ? 'AutoUpdate recalculó d2/b2/dS y el meridiano quedó inválido. Prueba sin AutoUpdate (edita d2 y b2 a mano) o con un cambio menor del punto de diseño.'
      : 'revisa el primer error; prueba un cambio menor o parte de una corrida que funcionó.'} También puedes <a href="#" id="askfix">pedir a Claude que lo corrija</a>.</div>`;
  $('msgs').innerHTML = guide + uniq(r?.errors).map(m => `<div class="msg error">Error: ${esc(m)}</div>`).join('') + corr + uniq(r?.warnings).map(m => `<div class="msg warn">Aviso: ${esc(m)}</div>`).join('');
  if ($('askfix')) $('askfix').onclick = e => { e.preventDefault(); askClaude(`La corrida ${runLabel(r)} (${r.id}) terminó con error. Lee sus errores, busca receta y córrela de nuevo corregida (máximo 3 intentos).`); };
  $('events').innerHTML = r ? ((r.events || []).map(e => `<li><span>${esc(e.t.slice(11, 19))}</span>${esc(e.msg)}</li>`).join('') || '<li class="mut">Esta corrida no tiene hitos.</li>') : '<li class="mut">Esperando corrida…</li>';
  const ne = (r?.errors || []).length, nw = (r?.warnings || []).length, nc = Object.keys(r?.corrected || {}).length;
  $('bev').textContent = ne + nw ? ne + nw : ''; $('bev').className = 'badge' + (ne ? ' error' : nw ? ' warn' : '');
  const sum = [ne && plural(ne, 'error', 'errores'), nw && plural(nw, 'aviso'), nc && plural(nc, 'corrección', 'correcciones')].filter(Boolean).join(' · ');
  $('vsummary').textContent = sum ? sum + ' → ver' : '';
  $('vsummary').setAttribute('aria-label', sum ? sum + ', ver detalles' : '');
}
function renderFiles() {
  const r = st.run;
  const groups = Object.entries(r?.exports || {}).map(([itf, fs]) => [itf, fs.filter(f => !f.endsWith('.stl'))]).filter(([, fs]) => fs.length);
  const nstl = (r?.exports?.OpenFOAM || []).length, nfiles = groups.reduce((a, [, fs]) => a + fs.length, 0);
  const ITF = { StarCCM: 'STAR-CCM+', OpenFOAM: 'OpenFOAM', General: 'General' };
  $('files').innerHTML = groups.map(([itf, fs]) => `<li class="files-group">${ITF[itf] || esc(itf)}</li>` + fs.map(f => `<li><a href="/files/${encodeURIComponent(r.id)}/${encodeURIComponent(f)}" download>${esc(f)}</a></li>`).join('')).join('')
    + (nstl ? `<li class="mut">${nstl} STL para el visor</li>` : '') || `<li class="mut">${r ? 'Esta corrida no exportó archivos.' : '–'}</li>`;
  $('filesnote').textContent = r ? (r.run_dir || '') : '';
  $('bfiles').textContent = nfiles + nstl ? nfiles + nstl : '';
  $('openfolder').disabled = $('openfolder2').disabled = !r;
}
function renderSaveBtn() {
  const r = st.run, sb = $('savebtn');
  sb.disabled = !r || !!r.saved || r.status === 'running' || r.status === 'error';
  sb.textContent = r?.saved ? '★ Guardada' : '★ Guardar versión';
  sb.title = !r ? 'Selecciona una corrida' : r.saved ? 'Ya está en versions/' : r.status === 'running' ? 'Espera a que termine la corrida' : r.status === 'error' ? 'Una corrida con error no se puede guardar' : 'Copia la corrida a versions/ (no se borra)';
  if (sb.disabled) hideSaveInput();
}
$('followchip').onclick = () => { if (st.pinned) { st.pinned = false; if (st.runs[0]) selectRun(st.runs[0].id); } else { st.pinned = true; renderRunbar(); } };
const openFolder = () => st.run && api('/api/open', { run_id: st.run.id }).then(() => toast('Carpeta abierta en el Explorador', 'ok')).catch(e => toast('No pude abrir la carpeta: ' + e.message, 'error'));
$('openfolder').onclick = openFolder; $('openfolder2').onclick = openFolder;
$('vsummary').onclick = () => openTab('events');
$('vsummary').onkeydown = e => { if (e.key === 'Enter') openTab('events'); };

// Guardar versión: el primer clic abre el nombre en línea; Enter (o segundo clic) guarda, Esc cancela
function hideSaveInput() { $('savename').hidden = true; }
$('savebtn').onclick = () => {
  if (!st.run) return;
  if ($('savename').hidden) { $('savename').hidden = false; $('savename').value = st.run.name; $('savename').focus(); $('savename').select(); $('savebtn').textContent = '★ Guardar'; return; }
  saveVersion();
};
$('savename').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); saveVersion(); } else if (e.key === 'Escape') { e.stopPropagation(); hideSaveInput(); renderSaveBtn(); } });
async function saveVersion() {
  const name = $('savename').value.trim() || st.run.name;
  try {
    const j = await api('/api/save', { run_id: st.run.id, name });
    hideSaveInput(); toast(`Guardada en versions/${j.id}`, 'ok'); st.pinned = true;
    clearTimeout(pollT); await poll(); selectRun(j.id);
  } catch (e) {
    toast(e.status === 409 ? `Ya existe una versión «${name}». Elige otro nombre.` : `No pude guardar: ${e.message}`, 'error');
    $('savename').focus();
  }
}

// ---------------------------------------------------------------- comparación A/B
async function setB(id) {
  if (!st.run || id === st.run.id) { toast('Elige como B una corrida distinta de la activa', 'warn'); return; }
  try { st.runB = await api('/api/runs/' + encodeURIComponent(id), undefined, 10000); } catch (e) { toast('No pude leer la corrida B: ' + e.message, 'error'); return; }
  st.runB.saved = st.runs.find(x => x.id === id)?.saved;
  renderGallery(true); renderCompare(); openTab('cmp'); loadOverlay();
}
function clearB() { st.runB = null; renderGallery(true); renderCompare(); loadOverlay(); }
function setOverlay(on) { st.overlayB = on; LS.set('cft_overlay_b', on ? '1' : null); renderCompare(); loadOverlay(); }
function renderCompare() {
  const A = st.run, B = st.runB;
  $('bcmp').textContent = B ? 'A⇄B' : ''; $('qab').hidden = !B;
  renderOverlayToggle();
  if (!A || !B) { $('cmp').innerHTML = '<div class="cmp-empty">Elige una segunda corrida con Ctrl+clic (o el botón ⇄ de la tarjeta) para compararla con la activa.</div>'; return; }
  const rows = [...PARAMS.map(p => [`${p.sym}${p.unit ? ' ' + p.unit : ''}`, p.from(A.info), p.from(B.info), p.d, p.label]),
    ['nq', A.info?.nq?.nq, B.info?.nq?.nq, 1, 'Velocidad específica'], ['duración s', A.seconds, B.seconds, 1, 'Duración de la corrida'],
    ['avisos', (A.warnings || []).length, (B.warnings || []).length, 0, 'Número de avisos'], ['errores', (A.errors || []).length, (B.errors || []).length, 0, 'Número de errores']];
  const tr = rows.map(([lab, a, b, d, long]) => {
    const ok = a != null && b != null && !isNaN(+a) && !isNaN(+b), dl = ok ? b - a : null, pc = ok && Math.abs(a) > 1e-12 ? dl / Math.abs(a) * 100 : null;
    const cls = pc != null && Math.abs(pc) >= 1 ? (pc > 0 ? 'up' : 'down') : '';
    return `<tr title="${esc(long)}"><td>${esc(lab)}</td><td class="num">${fmt(a, d)}</td><td class="num">${fmt(b, d)}</td><td class="num ${cls}">${dl == null ? '–' : (dl > 0 ? '+' : '') + fmt(dl, d)}</td><td class="num ${cls}">${pc == null ? '–' : (pc > 0 ? '+' : '') + fmt(pc, 1) + ' %'}</td></tr>`;
  }).join('') + `<tr><td>estado</td><td class="num">${tag(A)}</td><td class="num">${tag(B)}</td><td></td><td></td></tr>`;
  const wa = new Set(A.warnings || []), wb = new Set(B.warnings || []);
  const grp = (title, arr) => `<div class="cmp-sec">${title} (${arr.length})</div>` + (arr.map(w => `<div class="msg warn">${esc(w)}</div>`).join('') || '<div class="mut small">—</div>');
  $('cmp').innerHTML = `<div class="cmp-head"><span class="a">A ${esc(runLabel(A))}</span>${tag(A)}<span>⇄</span><span class="b">B ${esc(runLabel(B))}</span>${tag(B)}<span class="sp"></span>
      <button class="chip" id="cmpov" aria-pressed="${st.overlayB}" title="Dibuja B en alambre cian sobre A en el visor">Superponer B</button>
      <button class="sm" id="cmpswap" title="B pasa a ser la activa (se ve en el visor)">Intercambiar</button><button class="sm" id="cmpclear" title="Esc">Quitar B</button><button class="sm pri" id="cmpask">Pedir comparación a Claude</button></div>
    <div class="tblwrap"><table id="cmptbl"><thead><tr><th>Parámetro</th><th class="num">A</th><th class="num">B</th><th class="num">Δ</th><th class="num">Δ %</th></tr></thead><tbody>${tr}</tbody></table></div>
    ${grp('Avisos solo en A', [...wa].filter(w => !wb.has(w)))}${grp('Avisos solo en B', [...wb].filter(w => !wa.has(w)))}${grp('Avisos en ambas', [...wa].filter(w => wb.has(w)))}`;
  $('cmpov').onclick = () => setOverlay(!st.overlayB);
  $('cmpswap').onclick = () => { const b = st.runB; st.runB = st.run; st.pinned = true; selectRun(b.id).then(loadOverlay); };
  $('cmpclear').onclick = clearB;
  $('cmpask').onclick = askCompare;
}
const askCompare = () => st.run && st.runB && askClaude(`Compara las corridas A (${st.run.id}) y B (${st.runB.id}): parámetros, avisos y qué cambió en la geometría. Dime cuál conviene y por qué.`);
$('qab').onclick = askCompare;

// ---------------------------------------------------------------- dock con pestañas
function openTab(t, expand = true) {
  st.tab = t; LS.set('cft_tab', t);
  for (const b of document.querySelectorAll('.dock-tabs [role=tab]')) { const on = b.dataset.tab === t; b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; }
  for (const id of ['chat', 'tab-events', 'tab-files', 'tab-cmp']) $(id).hidden = id !== (t === 'chat' ? 'chat' : 'tab-' + t);
  if (expand) setCollapsed(false);
}
function setCollapsed(c) {
  $('stage').classList.toggle('dock-collapsed', c); LS.set('cft_dock_collapsed', c ? '1' : null);
  $('docktoggle').setAttribute('aria-label', c ? 'Desplegar panel' : 'Plegar panel');
}
for (const b of document.querySelectorAll('.dock-tabs [role=tab]')) {
  b.onclick = () => openTab(b.dataset.tab);
  b.onkeydown = e => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const tabs = [...document.querySelectorAll('.dock-tabs [role=tab]')], i = tabs.indexOf(b), n = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    n.focus(); openTab(n.dataset.tab);
  };
}
$('docktoggle').onclick = () => setCollapsed(!$('stage').classList.contains('dock-collapsed'));
// alto del dock arrastrando su borde (160 px – 60 vh), guardado
(() => {
  const h = +LS.get('cft_dock_h', 0); if (h) $('stage').style.setProperty('--dock-h', h + 'px');
  let y0 = 0, h0 = 0;
  const move = e => { const h = Math.max(160, Math.min(innerHeight * .6, h0 + y0 - e.clientY)); $('stage').style.setProperty('--dock-h', h + 'px'); };
  const up = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', up); LS.set('cft_dock_h', String(Math.round($('dock').getBoundingClientRect().height))); };
  $('dockresize').addEventListener('pointerdown', e => { e.preventDefault(); setCollapsed(false); y0 = e.clientY; h0 = $('dock').getBoundingClientRect().height; addEventListener('pointermove', move); addEventListener('pointerup', up); });
})();

// ---------------------------------------------------------------- chat con Claude Code (SSE)
// Chat vacío: ayuda centrada con los botones rápidos dentro; con mensajes, los botones van al pie.
function placeQuick() {
  const empty = !$('chatlog').querySelector('.m');
  $('chatempty').hidden = !empty;
  if (empty) $('chatempty').appendChild($('quick')); else $('chatin').before($('quick'));
}
function addMsg(cls, html) {
  const d = document.createElement('div'); d.className = 'm ' + cls; d.innerHTML = html; $('chatlog').appendChild(d);
  placeQuick(); $('chatlog').scrollTop = 1e9; return d;
}
function md(s) {  // markdown mínimo: tablas, negrita, código, títulos, viñetas y ---
  const lines = esc(s).split('\n'); let out = [], i = 0;
  while (i < lines.length) {
    if (/^\s*\|.*\|\s*$/.test(lines[i]) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {
      const rows = []; while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
      const cells = r => r.trim().slice(1, -1).split('|').map(c => c.trim());
      out.push('<table><tr>' + cells(rows[0]).map(c => `<th>${c}</th>`).join('') + '</tr>' + rows.slice(2).map(r => '<tr>' + cells(r).map(c => `<td>${c}</td>`).join('') + '</tr>').join('') + '</table>');
    } else if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(lines[i])) { out.push('<hr>'); i++; }
    else out.push(lines[i++].replace(/^#{1,4}\s+(.*)$/, '<b>$1</b>').replace(/^(\s*)[-*]\s+/, '$1• '));
  }
  return out.join('\n').replace(/\\([_*`#\-.!()[\]])/g, '$1').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n(?=<table|<hr>)/g, '').replace(/(<\/table>|<hr>)\n/g, '$1');
}
function toolSummary(name, inp = {}) {
  const bits = [inp.name, inp.project && String(inp.project).split(/[\\/]/).pop(), inp.edits && `${Object.keys(inp.edits).length} cambios`, inp.query && `«${inp.query}»`, inp.run_id].filter(Boolean);
  return [name, ...bits].join(' · ');
}
function loginCard() {
  const d = addMsg('err', 'La CLI de Claude Code no tiene sesión. En una terminal ejecuta: <code>claude auth login</code><div class="actions"><button class="sm">Copiar comando</button></div>');
  d.querySelector('button').onclick = async e => { try { await navigator.clipboard.writeText('claude auth login'); e.target.textContent = 'Copiado'; } catch { e.target.textContent = 'Cópialo a mano'; } };
}
function setChatting(on) {
  st.chatting = on; $('send').disabled = on; $('stopchat').disabled = !on; $('chatdot').hidden = !on; renderStatus();
}
function askClaude(text) { openTab('chat'); $('chattext').value = text; sendChat(); }
// un evento SSE del chat -> la página
function onChatEvent(ev, ctx) {
  // sesión guardada que la CLI ya no conoce (borrada, o creada desde otra carpeta): se reintenta sin --resume
  if (['result', 'error'].includes(ev.kind) && /No conversation found/i.test(ev.text || '')) { ctx.stale = true; return; }
  if (ev.kind === 'result' && ev.turns === 0 && ev.subtype !== 'success' && !ev.text) return;  // lo explica el «error» que sigue
  if (ev.kind === 'init') { st.session = ev.session_id; LS.set('cft_session', st.session); $('chatstate').textContent = `sesión ${st.session.slice(0, 8)} · ${ev.model || ''}`; }
  else if (ev.kind === 'text') { addMsg('bot', md(ev.text)); ctx.tool = ''; $('chatstate').textContent = 'pensando…'; }
  else if (ev.kind === 'tool') {
    addMsg('tool', `<details><summary>Tool: ${esc(toolSummary(ev.name, ev.input || {}))}</summary>${esc(JSON.stringify(ev.input || {}, null, 1)).slice(0, 1500)}</details>`);
    ctx.tool = ev.name; ctx.t0 = Date.now(); $('chatstate').textContent = `ejecutando ${ev.name}…`;
    if (/cft_run|cft_save/.test(ev.name)) { st.pinned = false; schedule(1); }
  }
  else if (ev.kind === 'tool_result') { if (ev.is_error) addMsg('tool bad', 'Error de tool: ' + esc(ev.text)); }
  else if (ev.kind === 'status') { $('chatstate').textContent = ev.text; }
  else if (ev.kind === 'ping') { if (!ctx.tool) $('chatstate').textContent = `trabajando… ${ev.t} s`; }
  else if (ev.kind === 'error') addMsg('err', /conversación en curso/.test(ev.text) ? 'Ya hay una conversación en curso. Espera o pulsa Detener.' : esc(ev.text));
  else if (ev.kind === 'result') { ctx.tool = ''; if (ev.text) addMsg('err', esc(ev.text)); $('chatstate').textContent = `listo · ${ev.turns ?? '?'} turnos · ${ev.seconds} s`; }
  else if (ev.kind === 'stopped') { addMsg('bot mut', 'Detenido por el usuario.'); ctx.tool = ''; $('chatstate').textContent = 'detenido'; }
  else if (ev.kind === 'done') { ctx.done = true; if (ev.rc && ev.rc !== 0 && !/listo|detenido/.test($('chatstate').textContent)) $('chatstate').textContent = `terminó con código ${ev.rc}`; }
  if (!ctx.login && ['text', 'result', 'error'].includes(ev.kind) && /401|not logged in|OAuth|auth login/i.test(ev.text || '')) { ctx.login = true; loginCard(); }
}
async function sendChat(retry = false) {
  const text = $('chattext').value.trim(); if (!text || st.chatting) return;
  $('chattext').value = ''; st.lastMsg = text; if (!retry) addMsg('user', esc(text));
  setChatting(true); $('chatstate').textContent = 'pensando…';
  const ctx = { t0: Date.now(), tool: '', login: false, done: false };
  const clock = setInterval(() => { if (ctx.tool) $('chatstate').textContent = `ejecutando ${ctx.tool}… ${Math.round((Date.now() - ctx.t0) / 1000)} s`; }, 1000);
  try {
    const r = await fetch('/api/chat', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ message: text, session_id: st.session, project: st.project }) });
    if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = '';
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx; while ((idx = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2);
        if (!chunk.startsWith('data: ')) continue;
        let ev; try { ev = JSON.parse(chunk.slice(6)); } catch { continue; }
        onChatEvent(ev, ctx);
      }
    }
    if (!ctx.done && st.chatting) throw new Error('el flujo se cortó');
  } catch (e) {
    const d = addMsg('err', `Se cortó la conexión con el chat (${esc(String(e.message || e))}). Tu mensaje no se perdió:<div class="actions"><button class="sm">Reenviar</button></div>`);
    d.querySelector('button').onclick = () => { $('chattext').value = text; sendChat(); };
    $('chatstate').textContent = 'conexión perdida';
  }
  clearInterval(clock); setChatting(false); pollNow();
  if (ctx.stale && !retry) {  // la sesión guardada ya no existe: se empieza una nueva y se reenvía UNA vez
    st.session = null; LS.set('cft_session', null);
    addMsg('bot mut', 'La conversación anterior ya no existe; empiezo una nueva con tu mensaje.');
    $('chattext').value = text; sendChat(true);
  }
}
$('send').onclick = () => sendChat();
$('chattext').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  else if (e.key === 'ArrowUp' && !$('chattext').value && st.lastMsg) { e.preventDefault(); $('chattext').value = st.lastMsg; }
});
$('stopchat').onclick = () => { $('stopchat').disabled = true; $('chatstate').textContent = 'deteniendo…';
  api('/api/chat/stop', {}).then(j => { if (!j.stopped) $('chatstate').textContent = 'no había nada que detener'; }).catch(e => { $('chatstate').textContent = 'no pude detener: ' + e.message; }); };
let newchatT = 0;
$('newchat').onclick = () => {
  const b = $('newchat');
  if (!b.dataset.armed) { b.dataset.armed = '1'; b.textContent = '¿Seguro? Pulsa otra vez para borrar'; newchatT = setTimeout(() => { delete b.dataset.armed; b.textContent = 'Nueva conversación'; }, 4000); return; }
  clearTimeout(newchatT); delete b.dataset.armed; b.textContent = 'Nueva conversación';
  st.session = null; LS.set('cft_session', null);
  for (const m of $('chatlog').querySelectorAll('.m')) m.remove();
  placeQuick(); $('chatstate').textContent = 'nueva conversación';
};
for (const b of document.querySelectorAll('.quick button[data-q]')) b.onclick = () => askClaude(b.dataset.q);
st.session = LS.get('cft_session'); if (st.session) $('chatstate').textContent = `sesión ${st.session.slice(0, 8)} (continúa)`;

// ---------------------------------------------------------------- visor 3D
// Render bajo demanda (dirty) con rAF y respaldo a 30 fps por si la pestaña no anima;
// el canvas va en posición absoluta y la barra de piezas encima con z-index.
const V = $('viewer');
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true }); V.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const applyBg = () => { scene.background = new THREE.Color(cssVar('--viewer-bg') || '#0b1016'); render(); };
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100000);
const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true; controls.dampingFactor = .12;
let dirty = true, lastTick = 0;
const render = () => { dirty = true; };
controls.addEventListener('change', render);
controls.addEventListener('start', () => setViewPressed(null));  // el usuario orbita: ya no hay vista predefinida activa
function tick() { lastTick = performance.now(); if (controls.update()) dirty = true; if (dirty) { renderer.render(scene, camera); dirty = false; } }
(function raf() { requestAnimationFrame(raf); tick(); })();
setInterval(() => { if (performance.now() - lastTick > 40) tick(); }, 33);  // respaldo si el rAF no corre
scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 1.6));
const dl = new THREE.DirectionalLight(0xffffff, 1.8); dl.position.set(1, 1, 2); scene.add(dl);
const dl2 = new THREE.DirectionalLight(0xffffff, 0.8); dl2.position.set(-1, -2, -1); scene.add(dl2);
scene.add(new THREE.AxesHelper(50));
const group = new THREE.Group(); scene.add(group);
const groupB = new THREE.Group(); scene.add(groupB);  // B superpuesta en alambre (P2-1)
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
let lastW = 0, lastH = 0;
function resize() {
  const w = V.clientWidth, h = V.clientHeight;
  if (!w || !h || (w === lastW && h === lastH)) return;   // evita el bucle lienzo -> scrollbar -> lienzo
  lastW = w; lastH = h; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); render();
}
new ResizeObserver(resize).observe(V); resize(); applyBg();
const COLORS = { Stator: 0x7aa2f7, Impeller: 0xff9e64, Volute: 0x9ece6a, ext: 0x565f89 };
const colorFor = c => c.includes('ext') ? COLORS.ext : c.includes('Impeller') ? COLORS.Impeller : c.includes('Volute') ? COLORS.Volute : COLORS.Stator;
const isCap = g => /inflow|outflow/i.test(g.boundary || '');
const loader = new STLLoader();
const stlUrl = (r, g) => `/files/${encodeURIComponent(r.id)}/${encodeURIComponent(g.file)}`;
function vEmpty(html) { $('vempty').innerHTML = html; $('vempty').hidden = !html; const a = $('vempty').querySelector('a'); if (a) a.onclick = e => { e.preventDefault(); openTab('events'); }; }
let geoSeq = 0;
async function loadGeometry(r) {
  const seq = ++geoSeq;
  group.clear(); st.meshes.clear(); render();
  const geo = (r?.geometry || []).filter(g => g.kind === 'stl');
  if (!geo.length) {
    $('vtools').innerHTML = '';
    if (!r) { vEmpty('Sin geometría. Ejecuta una corrida con STL o elige una en la galería.'); $('vmsg').textContent = 'sin geometría'; }
    else if (r.status === 'running') { vEmpty('CFturbo trabajando… la geometría aparecerá al terminar'); $('vmsg').textContent = `${runLabel(r)} · corriendo`; }
    else if (r.status === 'error') { vEmpty('La corrida terminó con error; no hay geometría. <a href="#">Mira «Hitos y avisos».</a>'); $('vmsg').textContent = `${runLabel(r)} · error`; }
    else { vEmpty('Esta corrida no exportó STL. Vuelve a correrla con «Exportar STL» activado.'); $('vmsg').textContent = `${runLabel(r)} · sin STL`; }
    renderRunbar(); return;
  }
  vEmpty('');
  $('vmsg').textContent = `Cargando 0/${geo.length} superficies…`;
  const comps = [...new Set(geo.map(g => g.component))];
  $('vtools').innerHTML = comps.map(c => `<label><input type="checkbox" data-c="${esc(c)}" ${c.includes('ext') ? '' : 'checked'}><span style="color:#${colorFor(c).toString(16).padStart(6, '0')}">■</span>&nbsp;${esc(c)}</label>`).join('') +
    `<label><input type="checkbox" id="caps" ${st.showCaps ? 'checked' : ''}>Tapas in/out</label><span id="ovbwrap"></span>`;
  for (const cb of $('vtools').querySelectorAll('input[data-c]')) cb.onchange = applyVis;
  $('caps').onchange = e => { st.showCaps = e.target.checked; applyVis(); };
  renderOverlayToggle();
  let n = 0;
  await Promise.all(geo.map(g => new Promise(res => loader.load(stlUrl(r, g), bg => {
    if (seq !== geoSeq) return res();
    bg.computeVertexNormals();
    const m = new THREE.Mesh(bg, new THREE.MeshStandardMaterial({ color: colorFor(g.component), metalness: .1, roughness: .6, side: THREE.DoubleSide, transparent: !g.component.includes('Impeller'), opacity: g.component.includes('Impeller') ? 1 : .7 }));
    m.userData = g; group.add(m); st.meshes.set(g.file, m); n++; $('vmsg').textContent = `Cargando ${n}/${geo.length} superficies…`; render(); res();
  }, undefined, () => res()))));
  if (seq !== geoSeq) return;
  applyVis(); fit();
  $('vmsg').textContent = `${runLabel(r)} · ${comps.join(', ')}`;
  renderRunbar();
  captureThumb(r).catch(() => {});
}
function applyVis() {
  const on = new Set([...$('vtools').querySelectorAll('input[data-c]:checked')].map(i => i.dataset.c));
  for (const m of st.meshes.values()) m.visible = on.has(m.userData.component) && (st.showCaps || !isCap(m.userData));
  render();
}
// B en alambre cian semitransparente sobre A (sin extensiones ni tapas); el encuadre abarca las dos
let ovSeq = 0;
function renderOverlayToggle() {
  const w = $('ovbwrap'); if (!w) return;
  w.innerHTML = st.runB ? `<label title="Dibuja la corrida B en alambre cian"><input type="checkbox" id="ovb" ${st.overlayB ? 'checked' : ''}><span style="color:var(--cmp)">■</span>&nbsp;B en alambre</label>` : '';
  if ($('ovb')) $('ovb').onchange = e => setOverlay(e.target.checked);
}
async function loadOverlay() {
  const seq = ++ovSeq; groupB.clear(); render();
  const B = st.runB; if (!B || !st.overlayB) return;
  const geo = (B.geometry || []).filter(g => g.kind === 'stl' && !g.component.includes('ext') && !isCap(g));
  const mat = new THREE.MeshBasicMaterial({ color: new THREE.Color(cssVar('--cmp') || '#2dd4bf'), wireframe: true, transparent: true, opacity: .35, depthWrite: false });
  await Promise.all(geo.map(g => new Promise(res => loader.load(stlUrl(B, g), bg => { if (seq === ovSeq) groupB.add(new THREE.Mesh(bg, mat)); res(); }, undefined, () => res()))));
  if (seq === ovSeq) { fit(st.view || 'iso'); if (!geo.length) toast('La corrida B no tiene STL para superponer', 'warn'); }
}
// Vistas: iso = la de siempre; axial mira a lo largo de z (eje de la bomba en CFturbo); lateral con z horizontal.
// camera.up se deja en +y porque OrbitControls fija su orientación al crearse.
const VIEWS = { iso: [.6, -.8, .6], axial: [0, 0, 1.25], lateral: [1.25, 0, 0] };
function setViewPressed(v) {
  st.view = v;
  for (const b of document.querySelectorAll('#vactions [data-view]')) b.setAttribute('aria-pressed', String(b.dataset.view === v));
}
function fit(view = 'iso', pressed = true) {
  const box = new THREE.Box3();
  for (const m of st.meshes.values()) if (m.visible) box.expandByObject(m);
  for (const m of groupB.children) box.expandByObject(m);
  if (box.isEmpty()) return;
  const c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3()).length();
  controls.target.copy(c); camera.position.copy(c).add(new THREE.Vector3(...VIEWS[view]).multiplyScalar(s)); camera.near = s / 500; camera.far = s * 20; camera.updateProjectionMatrix();
  camera.lookAt(c); controls.update(); renderer.render(scene, camera);
  if (pressed) setViewPressed(view);
}
$('vfit').onclick = () => fit(st.view || 'iso');
renderer.domElement.tabIndex = 0; renderer.domElement.setAttribute('aria-label', 'Visor 3D: flechas para orbitar, + y - para zoom, F para encuadrar');
renderer.domElement.addEventListener('keydown', e => {
  const off = camera.position.clone().sub(controls.target), sph = new THREE.Spherical().setFromVector3(off), a = Math.PI / 18;
  if (e.key === 'ArrowLeft') sph.theta -= a; else if (e.key === 'ArrowRight') sph.theta += a;
  else if (e.key === 'ArrowUp') sph.phi = Math.max(.05, sph.phi - a); else if (e.key === 'ArrowDown') sph.phi = Math.min(Math.PI - .05, sph.phi + a);
  else if (e.key === '+' || e.key === '=') sph.radius *= .85; else if (e.key === '-') sph.radius /= .85; else return;
  e.preventDefault(); setViewPressed(null); camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(sph)); camera.lookAt(controls.target); controls.update(); render();
});
for (const b of document.querySelectorAll('#vactions [data-view]')) b.onclick = () => fit(b.dataset.view);

// ---------------------------------------------------------------- miniaturas 320×240
// Automática: una por corrida ok/aviso, vista iso y visibilidad por defecto (comparables entre sí).
// Recapturar (P2-2): la vista actual del visor, tal cual la ve el usuario.
const canThumb = r => !!r && st.meshes.size > 0 && ['ok', 'warn'].includes(r.status) && st.run?.id === r.id;
async function captureThumb(r, current = false) {
  const row = st.runs.find(x => x.id === r.id);
  if ((!current && (row ? row.thumb : r.thumb)) || !canThumb(r)) return false;
  const W = 320, H = 240, pr = renderer.getPixelRatio();
  const vis = [...st.meshes.values()].map(m => m.visible), ovVis = groupB.visible;
  const saved = { pos: camera.position.clone(), tgt: controls.target.clone() };
  if (!current) { for (const m of st.meshes.values()) m.visible = !m.userData.component.includes('ext') && !isCap(m.userData); groupB.visible = false; }
  renderer.setPixelRatio(1); renderer.setSize(W, H, false); camera.aspect = W / H; camera.updateProjectionMatrix();
  if (!current) fit('iso', false);
  renderer.render(scene, camera);
  const pending = new Promise(res => renderer.domElement.toBlob(res, 'image/png'));  // copia el lienzo ya
  // volver al tamaño del visor en el mismo tick: el usuario no llega a ver el lienzo de 320×240
  [...st.meshes.values()].forEach((m, i) => { m.visible = vis[i]; }); groupB.visible = ovVis;
  renderer.setPixelRatio(pr); lastW = lastH = 0; resize();
  camera.position.copy(saved.pos); controls.target.copy(saved.tgt); controls.update(); renderer.render(scene, camera);
  const blob = await pending;
  if (!blob) return false;
  const j = await fetch(`/api/runs/${encodeURIComponent(r.id)}/thumb`, { method: 'POST', headers: { 'content-type': 'image/png' }, body: blob });
  if (!j.ok) return false;
  const t = Math.floor(Date.now() / 1000); if (row) row.thumb = t; if (st.run?.id === r.id) st.run.thumb = t; renderGallery(true);
  return true;
}
$('rethumb').onclick = async () => {
  const ok = await captureThumb(st.run, true).catch(() => false);
  toast(ok ? 'Miniatura actualizada con la vista actual' : 'No pude guardar la miniatura', ok ? 'ok' : 'error');
};

// ---------------------------------------------------------------- tema
function setTheme(t) { if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme; LS.set('cft_theme', t); applyBg(); }
$('theme').onclick = () => setTheme((document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')) === 'dark' ? 'light' : 'dark');
matchMedia('(prefers-color-scheme: light)').addEventListener('change', applyBg);
// tema claro por defecto (petición del usuario); ◐ cambia a oscuro y la elección se guarda
setTheme(LS.get('cft_theme') || 'light');

// ---------------------------------------------------------------- atajos: popover «?» y teclado global
function setHelp(open) {
  $('help').hidden = !open; $('helpbtn').setAttribute('aria-expanded', String(open));
  if (open) $('helpclose').focus();
}
$('helpbtn').onclick = () => setHelp($('help').hidden);
$('helpclose').onclick = () => { setHelp(false); $('helpbtn').focus(); };
addEventListener('pointerdown', e => { if (!$('help').hidden && !e.target.closest('#help,#helpbtn')) setHelp(false); });
addEventListener('keydown', e => {
  const typing = e.target.closest?.('input,textarea,select,[contenteditable]');
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && e.target.id !== 'chattext' && !e.target.closest?.('.card-run')) { e.preventDefault(); runNow(); return; }
  if (e.key === 'Escape') {
    if (!$('help').hidden) { setHelp(false); $('helpbtn').focus(); }
    else if (!$('savename').hidden) { hideSaveInput(); renderSaveBtn(); }
    else if (st.runB) clearB();
    return;
  }
  if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === '?') setHelp($('help').hidden);
  else if (e.key === 'f' || e.key === 'F') fit(st.view || 'iso');
  else if (e.key === '1') fit('iso'); else if (e.key === '2') fit('axial'); else if (e.key === '3') fit('lateral');
  else if (e.key === '`') setCollapsed(!$('stage').classList.contains('dock-collapsed'));
});

// reloj de 1 s: contadores de «Corriendo… N s» y cuenta atrás del reintento sin esperar al sondeo
function tickClock() {
  renderOffline();
  if (st.online && (st.status.running || st.runs.some(r => r.status === 'running'))) {
    renderStatus(); renderRunMeta();
    for (const t of document.querySelectorAll('.thumb.loading[data-started]')) t.textContent = `Corriendo… ${elapsed(t.dataset.started)} s`;
  }
}
setInterval(tickClock, 1000);

// <1100 px el pie de Ejecutar es fijo: el body reserva su alto real para no tapar el dock
new ResizeObserver(([e]) => document.body.style.setProperty('--foot-h', Math.ceil(e.target.getBoundingClientRect().height) + 12 + 'px')).observe(document.querySelector('.props-foot'));

// ---------------------------------------------------------------- arranque
openTab(['chat', 'events', 'files', 'cmp'].includes(st.tab) ? st.tab : 'chat', false);
setCollapsed(LS.get('cft_dock_collapsed') === '1');
// Opciones abiertas si hay alto (≥ 820 px) salvo que el usuario las haya plegado/abierto antes
$('opts').open = LS.get('cft_opts_open') != null ? LS.get('cft_opts_open') === '1' : innerHeight >= 820 && innerWidth >= 1100;
// solo la elección del usuario se recuerda (el evento toggle también salta al abrirlas por código)
$('optsum').addEventListener('click', () => setTimeout(() => LS.set('cft_opts_open', $('opts').open ? '1' : '0')));
setDensity(st.compact); placeQuick(); setViewPressed(null);
renderCompare(); renderActive(); applyExtDefault();
window.__cft = { st, group, groupB, camera, controls, scene, fit, renderer, captureThumb, selectRun, setB, clearB, setOverlay, poll };
loadProjects(); poll();
