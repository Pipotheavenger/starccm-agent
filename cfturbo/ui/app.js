// CFturbo · Controlador — lógica de la página (módulo ES, sin build). Ver agents/out/ux_1.md.
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
  online: true, failures: 0, lastMsg: '', loadedKey: '',
};
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (x, d = 1) => x == null || x === '' || isNaN(+x) ? '–' : (+x).toFixed(d).replace('.', ',');
const fmtIn = (x, d = 1) => x == null || x === '' || isNaN(+x) ? '' : (+x).toFixed(d);  // placeholders con punto
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const fdate = iso => { const d = new Date(iso); return isNaN(d) ? '' : `${d.getDate()} ${MESES[d.getMonth()]} ${iso.slice(11, 16)}`; };
const elapsed = iso => Math.max(0, Math.round((Date.now() - new Date(iso)) / 1000));
const TAG = { running: 'Corriendo', ok: 'OK', warn: 'Con avisos', error: 'Error' };
const tag = r => `<span class="tag ${esc(r?.status)}">${TAG[r?.status] || esc(r?.status || '')}</span>`;
const savedTag = r => r?.saved ? '<span class="tag saved">★ Guardada</span>' : r?.saved_as_version ? `<span class="tag saved" title="Esta temporal ya está en versions/${esc(r.saved_as_version)}">★ como ${esc(r.saved_as_version)}</span>` : '';
const runLabel = r => r ? (r.saved ? r.id : r.name) : '';
const api = async (url, body) => {
  const r = await fetch(url, body === undefined ? undefined : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) { let d = r.status; try { d = (await r.json()).detail || d; } catch {} const e = new Error(d); e.status = r.status; throw e; }
  return r.json();
};

// ---------------------------------------------------------------- avisos flotantes
let toastT = 0;
function toast(text, kind = '') {
  const t = $('toast'); t.className = kind; t.textContent = text;
  clearTimeout(toastT); toastT = setTimeout(() => { t.textContent = ''; }, 6000);
}

// ---------------------------------------------------------------- parámetros
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
function renderParams() {
  const base = st.info, run = st.run?.info, src = fromRun() ? run : base;
  $('runcol').textContent = st.run ? runLabel(st.run) : 'Corrida'; $('runcol').title = st.run ? runLabel(st.run) : '';
  const tb = $('params').querySelector('tbody');
  const prev = Object.fromEntries([...tb.querySelectorAll('input')].map(i => [i.dataset.k, i.value]));
  tb.innerHTML = PARAMS.map(p => {
    const b = p.from(base), r = p.from(run);
    const changed = b != null && r != null && Math.abs(b - r) > 1e-9;
    return `<tr title="${p.label}${p.unit ? ' (' + p.unit + ')' : ''}"><td><b>${p.sym}</b> <span class="mut">${p.unit}</span></td><td class="num">${fmt(b, p.d)}</td><td class="num${changed ? ' changed' : ''}">${fmt(r, p.d)}</td><td><input data-k="${p.key}" type="number" step="any" aria-label="${p.label} nuevo" value="${esc(prev[p.key] ?? '')}" placeholder="${fmtIn(p.from(src) ?? b, p.d)}"></td></tr>`;
  }).join('') + `<tr title="Velocidad específica nq"><td><b>nq</b></td><td class="num">${fmt(base?.nq?.nq)}</td><td class="num">${fmt(run?.nq?.nq)}</td><td class="num" id="nqcell"></td></tr>`;
  for (const i of tb.querySelectorAll('input')) i.addEventListener('input', onEdit);
  onEdit();
}
function edits() {
  const e = {};
  for (const i of $('params').querySelectorAll('input')) if (i.value !== '') e[i.dataset.k] = +i.value;
  if ($('autoupd').checked) e.AutoUpdate = true;
  if ($('extoff').checked) e.ext_outlet = false;
  return e;
}
function onEdit() {
  for (const i of $('params').querySelectorAll('input')) i.closest('tr').classList.toggle('edited', i.value !== '');
  nqNew(); renderFoot();
}
function nqNew() {
  const e = edits(), src = fromRun() && st.run?.info ? st.run.info : st.info;
  const Q = e.Q_m3h ?? src?.design_point?.Q_m3h, H = e.H_m ?? src?.design_point?.H_m, n = e.n_rpm ?? src?.design_point?.n_rpm;
  if (!(Q > 0 && H > 0 && n > 0)) { $('nqnew').textContent = '–'; $('nqtipo').textContent = ''; return; }
  const v = n * Math.sqrt(Q / 3600) / Math.pow(H, .75);
  const tipo = v < 10 ? 'radial muy lenta' : v < 30 ? 'radial lenta' : v < 50 ? 'radial normal' : v < 80 ? 'radial rápida / semiaxial' : v < 160 ? 'flujo mixto' : 'axial';
  $('nqnew').textContent = fmt(v); $('nqtipo').textContent = tipo; const c = $('nqcell'); if (c) c.textContent = fmt(v);
}
const nParamEdits = () => [...$('params').querySelectorAll('input')].filter(i => i.value !== '').length;
function renderFoot() {
  const n = nParamEdits();
  $('clear').disabled = !n;
  const nopt = ['autoupd', 'extoff'].filter(id => $(id).checked).length + ['exCCM', 'exSTL'].filter(id => $(id).checked).length;
  $('optsum').textContent = `Opciones · ${nopt} activas`;
  if (!st.status.running && !(+$('runmsg').dataset.keep > Date.now()))  // keep = hasta cuándo no pisar el mensaje
    $('runmsg').textContent = n ? `${n} cambio${n > 1 ? 's' : ''} · desde ${fromRun() ? 'la corrida ' + runLabel(st.run) : 'la base'}` : `Sin cambios: solo exporta${fromRun() ? ' (desde ' + runLabel(st.run) + ')' : ''}`;
  $('rname').placeholder = defaultName();
}
$('clear').onclick = () => { for (const i of $('params').querySelectorAll('input')) i.value = ''; onEdit(); };
for (const id of ['autoupd', 'extoff', 'exCCM', 'exSTL']) $(id).onchange = onEdit;

