// STAR-CCM+ · Agente — lógica de la página (módulo ES, sin build). Endpoints: ui/server.py.
// Secciones: utilidades · casos · caso activo (resumen, escenas, convergencia) · estado del solver · chat SSE · tema.
const $ = id => document.getElementById(id);
const LS = {
  get(k, d = null) { try { const v = localStorage.getItem(k); return v ?? d; } catch { return d; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} },
};
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (x, d = 1) => x == null || isNaN(+x) ? '–' : (+x).toFixed(d).replace('.', ',');
const st = { cases: [], case: null, data: null, tab: LS.get('scc_tab', 'resumen'), status: {}, chatting: false, session: null, lastMsg: '', failures: 0 };

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || ('HTTP ' + r.status));
  return j;
}
function toast(txt, cls = '') { const t = $('toast'); t.textContent = txt; t.className = cls; clearTimeout(toast.t); toast.t = setTimeout(() => { t.textContent = ''; }, 5000); }

// markdown mínimo: títulos, tablas, negrita, código, viñetas, ---
function md(s) {
  const lines = esc(s).split('\n'); const out = []; let i = 0;
  while (i < lines.length) {
    const ln = lines[i];
    if (/^\s*\|.*\|\s*$/.test(ln) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {
      const rows = []; while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
      const cells = r => r.trim().slice(1, -1).split('|').map(c => c.trim());
      out.push('<table><tr>' + cells(rows[0]).map(c => `<th>${c}</th>`).join('') + '</tr>' + rows.slice(2).map(r => '<tr>' + cells(r).map(c => `<td class="${/^[\d\s.,%−\-e+*]+$/.test(c.replace(/\*\*/g, '')) ? 'num' : ''}">${c}</td>`).join('') + '</tr>').join('') + '</table>');
    } else if (/^```/.test(ln)) {
      const code = []; i++; while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]); i++;
      out.push('<pre>' + code.join('\n') + '</pre>');
    } else if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(ln)) { out.push('<hr>'); i++; }
    else if (/^#{1,4}\s/.test(ln)) { const n = ln.match(/^#+/)[0].length; out.push(`<h${Math.min(n + 1, 4)}>${ln.replace(/^#+\s+/, '')}</h${Math.min(n + 1, 4)}>`); i++; }
    else if (/^\s*[-*]\s+/.test(ln)) {
      const items = []; while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { let it = lines[i++].replace(/^\s*[-*]\s+/, ''); while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*[-*]\s+/.test(lines[i])) it += ' ' + lines[i++].trim(); items.push(it); }
      out.push('<ul>' + items.map(x => `<li>${x}</li>`).join('') + '</ul>');
    } else if (ln.trim() === '') { out.push(''); i++; }
    else { const p = []; while (i < lines.length && lines[i].trim() !== '' && !/^(#{1,4}\s|\s*[-*]\s|\s*\||```)/.test(lines[i])) p.push(lines[i++]); out.push('<p>' + p.join(' ') + '</p>'); }
  }
  return out.join('\n').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>');
}

// ---------------------------------------------------------------- casos
async function loadCases() {
  st.cases = await api('/api/cases');
  $('ccount').textContent = st.cases.length ? `(${st.cases.length})` : '';
  const g = $('cases');
  if (!st.cases.length) { g.innerHTML = '<div class="gallery-empty">Sin casos en cases/</div>'; return; }
  g.innerHTML = st.cases.map(c => `<button class="card-case" role="option" data-name="${esc(c.name)}" aria-selected="${c.name === st.case}">
    <span class="name">${esc(c.name)}</span>
    <span class="sub">${esc(c.date)} · ${c.n_images} escena${c.n_images === 1 ? '' : 's'}</span>
    ${c.last ? `<span class="sub">iter ${c.last.iter ?? '–'} · H ${fmt(c.last.H)} m · η ${fmt(c.last.eta * 100, 1)} %</span>` : ''}
  </button>`).join('');
  for (const b of g.querySelectorAll('.card-case')) b.onclick = () => openCase(b.dataset.name);
  if (!st.case) openCase(LS.get('scc_case') && st.cases.some(c => c.name === LS.get('scc_case')) ? LS.get('scc_case') : st.cases[0].name);
}

async function openCase(name) {
  st.case = name; LS.set('scc_case', name);
  for (const b of $('cases').querySelectorAll('.card-case')) b.setAttribute('aria-selected', b.dataset.name === name);
  try { st.data = await api('/api/cases/' + encodeURIComponent(name)); }
  catch (e) { toast('No pude abrir el caso: ' + e.message, 'error'); return; }
  const d = st.data;
  $('casetitle').textContent = d.title || d.name;
  $('casemeta').textContent = `cases/${d.name} · ${d.date}`;
  $('bimg').textContent = d.images.length || '';
  $('bconv').textContent = d.convergencia ? d.convergencia.rows.length : '';
  $('resumen').innerHTML = d.resumen ? md(d.resumen) : '<p class="mut">Este caso no tiene RESUMEN.md</p>';
  renderScenes(d); renderConv(d);
  openTab(st.tab);
}

function renderScenes(d) {
  const s = $('scenes');
  if (!d.images.length) { s.innerHTML = '<p class="mut">Sin escenas en images/</p>'; return; }
  s.innerHTML = d.images.map(im => { const u = `/files/${encodeURIComponent(d.name)}/images/${encodeURIComponent(im.file)}?v=${im.mtime}`;
    return `<figure class="scene"><img src="${u}" alt="${esc(im.label)}" loading="lazy" data-u="${u}" data-cap="${esc(im.label)}"><figcaption>${esc(im.label)} <span class="mut mono">${esc(im.file)} · ${Math.round(im.size / 1024)} KB</span><span class="sp"></span><button class="sm regen" data-n="${esc(im.file.replace(/\.png$/, ''))}" title="Vuelve a exportar esta escena desde el solver vivo (export_scene, ~10 s)">↻</button></figcaption></figure>`; }).join('');
  for (const img of s.querySelectorAll('img')) img.onclick = () => { $('lightbox').querySelector('img').src = img.dataset.u; $('lightbox').querySelector('.lb-cap').textContent = img.dataset.cap; $('lightbox').hidden = false; };
  for (const b of s.querySelectorAll('.regen')) b.onclick = async () => {
    b.disabled = true; b.textContent = '…';
    try { const r = await api('/api/scene', { name: b.dataset.n, case: d.name }); toast(`«${b.dataset.n}» exportada en ${r.seconds} s`, 'ok'); openCase(d.name); }
    catch (e) { toast(e.message, 'warn'); b.disabled = false; b.textContent = '↻'; }
  };
}
$('lightbox').onclick = () => { $('lightbox').hidden = true; };

// convergencia: un gráfico por magnitud (nunca dos ejes), línea 2 px, puntos ≥ 8 px, tooltip, y la tabla
function chart(x, y, label, unit) {
  const W = 420, H = 200, L = 52, R = 14, T = 16, B = 30;
  const xs = x.filter((_, i) => y[i] != null), ys = y.filter(v => v != null);
  if (ys.length < 1) return '';
  const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin0 = Math.min(...ys), ymax0 = Math.max(...ys);
  const pad = (ymax0 - ymin0 || Math.abs(ymax0) || 1) * 0.15, ymin = ymin0 - pad, ymax = ymax0 + pad;
  const sx = v => L + (xmax === xmin ? 0.5 : (v - xmin) / (xmax - xmin)) * (W - L - R);
  const sy = v => T + (1 - (v - ymin) / (ymax - ymin)) * (H - T - B);
  const ticks = n => Array.from({ length: n }, (_, i) => ymin + (ymax - ymin) * i / (n - 1));
  const dec = Math.abs(ymax - ymin) < 2 ? 3 : Math.abs(ymax - ymin) < 20 ? 2 : 1;
  const grid = ticks(4).map(v => `<line x1="${L}" x2="${W - R}" y1="${sy(v)}" y2="${sy(v)}" class="grid"/><text x="${L - 6}" y="${sy(v) + 4}" class="tick" text-anchor="end">${fmt(v, dec)}</text>`).join('');
  const xt = xs.map((v, i) => `<text x="${sx(v)}" y="${H - 10}" class="tick" text-anchor="middle">${v}</text>`).join('');
  const path = xs.map((v, i) => `${i ? 'L' : 'M'}${sx(v).toFixed(1)},${sy(ys[i]).toFixed(1)}`).join(' ');
  const dots = xs.map((v, i) => `<circle cx="${sx(v)}" cy="${sy(ys[i])}" r="4" class="pt"><title>iter ${v}: ${label} = ${fmt(ys[i], dec)} ${unit}</title></circle>`).join('');
  const last = `<text x="${sx(xs[xs.length - 1]) - 6}" y="${sy(ys[ys.length - 1]) - 8}" class="lbl" text-anchor="end">${fmt(ys[ys.length - 1], dec)} ${unit}</text>`;
  return `<figure class="chart"><figcaption>${esc(label)} <span class="mut">(${esc(unit)}) frente a iteración</span></figcaption>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)} frente a iteración">${grid}<line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" class="axis"/>${xt}<path d="${path}" class="line"/>${dots}${last}</svg></figure>`;
}
function renderConv(d) {
  const c = $('conv'), cv = d.convergencia;
  if (!cv || !cv.rows.length) { c.innerHTML = '<p class="mut">Sin reports/convergencia.csv</p>'; return; }
  const col = n => { const k = cv.columns.indexOf(n); return k < 0 ? null : cv.rows.map(r => r[k]); };
  const it = col('iter') || cv.rows.map((_, i) => i + 1);
  const units = { H: 'm', M: 'N·m', eta: '', continuity: '', Q_out: 'kg/s' };
  const charts = ['H', 'M'].map(k => col(k) ? chart(it, col(k), k, units[k]) : '').join('');
  const delta = (k) => { const v = col(k); if (!v || v.length < 2 || !v[v.length - 1]) return null; return Math.abs((v[v.length - 1] - v[v.length - 2]) / v[v.length - 1] * 100); };
  const dH = delta('H'), dM = delta('M');
  const crit = dH != null ? `<p class="small">Último bloque: ΔH ${fmt(dH, 2)} % · ΔM ${fmt(dM, 2)} % ${dH < 0.5 && dM < 0.5 ? '<span class="tag ok">convergido (&lt; 0,5 %)</span>' : '<span class="tag warn">aún no (&gt; 0,5 %)</span>'}</p>` : '';
  const table = `<table class="data"><tr>${cv.columns.map(h => `<th>${esc(h)}</th>`).join('')}</tr>${cv.rows.map(r => '<tr>' + r.map((v, i) => `<td class="num">${v == null ? '–' : (Math.abs(v) > 0 && (Math.abs(v) < 1e-2 || Math.abs(v) >= 1e5)) ? v.toExponential(2).replace('.', ',') : fmt(v, i === 0 ? 0 : 3)}</td>`).join('') + '</tr>').join('')}</table>`;
  c.innerHTML = `<div class="charts">${charts}</div>${crit}<details open><summary>${esc(cv.file)} · ${cv.rows.length} filas</summary>${table}</details>`;
}

function openTab(t) {
  st.tab = t; LS.set('scc_tab', t);
  for (const b of document.querySelectorAll('[role=tab]')) b.setAttribute('aria-selected', b.dataset.tab === t);
  for (const id of ['resumen', 'escenas', 'conv', 'live', 'tree', 'prog']) $('tab-' + id).hidden = id !== t;
  if (t === 'live') loadLive();
  if (t === 'tree') loadTree(false);
  if (t === 'prog') loadProgress();
}

// ---------------------------------------------------------------- árbol de la simulación (inspect tree del MCP)
const KINDS = { solver: 'Solver', part: 'Partes', region: 'Regiones', boundary: 'Fronteras', physics: 'Física', model: 'Modelos', mesh_op: 'Operaciones de malla', mesher: 'Malladores', report: 'Reportes', monitor: 'Monitores', scene: 'Escenas', continuum: 'Continuos', interface: 'Interfaces' };
function renderTree(r) {
  const t = $('tree');
  if (!r.tree) { t.innerHTML = '<p class="mut">Sin lectura todavía. Con el solver vivo pulsa «Leer del solver».</p>'; return; }
  const when = r.at ? new Date(r.at * 1000).toLocaleTimeString('es') : '';
  $('treestate').textContent = `leído ${when}${r.seconds ? ' en ' + r.seconds + ' s' : ''}${r.sim ? ' · ' + r.sim.split(/[\\/]/).pop() : ''}${r.alive ? '' : ' · (solver apagado: lectura anterior)'}`;
  t.innerHTML = Object.entries(r.tree).map(([k, items]) => `<details open><summary>${esc(KINDS[k] || k)} <span class="badge">${items.length}</span></summary><ul>${items.map(it => `<li><span class="n">${esc(it.name)}</span>${it.type ? `<span class="t">${esc(it.type)}</span>` : ''}${it.value != null ? `<span class="v">${esc(it.value)}</span>` : ''}</li>`).join('')}</ul></details>`).join('');
}
async function loadTree(refresh) {
  if (refresh) { $('treerefresh').disabled = true; $('treestate').textContent = 'leyendo el árbol del solver…'; }
  try { renderTree(await api('/api/tree' + (refresh ? '?refresh=1' : ''))); }
  catch (e) { $('treestate').textContent = e.message; }
  $('treerefresh').disabled = false;
}
$('treerefresh').onclick = () => loadTree(true);

// ---------------------------------------------------------------- progreso: log del servidor y macros (la «terminal»)
const prog = { key: '' };
function hlLine(l) {
  const c = /AGENT_ERROR|Exception|error|Error|FAIL/.test(l) ? 'err' : /AGENT_BEGIN|AGENT_END|Playing macro|SAVED|PNG |SCENE /.test(l) ? 'hl' : /complete|Server::start|converged/i.test(l) ? 'ok' : '';
  return c ? `<span class="${c}">${esc(l)}</span>` : esc(l);
}
async function loadProgress() {
  let p; try { p = await api('/api/progress'); } catch (e) { $('macrostate').textContent = e.message; return; }
  const m = p.macro;
  $('progdot').hidden = !(m && m.running && st.status.alive);
  if (m) {
    const t0 = new Date(m.started * 1000).toLocaleTimeString('es');
    $('macrostate').innerHTML = m.running && st.status.alive ? `Macro <b>${esc(m.file)}</b> en marcha desde ${t0} <span class="tag ok">corriendo</span>`
      : `Última macro <b>${esc(m.file)}</b> · ${t0}${m.finished ? ' → ' + new Date(m.finished * 1000).toLocaleTimeString('es') : ''} <span class="tag">${m.running ? 'sin salida' : 'terminada'}</span>`;
    $('macrobody').querySelector('pre').textContent = m.body + (m.out.length ? '\n\n--- salida\n' + m.out.join('\n') : '');
  } else { $('macrostate').textContent = 'Sin macros inyectadas todavía.'; $('macrobody').querySelector('pre').textContent = ''; }
  const key = `${p.server_log.file}|${p.server_log.size}|${(p.agent_log || []).slice(-1)[0] || ''}`;
  if (key !== prog.key) {
    prog.key = key;
    const lines = p.server_log.tail.length ? p.server_log.tail : ['(sin log del servidor todavía)'];
    $('term').innerHTML = lines.map(hlLine).join('\n') + (p.agent_log.length ? '\n\n<span class="hl">--- agent.log</span>\n' + p.agent_log.map(esc).join('\n') : '');
    if ($('progfollow').checked) $('term').scrollTop = 1e9;
  }
  $('termfile').textContent = p.server_log.file ? `${p.server_log.file} · ${Math.round(p.server_log.size / 1024)} KB` : '';
}
setInterval(() => { if (st.tab === 'prog') loadProgress(); }, 3000);

// ---------------------------------------------------------------- parámetros -> prompt al chat (la página nunca edita el .sim)
const PARAMS = [['p_rpm', v => `velocidad de giro del rotor a ${v} rpm (MRF)`], ['p_mdot', v => `caudal másico de entrada a ${v} kg/s`], ['p_base', v => `tamaño base de malla a ${v} mm (remallar las 3 operaciones)`], ['p_iter', v => `luego corre ${v} iteraciones (en bloques de 100 con iterate)`]];
$('paskbtn').onclick = () => {
  const parts = PARAMS.map(([id, f]) => { const v = $(id).value.trim(); return v ? f(v) : ''; }).filter(Boolean);
  if (!parts.length) { toast('Rellena al menos un parámetro', 'warn'); return; }
  const sim = st.case ? `sims/${st.case}.sim` : 'el .sim abierto';
  $('chattext').value = `En la simulación ${sim} (server_start la reutiliza si está viva): cambia ${parts.join('; ')}. Precompila cada macro y usa las recetas bomba-*. Al terminar, añade las filas a cases/${st.case || '<caso>'}/reports/convergencia.csv, vuelve a exportar las escenas de presión, velocidad e y+ a images/ y dime H, M y eficiencia en una tabla frente a los valores anteriores.`;
  sendChat();
};
$('pclear').onclick = () => { for (const [id] of PARAMS) $(id).value = ''; };

// ---------------------------------------------------------------- abrir en la GUI de STAR-CCM+
$('opengui').onclick = async () => {
  if (!st.case) return;
  if (st.status.alive) { toast('Hay un servidor batch vivo sobre este .sim: apágalo primero', 'warn'); return; }
  if (!confirm(`Abrir sims/${st.case}.sim en la GUI de STAR-CCM+.\nLa licencia Power-on-Demand cobra por hora de sesión. ¿Continuar?`)) return;
  $('opengui').disabled = true;
  try { const r = await api('/api/open_gui', { case: st.case }); toast(`GUI lanzada (pid ${r.pid}); tarda unos segundos en abrir`, 'ok'); }
  catch (e) { toast(e.message, 'error'); }
  $('opengui').disabled = false;
};

// ---------------------------------------------------------------- en vivo: escena grande exportada del solver
// STAR-CCM+ en modo servidor no tiene ventana: lo que se ve es un PNG exportado a demanda (~10 s por escena).
const live = { rows: [], sel: null, busy: false };
function showLive(r) {
  live.sel = r ? r.url : null;
  const v = $('liveview');
  if (!r) { v.innerHTML = '<div class="empty mut">Sin escenas exportadas todavía. Con el solver vivo, escribe el nombre de una escena y pulsa Actualizar; o pide a Claude que exporte una.</div>'; }
  else {
    const when = new Date(r.mtime * 1000);
    v.innerHTML = `<img src="${r.url}?v=${r.mtime}" alt="${esc(r.label)}"><span class="cap">${esc(r.label)} · ${esc(r.src)}/${esc(r.file)} · ${when.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>`;
    v.querySelector('img').onclick = () => { $('lightbox').querySelector('img').src = `${r.url}?v=${r.mtime}`; $('lightbox').querySelector('.lb-cap').textContent = r.label; $('lightbox').hidden = false; };
  }
  $('livestrip').innerHTML = live.rows.map(x => `<button data-u="${x.url}" aria-pressed="${x.url === live.sel}" title="${esc(x.src)}/${esc(x.file)}"><img src="${x.url}?v=${x.mtime}" alt="" loading="lazy">${esc(x.label).slice(0, 18)}</button>`).join('');
  for (const b of $('livestrip').querySelectorAll('button')) b.onclick = () => showLive(live.rows.find(x => x.url === b.dataset.u));
}
async function loadLive(keep = true) {
  try { live.rows = (await api('/api/live' + (st.case ? '?case=' + encodeURIComponent(st.case) : ''))).scenes; }
  catch (e) { $('livestate').textContent = e.message; return; }
  const cur = keep && live.sel ? live.rows.find(x => x.url === live.sel) : null;
  showLive(cur || live.rows[0] || null);
}
async function refreshScene() {
  const name = $('scenename').value.trim() || (live.sel ? live.rows.find(x => x.url === live.sel)?.label.replace(/ /g, '_') : '');
  if (!name) { $('livestate').textContent = 'escribe el nombre de una escena'; $('scenename').focus(); return; }
  if (live.busy) return;
  live.busy = true; $('refreshscene').disabled = true; $('livedot').hidden = false;
  const t0 = Date.now(); const clock = setInterval(() => { $('livestate').textContent = `exportando «${name}»… ${Math.round((Date.now() - t0) / 1000)} s`; }, 500);
  try {
    const r = await api('/api/scene', { name, case: st.case, width: 1600, height: 1000 });
    $('livestate').textContent = `«${name}» exportada en ${r.seconds} s`;
    await loadLive(false); showLive(live.rows.find(x => x.url === r.url) || live.rows[0]);
    if (st.case) loadCases();
  } catch (e) { $('livestate').textContent = e.message; toast(e.message, 'warn'); }
  clearInterval(clock); live.busy = false; $('refreshscene').disabled = false; $('livedot').hidden = true;
}
$('refreshscene').onclick = refreshScene;
$('scenename').addEventListener('keydown', e => { if (e.key === 'Enter') refreshScene(); });
$('listscenes').onclick = async () => {
  $('listscenes').disabled = true; $('livestate').textContent = 'preguntando al solver…';
  try { const r = await api('/api/scenes'); $('scenelist').innerHTML = r.names.map(n => `<option value="${esc(n)}">`).join('');
    $('livestate').textContent = r.names.length ? `escenas: ${r.names.join(', ')}` : 'el .sim no tiene escenas'; if (r.names.length && !$('scenename').value) $('scenename').value = r.names[0]; }
  catch (e) { $('livestate').textContent = e.message; }
  $('listscenes').disabled = false;
};
setInterval(() => {  // auto: cada 60 s mientras el solver esté vivo y la pestaña abierta
  if ($('liveauto').checked && st.tab === 'live' && st.status.alive && !st.chatting && !live.busy) refreshScene();
}, 60000);
setInterval(() => { if (st.tab === 'live' && !live.busy) loadLive(); }, 10000);  // PNG nuevos exportados por Claude
for (const b of document.querySelectorAll('[role=tab]')) b.onclick = () => openTab(b.dataset.tab);

// ---------------------------------------------------------------- estado del solver
function renderStatus(s) {
  st.status = s;
  const dot = s.alive ? 'ok' : s.stale ? 'busy' : 'off';
  const txt = s.stopping ? 'apagando solver…' : s.alive ? `solver vivo · puerto ${s.port} · ${s.idle_min ?? '?'} min sin actividad` : s.stale ? 'solver caído (.server.json viejo)' : 'solver apagado';
  $('solver').innerHTML = `<span class="dot ${dot}"></span><span>${esc(txt)}</span>` + ((s.chatting || st.chatting) ? ' <span class="dot chat"></span><span>Claude trabajando</span>' : '');
  $('stopsolver').hidden = !s.alive; $('stopsolver').disabled = !!s.stopping;
  $('refreshscene').title = s.alive ? 'Exporta la escena a PNG desde el solver vivo (~10 s)' : 'Hace falta un solver vivo (pide a Claude server_start)';
  $('opengui').disabled = !!s.alive; $('opengui').title = s.alive ? 'Hay un servidor batch vivo: apágalo antes de abrir la GUI' : 'Abre este .sim en la GUI de STAR-CCM+ (la licencia PoD cobra por hora)';
  $('solvertag').innerHTML = s.alive ? '<span class="tag ok">vivo</span>' : s.stale ? '<span class="tag warn">caído</span>' : '<span class="tag">apagado</span>';
  const rows = s.alive || s.stale ? [['pid', s.pid], ['puerto', s.port], ['sim', s.sim ? s.sim.split(/[\\/]/).pop() : '(nueva)'], ['procesos', s.np], ['arranque', s.started ? s.started.replace('T', ' ') : '–'], ['inactivo', s.idle_min != null ? `${fmt(s.idle_min, 0)} / ${s.idle_limit_min} min` : '–']] : [['apagado por inactividad', `${s.idle_limit_min} min`]];
  $('solverkv').querySelector('tbody').innerHTML = rows.map(([k, v]) => `<tr><td class="mut">${esc(k)}</td><td class="mono" title="${esc(v)}">${esc(v)}</td></tr>`).join('');
  $('agentlog').textContent = (s.log || []).join('\n') || '(vacío)';
}
async function poll() {
  try { renderStatus(await api('/api/status')); st.failures = 0; $('offline').hidden = true; }
  catch (e) { st.failures++; $('offline').hidden = false; $('offlinetxt').textContent = 'Sin conexión con el servidor local: ' + e.message; }
}
$('retry').onclick = poll;
setInterval(poll, 5000);
$('stopsolver').onclick = async () => {
  if (!confirm('¿Guardar el .sim y apagar el servidor de STAR-CCM+?')) return;
  $('stopsolver').disabled = true; $('solver').innerHTML = '<span class="dot busy"></span><span>apagando solver…</span>';
  try { const r = await api('/api/server/stop', { save: true }); toast(r.stopped ? `Solver apagado en ${r.seconds} s${r.saved ? ' · guardado ' + r.saved.split(/[\\/]/).pop() : ''}${r.forced ? ' (forzado)' : ''}` : 'No había servidor', r.stopped ? 'ok' : 'warn'); }
  catch (e) { toast('No pude apagar: ' + e.message, 'error'); }
  poll();
};

// ---------------------------------------------------------------- chat con Claude Code (SSE)
function placeQuick() {
  const empty = !$('chatlog').querySelector('.m');
  $('chatempty').hidden = !empty;
  if (empty) $('chatempty').appendChild($('quick')); else $('chatin').before($('quick'));
}
function addMsg(cls, html) {
  const d = document.createElement('div'); d.className = 'm ' + cls; d.innerHTML = html; $('chatlog').appendChild(d);
  placeQuick(); $('chatlog').scrollTop = 1e9; return d;
}
function toolSummary(name, inp = {}) {
  const bits = [inp.name, inp.path, inp.query && `«${inp.query}»`, inp.n != null && `${inp.n} iter`, inp.sim_path && String(inp.sim_path).split(/[\\/]/).pop(), inp.body && `${String(inp.body).split('\n').length} líneas Java`].filter(Boolean);
  return [name, ...bits].join(' · ');
}
function setChatting(on) { st.chatting = on; $('send').disabled = on; $('stopchat').disabled = !on; if (st.status.alive != null) renderStatus(st.status); }
function onChatEvent(ev, ctx) {
  if (['result', 'error'].includes(ev.kind) && /No conversation found/i.test(ev.text || '')) { ctx.stale = true; return; }
  if (ev.kind === 'result' && ev.turns === 0 && ev.subtype !== 'success' && !ev.text) return;
  if (ev.kind === 'init') { st.session = ev.session_id; LS.set('scc_session', st.session); $('chatstate').textContent = `sesión ${st.session.slice(0, 8)} · ${ev.model || ''}`; }
  else if (ev.kind === 'text') { addMsg('bot', md(ev.text)); ctx.tool = ''; $('chatstate').textContent = 'pensando…'; }
  else if (ev.kind === 'tool') {
    addMsg('tool', `<details><summary>Tool: ${esc(toolSummary(ev.name, ev.input || {}))}</summary>${esc(JSON.stringify(ev.input || {}, null, 1)).slice(0, 2000)}</details>`);
    ctx.tool = ev.name; ctx.t0 = Date.now(); $('chatstate').textContent = `ejecutando ${ev.name}…`;
    if (/server_|export_scene|iterate/.test(ev.name)) ctx.refresh = true;
  }
  else if (ev.kind === 'tool_result') { if (ev.is_error) addMsg('tool bad', 'Error de tool: ' + esc(ev.text)); else if (ctx.tool === 'server_start' || ctx.tool === 'server_stop') poll(); }
  else if (ev.kind === 'status') { $('chatstate').textContent = ev.text; }
  else if (ev.kind === 'ping') { if (!ctx.tool) $('chatstate').textContent = `trabajando… ${ev.t} s`; }
  else if (ev.kind === 'error') addMsg('err', /conversación en curso/.test(ev.text) ? 'Ya hay una conversación en curso. Espera o pulsa Detener.' : esc(ev.text));
  else if (ev.kind === 'result') { ctx.tool = ''; if (ev.text) addMsg('err', esc(ev.text)); $('chatstate').textContent = `listo · ${ev.turns ?? '?'} turnos · ${ev.seconds} s`; }
  else if (ev.kind === 'stopped') { addMsg('bot mut', 'Detenido por el usuario.'); ctx.tool = ''; $('chatstate').textContent = 'detenido'; }
  else if (ev.kind === 'done') { ctx.done = true; if (ev.rc && ev.rc !== 0 && !/listo|detenido/.test($('chatstate').textContent)) $('chatstate').textContent = `terminó con código ${ev.rc}`; }
  if (!ctx.login && ['text', 'result', 'error'].includes(ev.kind) && /401|not logged in|OAuth|auth login/i.test(ev.text || '')) {
    ctx.login = true; addMsg('err', 'La CLI de Claude Code no tiene sesión. En una terminal ejecuta: <code>claude auth login</code>');
  }
}
async function sendChat(retry = false) {
  const text = $('chattext').value.trim(); if (!text || st.chatting) return;
  $('chattext').value = ''; st.lastMsg = text; if (!retry) addMsg('user', esc(text));
  setChatting(true); $('chatstate').textContent = 'pensando…';
  const ctx = { t0: Date.now(), tool: '', login: false, done: false, refresh: false };
  const clock = setInterval(() => { if (ctx.tool) $('chatstate').textContent = `ejecutando ${ctx.tool}… ${Math.round((Date.now() - ctx.t0) / 1000)} s`; }, 1000);
  try {
    const r = await fetch('/api/chat', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ message: text, session_id: st.session, case: st.case }) });
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
  clearInterval(clock); setChatting(false); poll();
  if (ctx.refresh) { loadCases(); if (st.case) openCase(st.case); }  // escenas o convergencia nuevas
  if (ctx.stale && !retry) {
    st.session = null; LS.set('scc_session', null);
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
  if (!b.dataset.armed) { b.dataset.armed = '1'; b.textContent = '¿Seguro? Pulsa otra vez'; newchatT = setTimeout(() => { delete b.dataset.armed; b.textContent = 'Nueva conversación'; }, 4000); return; }
  clearTimeout(newchatT); delete b.dataset.armed; b.textContent = 'Nueva conversación';
  st.session = null; LS.set('scc_session', null);
  for (const m of $('chatlog').querySelectorAll('.m')) m.remove();
  placeQuick(); $('chatstate').textContent = 'nueva conversación';
};
for (const b of $('quick').querySelectorAll('[data-q]')) b.onclick = () => { $('chattext').value = b.dataset.q; sendChat(); };
st.session = LS.get('scc_session'); if (st.session) $('chatstate').textContent = `sesión ${st.session.slice(0, 8)} (continúa)`;

// ---------------------------------------------------------------- tema y arranque
const theme = LS.get('scc_theme'); if (theme) document.documentElement.dataset.theme = theme;
$('theme').onclick = () => { const dark = matchMedia('(prefers-color-scheme: dark)').matches; const cur = document.documentElement.dataset.theme || (dark ? 'dark' : 'light'); const nx = cur === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = nx; LS.set('scc_theme', nx); };
placeQuick();
poll();
loadCases().catch(e => { $('cases').innerHTML = `<div class="gallery-empty">No pude leer los casos: ${esc(e.message)}</div>`; });