// «Partir de»: control segmentado; la casilla oculta #fromrun sigue siendo la fuente de verdad
function setFrom(run) { $('fromrun').checked = run; renderSeg(); renderParams(); }
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
$('fromrun').onchange = () => { renderSeg(); renderParams(); };

function describeEdits(e) {
  const names = Object.fromEntries(PARAMS.map(p => [p.key, `${p.label}${p.unit ? ' ' + p.unit : ''}`]));
  return Object.entries(e).filter(([k]) => k !== 'AutoUpdate' && k !== 'ext_outlet').map(([k, v]) => `${names[k] || k} = ${v}`).join(', ') + (e.ext_outlet === false ? ' (sin extensión CFD)' : '');
}
function sourceProject() {
  if (fromRun() && st.run?.run_dir) return `${st.run.run_dir}\\${st.run.name}_out.cft`;
  return st.project;
}
async function runNow() {
  if ($('runbtn').disabled) return;
  const e = edits(), ex = [$('exCCM').checked && 'StarCCM', $('exSTL').checked && 'OpenFOAM'].filter(Boolean);
  const body = { project: sourceProject(), edits: e, name: $('rname').value.trim() || defaultName(), exports: ex, save: true };
  $('runbtn').disabled = true; $('runbtn').textContent = 'Lanzando CFturbo…'; $('runmsg').className = '';
  try {
    await api('/api/run', body);
  } catch (err) {
    $('runmsg').className = 'err';
    $('runmsg').textContent = err.status === 409 ? 'Ya hay una corrida en marcha. Espera a que termine.' : err.status === 404 ? `No encuentro el proyecto de origen: ${err.message}` : `No pude lanzar la corrida: ${err.message}`;
    $('runbtn').disabled = false; $('runbtn').textContent = '▶ Ejecutar en CFturbo'; return;
  }
  st.lastName = body.name; st.runStart = Date.now(); st.status.running = true;
  $('runmsg').dataset.keep = Date.now() + 20000;
  $('runmsg').textContent = `«${body.name}»: ${describeEdits(e) || 'sin cambios (solo exportar)'}`;
  st.pinned = false; $('rname').value = '';
  for (const i of $('params').querySelectorAll('input')) i.value = '';  // evita reenviar cambios viejos sin querer
  onEdit(); tickClock(); clearTimeout(pollT); poll();
}
$('runbtn').onclick = runNow;
$('askbtn').onclick = () => {
  const e = edits(); const txt = Object.keys(e).filter(k => k !== 'ext_outlet').length
    ? `Partiendo de ${fromRun() ? 'la corrida ' + runLabel(st.run) : 'el proyecto base'}, aplica ${describeEdits(e)}${e.AutoUpdate ? ' con AutoUpdate' : ''}, revisa con criterio de turbomáquinas si los demás parámetros deben acompañar el cambio, corre cft_run (name "${$('rname').value || defaultName()}") y dame pedido vs realizado, avisos y archivos.`
    : `Revisa el proyecto base con criterio de turbomáquinas y propón una mejora concreta; córrela con cft_run y explícame qué cambió.`;
  askClaude(txt);
};

// ---------------------------------------------------------------- proyecto base
async function loadProjects() {
  st.projects = await api('/api/projects');
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
  renderParams();
}
$('project').onchange = e => { st.project = e.target.value; loadInfo(); };

// ---------------------------------------------------------------- sondeo con reconexión
// Cada 3 s; si el servidor no responde: banda roja y reintentos a 3 → 6 → 12 → 30 s con UNA sola petición
// (así la consola no se llena de ERR_CONNECTION_REFUSED).
const BACKOFF = [3, 6, 12, 30];
let pollT = 0, pollBusy = false;
function schedule(s) { clearTimeout(pollT); pollT = setTimeout(poll, s * 1000); }
async function poll() {
  if (pollBusy) return; pollBusy = true;
  try {
    if (!st.online) { await api('/api/status'); goOnline(); }
    const [runs, status] = await Promise.all([api('/api/runs?limit=40&fields=summary'), api('/api/status')]);
    st.status = status; onRuns(runs); renderStatus();
    schedule(3);
  } catch {
    st.failures++; goOffline();
  } finally { pollBusy = false; }
}
function goOffline() {
  st.online = false;
  const s = BACKOFF[Math.min(st.failures - 1, BACKOFF.length - 1)];
  $('offline').hidden = false; $('offlinetxt').textContent = `Sin conexión con el servidor local. Reintento en ${s} s.`;
  $('status').innerHTML = '<span class="dot off"></span><span>Sin conexión</span>';
  schedule(s);
}
function goOnline() {
  const was = st.failures > 0; st.online = true; st.failures = 0; $('offline').hidden = true;
  if (was && !st.projects.length) loadProjects().catch(() => {});
  if (was) toast('Conexión recuperada', 'ok');
}
$('retry').onclick = () => { clearTimeout(pollT); poll(); };

function renderStatus() {
  const s = st.status, running = st.runs.find(r => r.status === 'running');
  const nv = st.runs.filter(r => r.saved).length, nt = st.runs.length - nv;
  let txt = s.running ? `CFturbo trabajando · ${running ? running.name + ' · ' + elapsed(running.started) + ' s' : s.running_name || st.lastName || ''}` : `Listo · ${nt} corrida${nt === 1 ? '' : 's'} · ${nv} versi${nv === 1 ? 'ón' : 'ones'}`;
  const chat = s.chatting || st.chatting;
  $('status').innerHTML = `<span class="dot ${s.running ? 'busy' : 'ok'}"></span><span>${esc(txt)}</span>` + (chat ? ' <span class="dot chat"></span><span>Claude trabajando</span>' : '');
  // botón Ejecutar
  if (s.running) {
    const name = running?.name || s.running_name || st.lastName || '';
    const t = running ? elapsed(running.started) : Math.round((Date.now() - (st.runStart || Date.now())) / 1000);
    $('runbtn').disabled = true; $('runbtn').textContent = `Corriendo ${name}… ${t} s`;
  } else {
    $('runbtn').disabled = false; $('runbtn').textContent = '▶ Ejecutar en CFturbo';
  }
  $('runbar').classList.toggle('busy', !!s.running);
  renderFoot();
}

function onRuns(runs) {
  // toasts al terminar una corrida
  for (const r of runs) {
    const prev = st.prevStatus.get(r.id);
    if (prev === 'running' && r.status !== 'running') {
      const msg = r.status === 'ok' ? `${r.name} terminó: OK` : r.status === 'warn' ? `${r.name} terminó con ${(r.warnings || []).length} aviso${(r.warnings || []).length === 1 ? '' : 's'}` : `${r.name} falló: ${(r.errors || [''])[0]}`;
      toast(msg, r.status === 'error' ? 'error' : r.status === 'warn' ? 'warn' : 'ok');
      $('runmsg').className = r.status === 'error' ? 'err' : 'ok'; $('runmsg').textContent = msg; $('runmsg').dataset.keep = Date.now() + 6000;
      setTimeout(() => { $('runmsg').className = ''; renderFoot(); }, 6000);
    }
  }
  st.prevStatus = new Map(runs.map(r => [r.id, r.status]));
  st.runs = runs;
  if (st.runB && !runs.some(r => r.id === st.runB.id)) clearB();
  // selección automática: salta a una corrida NUEVA salvo que el usuario haya fijado otra (entonces solo avisa).
  // Al abrir la página se elige la última con geometría para que el visor no arranque vacío.
  // «nueva» = corrida temporal que no estaba en el sondeo anterior (guardar una versión no cuenta)
  const cur = st.run && runs.find(r => r.id === st.run.id), first = !st.known;
  const fresh = first ? null : runs.find(r => !st.known.has(r.id) && !r.saved);
  if (fresh && st.pinned) toast(`Nueva corrida: ${fresh.name} (sigues viendo ${runLabel(st.run)})`);
  if (first && runs.length && !st.run) {
    const g = runs.find(r => r.n_stl > 0 && r.status !== 'running') || runs[0];
    st.pinned = false; selectRun(g.id);
  } else if (st.run && !cur && runs.length) selectRun(runs[0].id);       // la activa se podó
  else if (fresh && !st.pinned) selectRun(fresh.id);
  else if (!st.run && runs.length && !first) selectRun(runs[0].id);
  else if (cur && (cur.status !== st.run.status || cur.saved !== st.run.saved || cur.saved_as_version !== st.run.saved_as_version)) selectRun(cur.id);
  else if (cur && cur.thumb !== st.run.thumb) st.run.thumb = cur.thumb;
  st.known = new Set(runs.map(r => r.id));
  if (!runs.length && st.run) { st.run = null; renderActive(); loadGeometry(null); }
  renderGallery();
}

// ---------------------------------------------------------------- galería
const FILTERS = { all: () => true, saved: r => r.saved, tmp: r => !r.saved, warn: r => r.status === 'warn' || (r.warnings || []).length > 0 };
let gallerySig = '';
function thumbHtml(r) {
  if (r.status === 'running') return `<div class="thumb loading" data-started="${esc(r.started)}">Corriendo… ${elapsed(r.started)} s</div>`;
  if (r.status === 'error') return `<div class="thumb err">✕<br>Sin geometría</div>`;
  if (r.thumb) return `<div class="thumb"><img alt="" loading="lazy" src="/files/${encodeURIComponent(r.id)}/thumb.png?v=${r.thumb}"></div>`;
  if (r.n_stl === 0) return `<div class="thumb"><span><span class="ini">${esc(runLabel(r).slice(0, 3))}</span><br>Sin STL para el visor</span></div>`;
  return `<div class="thumb"><span>Sin miniatura<br>ábrela para generarla</span></div>`;
}
function renderGallery(force) {
  const list = st.runs.filter(FILTERS[st.filter]);
  const sig = JSON.stringify([st.filter, st.run?.id, st.runB?.id, list.map(r => [r.id, r.status, r.thumb, r.saved])]);
  const nv = st.runs.filter(r => r.saved).length;
  $('gcount').textContent = `(${st.runs.length})${nv ? ' · ' + nv + ' ★' : ''}`;
  if (sig === gallerySig && !force) return;
  gallerySig = sig;
  const g = $('gallery'), focused = document.activeElement?.closest?.('.card-run')?.dataset.id;
  if (!st.runs.length) { g.innerHTML = `<div class="gallery-empty">Aún no hay corridas. Cambia un parámetro y pulsa «Ejecutar en CFturbo», o pídeselo a Claude en el chat.</div>`; return; }
  if (!list.length) { g.innerHTML = `<div class="gallery-empty">Ninguna corrida con este filtro. <a href="#" id="gall">Ver todas</a></div>`; $('gall').onclick = ev => { ev.preventDefault(); setFilter('all'); }; return; }
  g.innerHTML = list.map(r => {
    const d = r.info?.dims || {}, a = st.run?.id === r.id, b = st.runB?.id === r.id, nw = (r.warnings || []).length;
    return `<div class="card-run${b ? ' is-b' : ''}${r.saved_as_version ? ' dim' : ''}" role="option" tabindex="0" aria-selected="${a}" data-id="${esc(r.id)}" title="${esc(runLabel(r))} · clic: ver · Ctrl+clic: comparar como B">
      ${thumbHtml(r)}${r.saved ? '<span class="ribbon" aria-hidden="true">★</span>' : ''}
      ${a ? '<span class="ab">A</span>' : b ? '<span class="ab b">B</span>' : `<button class="cmpbtn" tabindex="-1" title="Comparar con la activa (B)" aria-label="Comparar ${esc(runLabel(r))} con la activa">⇄</button>`}
      <div class="meta"><span class="name">${esc(runLabel(r))}</span>
        <span class="sub"><span>${esc(fdate(r.started || ''))}</span><span>d2 ${fmt(d.d2_mm)}</span><span>z ${d.nBl ?? '–'}</span></span>
        <span class="row">${tag(r)}${savedTag(r)}${nw ? `<span class="chipw" title="${nw} avisos">⚠ ${nw}</span>` : ''}</span>
        ${r.status === 'error' && r.errors?.length ? `<span class="errline">${esc(r.errors[0])}</span>` : ''}
      </div></div>`;
  }).join('');
  for (const c of g.querySelectorAll('.card-run')) {
    c.onclick = ev => { if (ev.target.closest('.cmpbtn') || ev.ctrlKey || ev.metaKey) setB(c.dataset.id); else pick(c.dataset.id); };
  }
  if (focused) g.querySelector(`.card-run[data-id="${CSS.escape(focused)}"]`)?.focus();
}
function pick(id) { st.pinned = true; if (st.runB?.id === id) clearB(); selectRun(id); }
$('gallery').addEventListener('keydown', ev => {
  const c = ev.target.closest('.card-run'); if (!c) return;
  if (ev.key === 'Enter') { ev.preventDefault(); ev.ctrlKey || ev.metaKey ? setB(c.dataset.id) : pick(c.dataset.id); }
  else if (['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp'].includes(ev.key)) {
    ev.preventDefault(); const all = [...$('gallery').querySelectorAll('.card-run')], i = all.indexOf(c);
    all[Math.max(0, Math.min(all.length - 1, i + (ev.key === 'ArrowRight' || ev.key === 'ArrowDown' ? 1 : -1)))]?.focus();
  }
});
function setFilter(f) {
  st.filter = f; for (const b of $('gfilters').querySelectorAll('[data-f]')) b.setAttribute('aria-pressed', String(b.dataset.f === f));
  renderGallery(true);
}
for (const b of $('gfilters').querySelectorAll('[data-f]')) b.onclick = () => setFilter(b.dataset.f);

// ---------------------------------------------------------------- corrida activa (A)
let selectSeq = 0;
async function selectRun(id) {
  const seq = ++selectSeq;
  let r; try { r = await api('/api/runs/' + encodeURIComponent(id)); } catch { return; }
  if (seq !== selectSeq) return;  // llegó otra selección mientras tanto
  const row = st.runs.find(x => x.id === id) || {};
  r.thumb = row.thumb || 0; r.saved = row.saved ?? r.saved;
  st.run = r;
  renderActive();
  const key = r.id + '|' + r.status;
  if (key !== st.loadedKey) { st.loadedKey = key; loadGeometry(r); }
  if (st.runB) renderCompare();
}
function renderActive() {
  const r = st.run;
  renderGallery(); renderSeg(); renderParams();
  $('runtitle').textContent = r ? runLabel(r) : 'Ninguna corrida seleccionada';
  $('runtitle').title = r?.run_dir || '';
  $('runtag').innerHTML = r ? tag(r) + savedTag(r) : '';
  renderRunMeta();
  const fc = $('followchip'); fc.hidden = !r;
  fc.textContent = st.pinned ? 'Fijada · volver a la última' : 'Siguiendo la última';
  fc.setAttribute('aria-pressed', String(!st.pinned));
  fc.title = st.pinned ? 'La vista no salta a corridas nuevas. Clic para seguir la última.' : 'La vista salta sola a cada corrida nueva. Clic para fijar esta.';
  // hitos y avisos
  const corr = Object.entries(r?.corrected || {}).map(([k, [a, b]]) => `<div class="msg fix">CFturbo corrigió ${esc(k)}: pedido ${esc(a)} → ${esc(b)}</div>`).join('');
  const uniq = a => [...new Set(a || [])];  // STAR-CCM+ y OpenFOAM repiten el mismo mensaje
  const guide = !r?.errors?.length ? '' : `<div class="msg fix"><b>Qué hacer:</b> ${r.edits?.AutoUpdate
      ? 'AutoUpdate recalculó d2/b2/dS y el meridiano quedó inválido. Prueba sin AutoUpdate (edita d2 y b2 a mano) o con un cambio menor del punto de diseño.'
      : 'revisa el primer error; prueba un cambio menor o parte de una corrida que funcionó.'} También puedes <a href="#" id="askfix">pedir a Claude que lo corrija</a>.</div>`;
  $('msgs').innerHTML = guide + uniq(r?.errors).map(m => `<div class="msg error">Error: ${esc(m)}</div>`).join('') + corr + uniq(r?.warnings).map(m => `<div class="msg warn">Aviso: ${esc(m)}</div>`).join('');
  if ($('askfix')) $('askfix').onclick = e => { e.preventDefault(); askClaude(`La corrida ${runLabel(r)} (${r.id}) terminó con error. Lee sus errores, busca receta y córrela de nuevo corregida (máximo 3 intentos).`); };
  $('events').innerHTML = r ? ((r.events || []).map(e => `<li><span>${esc(e.t.slice(11, 19))}</span>${esc(e.msg)}</li>`).join('') || '<li class="mut">Esta corrida no tiene hitos.</li>') : '<li class="mut">Esperando corrida…</li>';
  const ne = (r?.errors || []).length, nw = (r?.warnings || []).length;
  $('bev').textContent = ne + nw ? ne + nw : ''; $('bev').className = 'badge' + (ne ? ' error' : nw ? ' warn' : '');
  const nc = Object.keys(r?.corrected || {}).length;
  $('vsummary').textContent = ne + nw + nc ? [ne && `${ne} error${ne > 1 ? 'es' : ''}`, nw && `${nw} aviso${nw > 1 ? 's' : ''}`, nc && `${nc} corrección${nc > 1 ? 'es' : ''}`].filter(Boolean).join(' · ') + ' → ver' : '';
  // archivos
  const groups = Object.entries(r?.exports || {}).map(([itf, fs]) => [itf, fs.filter(f => !f.endsWith('.stl'))]).filter(([, fs]) => fs.length);
  const nstl = (r?.exports?.OpenFOAM || []).length, nfiles = groups.reduce((a, [, fs]) => a + fs.length, 0);
  const ITF = { StarCCM: 'STAR-CCM+', OpenFOAM: 'OpenFOAM', General: 'General' };
  $('files').innerHTML = groups.map(([itf, fs]) => `<li class="files-group">${ITF[itf] || esc(itf)}</li>` + fs.map(f => `<li><a href="/files/${encodeURIComponent(r.id)}/${encodeURIComponent(f)}" download>${esc(f)}</a></li>`).join('')).join('')
    + (nstl ? `<li class="mut">${nstl} STL para el visor</li>` : '') || `<li class="mut">${r ? 'Esta corrida no exportó archivos.' : '–'}</li>`;
  $('filesnote').textContent = r ? (r.run_dir || '') : '';
  $('bfiles').textContent = nfiles + nstl ? nfiles + nstl : '';
  $('openfolder').disabled = $('openfolder2').disabled = !r;
  // guardar versión
  const sb = $('savebtn');
  sb.disabled = !r || !!r.saved || r.status === 'running' || r.status === 'error';
  sb.textContent = r?.saved ? '★ Guardada' : '★ Guardar versión';
  sb.title = !r ? 'Selecciona una corrida' : r.saved ? 'Ya está en versions/' : r.status === 'running' ? 'Espera a que termine la corrida' : r.status === 'error' ? 'Una corrida con error no se puede guardar' : 'Copia la corrida a versions/ (no se borra)';
  if (sb.disabled) hideSaveInput();
}
function renderRunMeta() {
  const r = st.run;
  $('runmeta').textContent = !r ? '' : r.status === 'running' ? `Corriendo · ${elapsed(r.started)} s` : `${fdate(r.started || '')}${r.seconds != null ? ' · ' + fmt(r.seconds) + ' s' : ''}`;
}
$('followchip').onclick = () => { if (st.pinned) { st.pinned = false; if (st.runs[0]) selectRun(st.runs[0].id); } else { st.pinned = true; renderActive(); } };
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
$('savename').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); saveVersion(); } else if (e.key === 'Escape') { e.stopPropagation(); hideSaveInput(); renderActive(); } });
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
  try { st.runB = await api('/api/runs/' + encodeURIComponent(id)); } catch (e) { toast('No pude leer la corrida B: ' + e.message, 'error'); return; }
  st.runB.saved = st.runs.find(x => x.id === id)?.saved;
  renderGallery(true); renderCompare(); openTab('cmp');
}
function clearB() { st.runB = null; renderGallery(true); renderCompare(); }
function renderCompare() {
  const A = st.run, B = st.runB;
  $('bcmp').textContent = B ? 'A⇄B' : ''; $('qab').hidden = !B;
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
      <button class="sm" id="cmpswap" title="B pasa a ser la activa (se ve en el visor)">Intercambiar</button><button class="sm" id="cmpclear" title="Esc">Quitar B</button><button class="sm pri" id="cmpask">Pedir comparación a Claude</button></div>
    <div class="tblwrap"><table id="cmptbl"><thead><tr><th>Parámetro</th><th class="num">A</th><th class="num">B</th><th class="num">Δ</th><th class="num">Δ %</th></tr></thead><tbody>${tr}</tbody></table></div>
    ${grp('Avisos solo en A', [...wa].filter(w => !wb.has(w)))}${grp('Avisos solo en B', [...wb].filter(w => !wa.has(w)))}${grp('Avisos en ambas', [...wa].filter(w => wb.has(w)))}`;
  $('cmpswap').onclick = () => { const b = st.runB; st.runB = st.run; st.pinned = true; selectRun(b.id); };
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
function addMsg(cls, html) { const d = document.createElement('div'); d.className = 'm ' + cls; d.innerHTML = html; $('chatlog').appendChild(d); $('chatlog').scrollTop = 1e9; return d; }
function md(s) {  // markdown mínimo: tablas, negrita, código
  const lines = esc(s).split('\n'); let out = [], i = 0;
  while (i < lines.length) {
    if (/^\s*\|.*\|\s*$/.test(lines[i]) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {
      const rows = []; while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
      const cells = r => r.trim().slice(1, -1).split('|').map(c => c.trim());
      out.push('<table><tr>' + cells(rows[0]).map(c => `<th>${c}</th>`).join('') + '</tr>' + rows.slice(2).map(r => '<tr>' + cells(r).map(c => `<td>${c}</td>`).join('') + '</tr>').join('') + '</table>');
    } else out.push(lines[i++].replace(/^#{1,4}\s+(.*)$/, '<b>$1</b>').replace(/^(\s*)[-*]\s+/, '$1• '));  // títulos y viñetas
  }
  return out.join('\n').replace(/\\([_*`#\-.!()[\]])/g, '$1').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\n(?=<table)/g, '').replace(/(<\/table>)\n/g, '$1');
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
async function sendChat() {
  const text = $('chattext').value.trim(); if (!text || st.chatting) return;
  $('chattext').value = ''; st.lastMsg = text; addMsg('user', esc(text));
  setChatting(true); $('chatstate').textContent = 'pensando…';
  let t0 = Date.now(), tool = '', loginShown = false, gotDone = false;
  const clock = setInterval(() => { if (tool) $('chatstate').textContent = `ejecutando ${tool}… ${Math.round((Date.now() - t0) / 1000)} s`; }, 1000);
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
        if (ev.kind === 'init') { st.session = ev.session_id; LS.set('cft_session', st.session); $('chatstate').textContent = `sesión ${st.session.slice(0, 8)} · ${ev.model || ''}`; }
        else if (ev.kind === 'text') { addMsg('bot', md(ev.text)); tool = ''; $('chatstate').textContent = 'pensando…'; }
        else if (ev.kind === 'tool') {
          const d = addMsg('tool', `<details><summary>Tool: ${esc(toolSummary(ev.name, ev.input || {}))}</summary>${esc(JSON.stringify(ev.input || {}, null, 1)).slice(0, 1500)}</details>`);
          tool = ev.name; t0 = Date.now(); $('chatstate').textContent = `ejecutando ${ev.name}…`;
          if (/cft_run|cft_save/.test(ev.name)) { st.pinned = false; clearTimeout(pollT); schedule(1); }
          void d;
        }
        else if (ev.kind === 'tool_result') { if (ev.is_error) addMsg('tool bad', 'Error de tool: ' + esc(ev.text)); }
        else if (ev.kind === 'status') { $('chatstate').textContent = ev.text; }
        else if (ev.kind === 'ping') { if (!tool) $('chatstate').textContent = `trabajando… ${ev.t} s`; }
        else if (ev.kind === 'error') {
          if (/conversación en curso/.test(ev.text)) addMsg('err', 'Ya hay una conversación en curso. Espera o pulsa Detener.');
          else addMsg('err', esc(ev.text));
        }
        else if (ev.kind === 'result') { tool = ''; if (ev.text) addMsg('err', esc(ev.text)); $('chatstate').textContent = `listo · ${ev.turns ?? '?'} turnos · ${ev.seconds} s`; }
        else if (ev.kind === 'stopped') { addMsg('bot mut', 'Detenido por el usuario.'); tool = ''; $('chatstate').textContent = 'detenido'; }
        else if (ev.kind === 'done') { gotDone = true; if (ev.rc && ev.rc !== 0 && !/listo|detenido/.test($('chatstate').textContent)) $('chatstate').textContent = `terminó con código ${ev.rc}`; }
        if (!loginShown && ['text', 'result', 'error'].includes(ev.kind) && /401|not logged in|OAuth|auth login/i.test(ev.text || '')) { loginShown = true; loginCard(); }
      }
    }
    if (!gotDone && st.chatting) throw new Error('el flujo se cortó');
  } catch (e) {
    const d = addMsg('err', `Se cortó la conexión con el chat (${esc(String(e.message || e))}). Tu mensaje no se perdió:<div class="actions"><button class="sm">Reenviar</button></div>`);
    d.querySelector('button').onclick = () => { $('chattext').value = text; sendChat(); };
    $('chatstate').textContent = 'conexión perdida';
  }
  clearInterval(clock); setChatting(false); clearTimeout(pollT); poll();
}
$('send').onclick = sendChat;
$('chattext').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  else if (e.key === 'ArrowUp' && !$('chattext').value && st.lastMsg) { e.preventDefault(); $('chattext').value = st.lastMsg; }
});
$('stopchat').onclick = () => { $('stopchat').disabled = true; $('chatstate').textContent = 'deteniendo…';
  api('/api/chat/stop', {}).then(j => { if (!j.stopped) $('chatstate').textContent = 'no había nada que detener'; }).catch(() => {}); };
let newchatT = 0;
$('newchat').onclick = () => {
  const b = $('newchat');
  if (!b.dataset.armed) { b.dataset.armed = '1'; b.textContent = '¿Seguro? Pulsa otra vez para borrar'; newchatT = setTimeout(() => { delete b.dataset.armed; b.textContent = 'Nueva conversación'; }, 4000); return; }
  clearTimeout(newchatT); delete b.dataset.armed; b.textContent = 'Nueva conversación';
  st.session = null; LS.set('cft_session', null); $('chatlog').innerHTML = ''; $('chatstate').textContent = 'nueva conversación';
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
function tick() { lastTick = performance.now(); if (controls.update()) dirty = true; if (dirty) { renderer.render(scene, camera); dirty = false; } }
(function raf() { requestAnimationFrame(raf); tick(); })();
setInterval(() => { if (performance.now() - lastTick > 40) tick(); }, 33);  // respaldo si el rAF no corre
scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 1.6));
const dl = new THREE.DirectionalLight(0xffffff, 1.8); dl.position.set(1, 1, 2); scene.add(dl);
const dl2 = new THREE.DirectionalLight(0xffffff, 0.8); dl2.position.set(-1, -2, -1); scene.add(dl2);
scene.add(new THREE.AxesHelper(50));
const group = new THREE.Group(); scene.add(group);
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
const loader = new STLLoader();
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
    return;
  }
  vEmpty('');
  $('vmsg').textContent = `Cargando 0/${geo.length} superficies…`;
  const comps = [...new Set(geo.map(g => g.component))];
  $('vtools').innerHTML = comps.map(c => `<label><input type="checkbox" data-c="${esc(c)}" ${c.includes('ext') ? '' : 'checked'}><span style="color:#${colorFor(c).toString(16).padStart(6, '0')}">■</span>&nbsp;${esc(c)}</label>`).join('') +
    `<label><input type="checkbox" id="caps" ${st.showCaps ? 'checked' : ''}>Tapas in/out</label>`;
  for (const cb of $('vtools').querySelectorAll('input[data-c]')) cb.onchange = applyVis;
  $('caps').onchange = e => { st.showCaps = e.target.checked; applyVis(); };
  let n = 0;
  await Promise.all(geo.map(g => new Promise(res => loader.load(`/files/${encodeURIComponent(r.id)}/${encodeURIComponent(g.file)}`, bg => {
    if (seq !== geoSeq) return res();
    bg.computeVertexNormals();
    const m = new THREE.Mesh(bg, new THREE.MeshStandardMaterial({ color: colorFor(g.component), metalness: .1, roughness: .6, side: THREE.DoubleSide, transparent: !g.component.includes('Impeller'), opacity: g.component.includes('Impeller') ? 1 : .7 }));
    m.userData = g; group.add(m); st.meshes.set(g.file, m); n++; $('vmsg').textContent = `Cargando ${n}/${geo.length} superficies…`; render(); res();
  }, undefined, () => res()))));
  if (seq !== geoSeq) return;
  applyVis(); fit();
  $('vmsg').textContent = `${runLabel(r)} · ${comps.join(', ')} · arrastra para orbitar, rueda para zoom, F para encuadrar`;
  captureThumb(r).catch(() => {});
}
function applyVis() {
  const on = new Set([...$('vtools').querySelectorAll('input[data-c]:checked')].map(i => i.dataset.c));
  for (const m of st.meshes.values()) { const b = (m.userData.boundary || '').toLowerCase(); m.visible = on.has(m.userData.component) && (st.showCaps || !(b.includes('inflow') || b.includes('outflow'))); }
  render();
}
// Vistas: iso = la de siempre; axial mira a lo largo de z (eje de la bomba en CFturbo); lateral con z horizontal.
// camera.up se deja en +y porque OrbitControls fija su orientación al crearse.
const VIEWS = { iso: [.6, -.8, .6], axial: [0, 0, 1.25], lateral: [1.25, 0, 0] };
function fit(view = 'iso') {
  const box = new THREE.Box3(); for (const m of st.meshes.values()) if (m.visible) box.expandByObject(m);
  if (box.isEmpty()) return;
  const c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3()).length();
  controls.target.copy(c); camera.position.copy(c).add(new THREE.Vector3(...VIEWS[view]).multiplyScalar(s)); camera.near = s / 500; camera.far = s * 20; camera.updateProjectionMatrix();
  camera.lookAt(c); controls.update(); renderer.render(scene, camera);
}
$('vfit').onclick = () => fit();
renderer.domElement.tabIndex = 0; renderer.domElement.setAttribute('aria-label', 'Visor 3D: flechas para orbitar, + y - para zoom, F para encuadrar');
renderer.domElement.addEventListener('keydown', e => {
  const off = camera.position.clone().sub(controls.target), sph = new THREE.Spherical().setFromVector3(off), a = Math.PI / 18;
  if (e.key === 'ArrowLeft') sph.theta -= a; else if (e.key === 'ArrowRight') sph.theta += a;
  else if (e.key === 'ArrowUp') sph.phi = Math.max(.05, sph.phi - a); else if (e.key === 'ArrowDown') sph.phi = Math.min(Math.PI - .05, sph.phi + a);
  else if (e.key === '+' || e.key === '=') sph.radius *= .85; else if (e.key === '-') sph.radius /= .85; else return;
  e.preventDefault(); camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(sph)); camera.lookAt(controls.target); controls.update(); render();
});
for (const b of document.querySelectorAll('#vactions [data-view]')) b.onclick = () => fit(b.dataset.view);

// Miniatura 320×240: una por corrida ok/aviso, con la vista iso y visibilidad por defecto (comparables entre sí)
async function captureThumb(r) {
  const row = st.runs.find(x => x.id === r.id);
  if ((row ? row.thumb : r.thumb) || !st.meshes.size || !['ok', 'warn'].includes(r.status) || st.run?.id !== r.id) return;
  const W = 320, H = 240, pr = renderer.getPixelRatio();
  const vis = [...st.meshes.values()].map(m => m.visible);
  for (const m of st.meshes.values()) { const b = (m.userData.boundary || '').toLowerCase(); m.visible = !m.userData.component.includes('ext') && !(b.includes('inflow') || b.includes('outflow')); }
  const saved = { pos: camera.position.clone(), tgt: controls.target.clone() };
  renderer.setPixelRatio(1); renderer.setSize(W, H, false); camera.aspect = W / H; camera.updateProjectionMatrix();
  fit(); renderer.render(scene, camera);
  const pending = new Promise(res => renderer.domElement.toBlob(res, 'image/png'));  // copia el lienzo ya
  // volver al tamaño del visor en el mismo tick: el usuario no llega a ver el lienzo de 320×240
  [...st.meshes.values()].forEach((m, i) => { m.visible = vis[i]; });
  renderer.setPixelRatio(pr); lastW = lastH = 0; resize();
  camera.position.copy(saved.pos); controls.target.copy(saved.tgt); controls.update(); renderer.render(scene, camera);
  const blob = await pending;
  if (!blob) return;
  const j = await fetch(`/api/runs/${encodeURIComponent(r.id)}/thumb`, { method: 'POST', headers: { 'content-type': 'image/png' }, body: blob });
  if (j.ok) { const t = Math.floor(Date.now() / 1000); if (row) row.thumb = t; if (st.run?.id === r.id) st.run.thumb = t; renderGallery(true); }
}

// ---------------------------------------------------------------- tema
function setTheme(t) { if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme; LS.set('cft_theme', t); applyBg(); }
$('theme').onclick = () => setTheme((document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')) === 'dark' ? 'light' : 'dark');
matchMedia('(prefers-color-scheme: light)').addEventListener('change', applyBg);
if (LS.get('cft_theme')) setTheme(LS.get('cft_theme'));

// ---------------------------------------------------------------- teclado global
addEventListener('keydown', e => {
  const typing = e.target.closest?.('input,textarea,select,[contenteditable]');
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && e.target.id !== 'chattext' && !e.target.closest?.('.card-run')) { e.preventDefault(); runNow(); return; }
  if (e.key === 'Escape') { if (!$('savename').hidden) { hideSaveInput(); renderActive(); } else if (st.runB) clearB(); return; }
  if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === 'f' || e.key === 'F') fit();
  else if (e.key === '1') fit('iso'); else if (e.key === '2') fit('axial'); else if (e.key === '3') fit('lateral');
  else if (e.key === '`') setCollapsed(!$('stage').classList.contains('dock-collapsed'));
});

// reloj de 1 s: contadores de «Corriendo… N s» sin esperar al sondeo
function tickClock() {
  if (st.status.running || st.runs.some(r => r.status === 'running')) {
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
renderCompare(); renderActive();
window.__cft = { st, group, camera, controls, scene, fit, renderer, captureThumb, selectRun, setB, clearB };
loadProjects().catch(() => {}); poll();
