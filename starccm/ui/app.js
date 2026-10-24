// STAR-CCM+ · Agente — lógica de la página (módulo ES, sin build). Endpoints: ui/server.py; datasets: ui/surfaces.py.
// Secciones: utilidades · caso · visor 3D (three.js) · superficies con campo · escenas PNG · árbol del .sim ·
// dock (salida, gráficos, resumen) · estado del solver · chat SSE · parámetros · tema y teclado · arranque.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = id => document.getElementById(id);
const LS = {
  get(k, d = null) { try { const v = localStorage.getItem(k); return v ?? d; } catch { return d; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} },
};
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (x, d = 1) => x == null || isNaN(+x) ? '–' : (+x).toFixed(d).replace('.', ',');
// un único formato numérico (leyenda, reportes, tablas): decimales con coma y miles con punto; científico solo para muy pequeños o enormes
const sci = x => { if (x == null || isNaN(x)) return '–'; const a = Math.abs(x); if ((a < 1e-2 && a !== 0) || a >= 1e7) return x.toExponential(2).replace('.', ','); return x.toLocaleString('es', { minimumFractionDigits: 0, maximumFractionDigits: a >= 1000 ? 0 : a >= 10 ? 2 : 3, useGrouping: a >= 10000 }); };
const st = { cases: [], case: null, data: null, status: {}, chatting: false, session: null, lastMsg: '', tab: LS.get('scc_tab', 'out'),
  view: '3d', datasets: [], ds: null, scalar: '', cmap: LS.get('scc_cmap', 'ccm'), range: null, settings: null, where: 'local' };
const NARROW = matchMedia('(max-width:1099px)');

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || ('HTTP ' + r.status));
  return j;
}
function toast(txt, cls = '') { const t = $('toast'); t.textContent = txt; t.className = cls; clearTimeout(toast.t); toast.t = setTimeout(() => { t.textContent = ''; }, 6000); }
function md(s) {  // markdown mínimo: títulos, tablas, negrita, código, viñetas, ---
  const lines = esc(s).split('\n'); const out = []; let i = 0;
  while (i < lines.length) {
    const ln = lines[i];
    if (/^\s*\|.*\|\s*$/.test(ln) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {
      const rows = []; while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
      const cells = r => r.trim().slice(1, -1).split('|').map(c => c.trim());
      out.push('<table><tr>' + cells(rows[0]).map(c => `<th>${c}</th>`).join('') + '</tr>' + rows.slice(2).map(r => '<tr>' + cells(r).map(c => `<td class="${/^[\d\s.,%−\-e+*]+$/.test(c.replace(/\*\*/g, '')) ? 'num' : ''}">${c}</td>`).join('') + '</tr>').join('') + '</table>');
    } else if (/^```/.test(ln)) { const code = []; i++; while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]); i++; out.push('<pre>' + code.join('\n') + '</pre>'); }
    else if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(ln)) { out.push('<hr>'); i++; }
    else if (/^#{1,4}\s/.test(ln)) { const n = Math.min(ln.match(/^#+/)[0].length + 1, 4); out.push(`<h${n}>${ln.replace(/^#+\s+/, '')}</h${n}>`); i++; }
    else if (/^\s*[-*]\s+/.test(ln)) { const items = []; while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { let it = lines[i++].replace(/^\s*[-*]\s+/, ''); while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*[-*]\s+/.test(lines[i])) it += ' ' + lines[i++].trim(); items.push(it); } out.push('<ul>' + items.map(x => `<li>${x}</li>`).join('') + '</ul>'); }
    else if (ln.trim() === '') { out.push(''); i++; }
    else { const p = []; while (i < lines.length && lines[i].trim() !== '' && !/^(#{1,4}\s|\s*[-*]\s|\s*\||```)/.test(lines[i])) p.push(lines[i++]); out.push('<p>' + p.join(' ') + '</p>'); }
  }
  return out.join('\n').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>');
}

// ---------------------------------------------------------------- caso (una simulación)
const fillCaseSelect = cs => { $('case').innerHTML = cs.map(c => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('') || '<option value="">(sin casos)</option>'; };
async function loadCases() {
  st.cases = await api('/api/cases');
  const sel = $('case'); fillCaseSelect(st.cases);
  const want = LS.get('scc_case');
  const name = st.cases.some(c => c.name === want) ? want : st.cases[0]?.name;
  if (name) { sel.value = name; await openCase(name); }
}
$('case').onchange = () => openCase($('case').value);
// ---------------------------------------------------------------- caso nuevo: carpeta + geometría + encargo a la IA
$('newcase').onclick = async () => {
  $('nc_prog').textContent = ''; ncFiles = []; ncRender();
  try { const s = await api('/api/settings'); $('nc_where').textContent = s.run_where === 'server' ? 'Correrá en el Servidor Linux (STAR-CCM+ 2502, 14 núcleos); la geometría se sube sola.' : 'Correrá en este PC (Local). Puedes cambiarlo arriba en «Ejecutar en».'; } catch { $('nc_where').textContent = ''; }
  $('ncdlg').showModal(); $('nc_name').focus();
};
$('nccancel').onclick = () => $('ncdlg').close();
// los archivos se SUMAN: cada selección o arrastre añade a la lista (hay selectores que solo dejan elegir uno)
let ncFiles = [];
const CAD_OK = /\.(stp|step|x_t|x_b|igs|iges|stl|jt|sat|cfturbo-ccm)$/i;
function ncAdd(list) {
  const bad = [];
  for (const f of list) { if (!CAD_OK.test(f.name)) { bad.push(f.name); continue; } ncFiles = ncFiles.filter(x => x.name !== f.name); ncFiles.push(f); }
  ncRender(); if (bad.length) $('nc_prog').textContent = 'No admitidos: ' + bad.join(', ');
}
function ncRender() {
  $('nc_list').innerHTML = ncFiles.map((f, i) => `<li><span class="n" title="${esc(f.name)}">${esc(f.name)}</span><span class="c">${(f.size / 1048576).toFixed(2).replace('.', ',')} MB</span><button type="button" class="sm mini" data-i="${i}" aria-label="Quitar ${esc(f.name)}">✕</button></li>`).join('');
  for (const b of $('nc_list').querySelectorAll('button')) b.onclick = () => { ncFiles.splice(+b.dataset.i, 1); ncRender(); };
  $('nc_drop').textContent = ncFiles.length ? `${ncFiles.length} archivo(s). Arrastra o elige más para sumarlos.` : 'Arrastra aquí los archivos, o elígelos arriba (se van sumando).';
}
$('nc_files').onchange = () => { ncAdd([...$('nc_files').files]); $('nc_files').value = ''; };
for (const ev of ['dragenter', 'dragover']) $('ncdlg').addEventListener(ev, e => { e.preventDefault(); $('nc_drop').classList.add('over'); });
for (const ev of ['dragleave', 'drop']) $('ncdlg').addEventListener(ev, e => { e.preventDefault(); $('nc_drop').classList.remove('over'); });
$('ncdlg').addEventListener('drop', e => ncAdd([...(e.dataTransfer?.files || [])]));
const NUM = v => { const x = parseFloat(String(v).replace(',', '.')); return Number.isFinite(x) ? x : null; };
$('ncform').onsubmit = async e => {
  e.preventDefault();
  const name = $('nc_name').value.trim(), files = [...ncFiles];
  const rpm = NUM($('nc_rpm').value), mdot = NUM($('nc_mdot').value), iters = parseInt($('nc_iter').value, 10);
  const run = $('nc_run').checked, tipo = $('nc_type').value, eje = $('nc_axis').value, fluido = $('nc_fluid').value.trim() || 'agua', notas = $('nc_notes').value.trim();
  if (!/^[A-Za-z0-9_-]+$/.test(name)) { $('nc_prog').textContent = 'Nombre: solo letras, números, _ y -'; return; }
  if (!files.length) { $('nc_prog').textContent = 'Elige al menos un archivo de geometría'; return; }
  if (run && (rpm == null || rpm === 0 || mdot == null || mdot <= 0)) { $('nc_prog').textContent = 'Para correr hacen falta rpm (≠ 0) y caudal másico (> 0)'; return; }
  if (st.chatting && run) { $('nc_prog').textContent = 'La IA está trabajando: espera a que termine'; return; }
  $('ncok').disabled = true;
  try {
    await api('/api/cases/new', { name });
    for (const [k, f] of files.entries()) {
      $('nc_prog').textContent = `subiendo ${k + 1}/${files.length}: ${f.name} (${(f.size / 1048576).toFixed(1).replace('.', ',')} MB)…`;
      const r = await fetch(`/api/cases/${encodeURIComponent(name)}/cad/${encodeURIComponent(f.name)}`, { method: 'PUT', body: f });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || ('HTTP ' + r.status));
    }
    $('ncdlg').close(); $('ncform').reset(); ncFiles = []; ncRender();
    await refreshCaseList(); $('case').value = name; await openCase(name);
    toast(`Caso ${name} creado con ${files.length} archivo(s) de geometría`, 'ok');
    if (!run) { $('ncok').disabled = false; return; }
    const lista = files.map(f => f.name).join(', ');
    $('chattext').value = `Caso nuevo cases/${name}: ${tipo}, geometría en cases/${name}/cad/ (${lista}). ` +
      `Datos: ${rpm} rpm sobre ${eje}, caudal másico ${mdot} kg/s de ${fluido}, máximo ${Number.isFinite(iters) ? iters : 1000} iteraciones. ` +
      `Prepara y corre la simulación completa siguiendo el flujo estándar (server_start(name="${name}") sin where; importar, nombrar fronteras, regiones e interfaces, malla por parte, física, MRF, fronteras, reportes), ` +
      `Por etapas: prepara el caso; si dudas de qué cara es entrada o salida, o de algún modelo, pregúntame con opciones y enséñamelo en el visor; ` +
      `luego corre 100 iteraciones de prueba y tráeme resultados (escenas, superficies con campo, tabla de reportes, convergencia y RESUMEN.md provisional), ` +
      `y pregúntame antes de seguir hasta el criterio de parada. Guarda al terminar cada etapa.` +
      (notas ? ` Notas: ${notas}` : '');
    sendChat();
  } catch (err) { $('nc_prog').textContent = 'No se pudo: ' + err.message; }
  $('ncok').disabled = false;
};
async function refreshCaseList() {  // un caso creado por Claude en el chat aparece sin F5
  try {
    const cs = await api('/api/cases'); if (cs.length === st.cases.length && cs.every((c, i) => c.name === st.cases[i].name)) return;
    st.cases = cs; const sel = $('case'); fillCaseSelect(cs);
    sel.value = cs.some(c => c.name === st.case) ? st.case : (cs[0]?.name || '');
  } catch {}
}
let openGen = 0;
async function openCase(name) {
  const gen = ++openGen; let d;
  try { d = await api('/api/cases/' + encodeURIComponent(name)); }
  catch (e) { if (gen === openGen) { toast('No pude abrir el caso: ' + e.message, 'error'); $('case').value = st.case || ''; } return; }
  if (gen !== openGen) return;  // llegó otra apertura después: esta respuesta ya no vale
  st.case = name; LS.set('scc_case', name); st.data = d;
  $('simname').textContent = `Simulación: ${d.title || d.name} · sims/${d.name}.sim`;
  $('bconv').textContent = d.convergencia ? d.convergencia.rows.length : '';
  $('resumen').innerHTML = d.resumen ? md(d.resumen) : '<p class="mut">Este caso no tiene RESUMEN.md</p>';
  renderScenes(d); renderConv(d); fillParams(d); renderOutline();
  await loadDatasets();
  loadRoles(); renderOutline();
  if (gen === openGen) loadTree(false);
}

// ---------------------------------------------------------------- dónde corre la simulación: Local (este PC) o Servidor (Linux)
// La elección vive en starccm/.ui-settings.json (GET/POST /api/settings), no en localStorage: Claude puede leerla.
async function loadSettings() {
  try { st.settings = await api('/api/settings'); st.where = st.settings.run_where; } catch (e) { st.settings = null; st.where = 'local'; }
  renderWhere();
}
function renderWhere() {
  for (const b of $('where').querySelectorAll('[role=radio]')) b.setAttribute('aria-checked', b.dataset.where === st.where);
  if (st.status.alive != null) renderStatus(st.status);
}
for (const b of $('where').querySelectorAll('[role=radio]')) b.onclick = async () => {
  if (b.dataset.where === st.where) return;
  try { st.settings = await api('/api/settings', { run_where: b.dataset.where }); st.where = st.settings.run_where; }
  catch (e) { toast('No pude guardar la elección: ' + e.message, 'error'); }
  renderWhere();
  const sv = st.settings?.server || {};
  toast(st.where === 'server' ? `La simulación correrá en ${sv.label || 'el servidor Linux'} ${sv.host || ''}` : 'La simulación corre en este PC (STAR-CCM+ 2410)', 'ok');
};
function whereRows() {  // filas del panel Solver
  const s = st.settings; if (!s) return [];
  if (st.where !== 'server') return [[['corre en', `Local (este PC) · STAR-CCM+ ${s.local.version} · np ${s.local.np}`], 'where']];
  const sv = s.server;
  return [[['corre en', `${sv.label}${sv.host ? ' ' + sv.host : ''} · STAR-CCM+ ${sv.version} · remoto listo`], 'where'],
    ...sv.rows.map(r => [r, 'srv'])];
}

// ---------------------------------------------------------------- visor 3D (three.js)
const V = { renderer: null, scene: null, camera: null, controls: null, group: null, meshes: [], raycaster: new THREE.Raycaster(),
  axes: null, axesCam: null, hot: null, anim: null, spin: false, bbox: null, clip: null, needs: true, wire: false, gen: 0, rolesMode: false };
function initViewer() {
  const canvas = $('gl');
  V.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  V.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  V.renderer.localClippingEnabled = true;
  V.scene = new THREE.Scene();
  V.camera = new THREE.PerspectiveCamera(40, 1, 0.001, 100);
  V.camera.position.set(0.5, 0.4, 0.6); V.camera.up.set(0, 1, 0);  // como el cliente de STAR-CCM+: Y arriba, se mira hacia −Z
  V.controls = new OrbitControls(V.camera, canvas);
  V.controls.enableDamping = true; V.controls.dampingFactor = 0.08; V.controls.screenSpacePanning = true;
  V.controls.addEventListener('change', () => { V.needs = true; });
  const hemi = new THREE.HemisphereLight(0xffffff, 0x6f7f90, 0.55);
  V.key = new THREE.DirectionalLight(0xffffff, 1.6);   // «faro»: va con la cámara (se recoloca en cada fotograma)
  V.rim = new THREE.DirectionalLight(0xffffff, 0.35);  // contraluz desde detrás para recortar la silueta
  V.scene.add(hemi, V.key, V.key.target, V.rim, V.rim.target);
  V.group = new THREE.Group(); V.scene.add(V.group);
  V.clip = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
  // tríada de ejes en la esquina (escena aparte, misma orientación que la cámara)
  V.axes = new THREE.Scene();
  const mk = (dir, col) => { const a = new THREE.ArrowHelper(new THREE.Vector3(...dir), new THREE.Vector3(), 0.8, col, 0.25, 0.12); V.axes.add(a); };
  mk([1, 0, 0], 0xd62828); mk([0, 1, 0], 0x2a9d3f); mk([0, 0, 1], 0x1d6fd1);
  V.axesCam = new THREE.PerspectiveCamera(40, 1, 0.1, 10);
  new ResizeObserver(resize).observe($('viewer'));
  resize();
  canvas.addEventListener('webglcontextlost', e => e.preventDefault());
  canvas.addEventListener('webglcontextrestored', () => { V.needs = true; });
  canvas.addEventListener('pointermove', onHover);
  canvas.addEventListener('pointerleave', () => { $('vtip').hidden = true; setHot(null); });
  canvas.addEventListener('dblclick', e => { const hit = pick(e); if (hit) flyTo(hit.object.userData.part); });
  let down = null;  // clic «limpio» (sin arrastrar para orbitar) en modo Fronteras: menú del papel de esa cara
  canvas.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
  canvas.addEventListener('pointerup', e => {
    if (!V.rolesMode || !down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4 || e.button !== 0) return;
    const hit = pick(e); if (hit) openRoleMenu(hit.object.userData.part, e.clientX, e.clientY); else $('rolemenu').hidden = true;
  });
  requestAnimationFrame(loop);
}
function resize() {
  const el = $('viewer'); const w = el.clientWidth, h = el.clientHeight; if (!w || !h) return;
  V.renderer.setSize(w, h, false); V.camera.aspect = w / h; V.camera.updateProjectionMatrix(); V.needs = true;
}
function loop(t) {
  requestAnimationFrame(loop);
  if (st.view !== '3d') return;
  if (V.anim) { const k = Math.min(1, (t - V.anim.t0) / V.anim.ms); const e = 1 - Math.pow(1 - k, 3);
    V.camera.position.lerpVectors(V.anim.p0, V.anim.p1, e); V.controls.target.lerpVectors(V.anim.c0, V.anim.c1, e); V.needs = true; if (k >= 1) V.anim = null; }
  if (V.rotor && V.spinRig) {  // cada marco rotatorio gira sus superficies sobre SU eje y SU centro
    for (const rig of V.spinRig) {
      const a = t * 0.001 * 0.25 * Math.PI * 2 * rig.sign, q = new THREE.Quaternion().setFromAxisAngle(rig.axis, a);
      const off = rig.origin.clone().sub(rig.origin.clone().applyQuaternion(q));  // p' = o + R(p − o)
      for (const m of rig.meshes) { m.quaternion.copy(q); m.position.copy(off); }
    }
    V.needs = true; }
  V.controls.autoRotate = V.spin; if (V.spin) V.needs = true;
  V.controls.update();
  if (!V.needs) return;
  V.needs = false;
  const view = V.camera.position.clone().sub(V.controls.target), right = new THREE.Vector3().crossVectors(view, V.camera.up).normalize();
  V.key.position.copy(V.camera.position).addScaledVector(V.camera.up, view.length() * 0.35).addScaledVector(right, -view.length() * 0.25); V.key.target.position.copy(V.controls.target);
  V.rim.position.copy(V.controls.target).sub(view); V.rim.target.position.copy(V.controls.target);
  const r = V.renderer; const w = $('viewer').clientWidth, h = $('viewer').clientHeight;
  r.setViewport(0, 0, w, h); r.setScissorTest(false); r.render(V.scene, V.camera);
  // tríada
  const s = 76; V.axesCam.position.copy(V.camera.position).sub(V.controls.target).normalize().multiplyScalar(3); V.axesCam.up.copy(V.camera.up); V.axesCam.lookAt(0, 0, 0);
  r.setViewport(8, 8, s, s); r.setScissor(8, 8, s, s); r.setScissorTest(true); r.autoClear = false; r.render(V.axes, V.axesCam); r.autoClear = true; r.setScissorTest(false);
}
const fitDist = (size, k) => size / (2 * Math.tan(V.camera.fov * Math.PI / 360)) * k;  // distancia a la que `size` llena el cuadro
function fit(ms = 600) {
  if (!V.bbox || V.bbox.isEmpty()) return;
  const c = V.bbox.getCenter(new THREE.Vector3()), size = V.bbox.getSize(new THREE.Vector3()).length();
  const dir = V.camera.position.clone().sub(V.controls.target).normalize();
  if (!dir.length()) dir.set(0.55, 0.45, 0.7);
  tween(c.clone().add(dir.multiplyScalar(fitDist(size, 1.15))), c, ms);
  V.camera.near = size / 500; V.camera.far = size * 20; V.camera.updateProjectionMatrix();
}
function tween(p1, c1, ms = 600) {
  V.anim = { t0: performance.now(), ms, p0: V.camera.position.clone(), p1, c0: V.controls.target.clone(), c1 };
}
function setView(name) {
  if (!V.bbox) return;
  const c = V.bbox.getCenter(new THREE.Vector3()), size = V.bbox.getSize(new THREE.Vector3()).length();
  const dist = fitDist(size, 1.15);
  const dir = { iso: [0.55, 0.45, 0.7], axial: [0, 0, 1], lateral: [1, 0, 0] }[name];
  V.camera.up.set(0, 1, 0);  // las vistas fijas reponen el «arriba» (el orbitado libre no lo cambia)
  tween(c.clone().add(new THREE.Vector3(...dir).normalize().multiplyScalar(dist)), c);
}
function flyTo(part) {
  if (!part) return;
  // una superficie oculta tras la carcasa opaca: se activa la carcasa translúcida y se avisa
  if (!part.mesh.visible) { part.mesh.visible = true; const cb = part.li?.querySelector('input'); if (cb) cb.checked = true; if (part.group) syncGroup(part.group); }
  if (!V.ghost && !OUTER.test(part.name) && st.ds.parts.some(q => OUTER.test(q.name) && q.mesh.visible)) {
    V.ghost = true; LS.set('scc_ghost', '1'); applyGhost(); toast(`Carcasa translúcida para ver ${part.name}`, 'ok');
  }
  const m = part.mesh; m.geometry.computeBoundingBox(); const b = m.geometry.boundingBox.clone().applyMatrix4(m.matrixWorld);
  const c = b.getCenter(new THREE.Vector3()), size = Math.max(b.getSize(new THREE.Vector3()).length(), V.bbox.getSize(new THREE.Vector3()).length() / 8);
  const dir = V.camera.position.clone().sub(V.controls.target).normalize();
  tween(c.clone().add(dir.multiplyScalar(fitDist(size, 1.3))), c, 700);
}
function pick(e) {
  const r = $('gl').getBoundingClientRect();
  const p = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  V.raycaster.setFromCamera(p, V.camera);
  let hits = V.raycaster.intersectObjects(V.meshes.filter(m => m.visible), false);
  if (V.clip && $('clipon').checked) hits = hits.filter(h => V.clip.distanceToPoint(h.point) >= 0);  // lo cortado no se ve
  return hits.find(h => h.object.material.opacity >= 1) || hits[0] || null;  // lo opaco manda sobre la carcasa translúcida
}
let hoverE = null;
function onHover(e) {  // un solo raycast por fotograma y ninguno mientras se orbita
  if (st.view !== '3d' || !V.meshes.length || e.buttons) return;
  const first = !hoverE; hoverE = e; if (first) requestAnimationFrame(doHover);
}
function doHover() {
  const e = hoverE; hoverE = null; if (!e || !V.meshes.length) return;
  const hit = pick(e);
  const tip = $('vtip');
  if (!hit) { tip.hidden = true; setHot(null); return; }
  const part = hit.object.userData.part; setHot(part);
  let val = '';
  if (st.scalar && st.ds?.scal[st.scalar]) {
    const a = st.ds.scal[st.scalar]; const i = part.v0 + hit.face.a; const v = a[i];
    val = ` · <b>${sci(v)}</b>${unitOf(st.scalar)}`;
  }
  tip.innerHTML = `${esc(part.name)}${val}`;
  const r = $('viewer').getBoundingClientRect();
  tip.style.left = (e.clientX - r.left + 12) + 'px'; tip.style.top = (e.clientY - r.top + 12) + 'px'; tip.hidden = false;
}
function setHot(part) {
  if (V.hot === part) return;
  if (V.hot) { V.hot.mesh.material.emissive.setHex(0); V.hot.li?.classList.remove('hot'); }
  V.hot = part;
  if (part) { part.mesh.material.emissive.setHex(0x335577); part.mesh.material.emissiveIntensity = 0.25; part.li?.classList.add('hot'); }
  V.needs = true;
}
const unitOf = n => /pressure/i.test(n) ? ' Pa' : /velocity/i.test(n) ? ' m/s' : /shear/i.test(n) ? ' Pa' : '';
// nombres internos de STAR-CCM+ -> etiqueta legible (lo que no está aquí se muestra tal cual)
const LABELS = { Pressure: 'Presión', TotalPressure: 'Presión total', VelocityMagnitude: '|Velocidad|', 'Velocity |mag|': '|Velocidad|', WallY: 'y+', WallYplus: 'y+', WallShearStressMagnitude: '|Esfuerzo cortante|', AbsolutePressure: 'Presión absoluta', Temperature: 'Temperatura' };
const labelOf = n => LABELS[n] || n;
const ROTOR = /blade|hub|impeller|rotor/i;  // partes que gira el botón «Rotor» (solo animación, eje Z)
const OUTER = /shroud|casing|volute|voluta|spiral|diffuser|cutwater|carcasa|housing|outer|wall$/i;  // superficies que tapan los álabes

// ---------------------------------------------------------------- superficies con campo (dataset de surfaces.py)
const PART_COLORS = [0x7f9fc0, 0xc9a66b, 0x8fb98f, 0xb48ead, 0xd08770, 0x88c0d0, 0xa3be8c, 0xebcb8b];
const CMAPS = {
  ccm: [[0, 0, 1], [0, 1, 1], [0, 1, 0], [1, 1, 0], [1, 0, 0]],
  viridis: [[0.267, 0.005, 0.329], [0.283, 0.141, 0.458], [0.254, 0.265, 0.530], [0.207, 0.372, 0.553], [0.164, 0.471, 0.558], [0.128, 0.567, 0.551], [0.135, 0.659, 0.518], [0.267, 0.749, 0.441], [0.478, 0.821, 0.318], [0.741, 0.873, 0.150], [0.993, 0.906, 0.144]],
  gray: [[0.15, 0.15, 0.15], [0.95, 0.95, 0.95]],
};
function cmapColor(t, out) {
  const stops = CMAPS[st.cmap] || CMAPS.ccm; t = Math.max(0, Math.min(1, t)); const x = t * (stops.length - 1); const i = Math.min(stops.length - 2, Math.floor(x)); const f = x - i;
  out[0] = stops[i][0] + (stops[i + 1][0] - stops[i][0]) * f; out[1] = stops[i][1] + (stops[i + 1][1] - stops[i][1]) * f; out[2] = stops[i][2] + (stops[i + 1][2] - stops[i][2]) * f;
  return out;
}
async function loadDatasets() {
  if (!st.case) { clearDataset(); return; }
  const had = st.ds && st.ds.case === st.case ? { name: st.ds.name, mtime: st.ds.mtime } : null;
  try { st.datasets = (await api('/api/surfaces?case=' + encodeURIComponent(st.case))).datasets; }
  catch (e) { toast('No pude listar las superficies: ' + e.message, 'error'); return; }
  const dsel = $('datasets');
  $('b-geo').textContent = st.datasets.length || '';
  if (!st.datasets.length) { clearDataset(); dsel.innerHTML = 'Sin superficies exportadas.'; syncOverlays(); return; }
  dsel.innerHTML = `<select id="dsel" aria-label="Dataset">${st.datasets.map(d => `<option value="${esc(d.name)}">${esc(d.name)} · ${new Date(d.mtime * 1000).toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</option>`).join('')}</select>`;
  // por defecto el más nuevo que no sea «demo» (el sintético de prueba), salvo preferencia guardada
  const want = LS.get('scc_ds_' + st.case);
  const pick = (want && want !== 'demo' && st.datasets.find(d => d.name === want)) || st.datasets.find(d => d.name !== 'demo') || st.datasets[0];
  $('dsel').value = pick.name; $('dsel').onchange = () => loadDataset(st.datasets.find(d => d.name === $('dsel').value));
  // tras un chat la página se refresca: si el dataset es el mismo (nombre y fecha) no se recarga ni se pierde el encuadre
  if (had && had.name === pick.name && had.mtime === pick.mtime) { syncOverlays(); return; }
  await loadDataset(pick, !!had && had.name === pick.name);
  if (had && had.name === pick.name) toast('Superficies actualizadas', 'ok');
}
function clearDataset() {
  for (const m of V.meshes) { V.group.remove(m); m.geometry.dispose(); m.material.dispose(); const e = m.userData.part?.edges; if (e) { e.geometry.dispose(); e.material.dispose(); } }
  setHot(null); V.meshes = []; st.ds = null; V.bbox = null; $('parts').innerHTML = ''; $('vstate').textContent = ''; $('vtip').hidden = true;
  $('rmin').value = ''; $('rmax').value = ''; st.scalar = ''; st.range = null; V.rotor = false; $('rotor').setAttribute('aria-pressed', false);
  $('scalar').innerHTML = '<option value="">(geometría)</option>'; V.needs = true; syncOverlays();
}
// una sola función decide qué capas se ven sobre el visor según la vista (3D o escena PNG) y si hay dataset
function syncOverlays() {
  const is3d = st.view === '3d';
  $('vtools').hidden = !is3d; $('vactions').hidden = !is3d;
  // sin superficies (caso vacío) la barra del visor se apaga: nada de valores del caso anterior
  for (const id of ['vtools', 'vactions']) { $(id).classList.toggle('off', !st.ds); for (const c of $(id).querySelectorAll('button,select,input')) c.disabled = !st.ds; }
  if (st.ds && !st.scalar) for (const id of ['rmin', 'rmax', 'cmap', 'rauto']) $(id).disabled = true;
  $('legend').hidden = !is3d || !st.ds || !st.scalar || V.rolesMode;  // en modo Fronteras los colores son papeles, no campo
  $('chips').hidden = !st.ds || !st.data?.pump;  // sugerencias del visor: sin superficies no aplican
  $('vempty').hidden = !is3d || !!st.ds || !$('vbusy').hidden;
  if (!is3d) { $('vtip').hidden = true; setHot(null); }
  $('vhint').hidden = !(is3d && st.ds && NARROW.matches && !V.controls.enableZoom);
}
// keep = mantener cámara, corte y visibilidad por nombre de parte (recarga tras un chat); si no, encuadrar
async function loadDataset(d, keep = false) {
  const prev = keep && st.ds ? { pos: V.camera.position.clone(), tgt: V.controls.target.clone(), hidden: new Set(st.ds.parts.filter(p => !p.mesh.visible).map(p => p.name)) } : null;
  const gen = ++V.gen; clearDataset(); LS.set('scc_ds_' + st.case, d.name);
  $('vbusy').hidden = false; $('vbusytxt').textContent = `cargando ${d.name}…`; $('vempty').hidden = true;
  try {
    const man = d.manifest;
    const buf = async u => { const r = await fetch(u); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'HTTP ' + r.status); return r.arrayBuffer(); };
    const [pos, idx] = await Promise.all([buf(`${d.url}/positions.f32?v=${d.mtime}`), buf(`${d.url}/indices.u32?v=${d.mtime}`)]);
    const P = new Float32Array(pos), I = new Uint32Array(idx);
    if (P.length !== man.n_vertices * 3 || I.length !== man.n_triangles * 3) throw new Error('los archivos no coinciden con el manifest (¿se está reescribiendo?)');
    const scal = {};
    await Promise.all(man.scalars.map(async s => { scal[s.name] = new Float32Array(await buf(`${d.url}/${s.file}?v=${d.mtime}`)); }));
    if (gen !== V.gen) return;  // otra carga empezó mientras tanto
    st.ds = { ...d, case: st.case, P, I, scal, parts: [] };
    V.bbox = new THREE.Box3();
    man.parts.forEach((p, k) => {
      if (!p.ni) return;
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(P.subarray(p.v0 * 3, (p.v0 + p.nv) * 3), 3));
      const li = new Uint32Array(p.ni); for (let i = 0; i < p.ni; i++) li[i] = I[p.i0 + i] - p.v0;
      g.setIndex(new THREE.BufferAttribute(li, 1));
      g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(p.nv * 3), 3));
      g.computeVertexNormals(); g.computeBoundingBox(); V.bbox.union(g.boundingBox);
      const mat = new THREE.MeshStandardMaterial({ vertexColors: true, side: THREE.DoubleSide, roughness: 0.45, metalness: 0.1, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1, clippingPlanes: $('clipon').checked ? [V.clip] : [], transparent: true, opacity: 0 });
      const mesh = new THREE.Mesh(g, mat); const part = { ...p, mesh, color: PART_COLORS[k % PART_COLORS.length], k };
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(g, 30), new THREE.LineBasicMaterial({ color: 0x1b2430, transparent: true, opacity: 0.55, clippingPlanes: mat.clippingPlanes }));
      mesh.add(edges); part.edges = edges;
      mesh.userData.part = part; V.group.add(mesh); V.meshes.push(mesh); st.ds.parts.push(part);
    });
    if (!V.meshes.length) throw new Error('el dataset no tiene triángulos');
    $('scalar').innerHTML = '<option value="">(geometría)</option>' + man.scalars.map(s => `<option value="${esc(s.name)}">${esc(labelOf(s.name))}</option>`).join('');
    const ws = LS.get('scc_scalar'); st.scalar = man.scalars.some(s => s.name === ws) ? ws : (man.scalars[0]?.name || '');
    $('scalar').value = st.scalar; st.range = null;
    renderParts(); applyColors(); applyGhost(); updateClip();
    if (prev) { V.camera.position.copy(prev.pos); V.controls.target.copy(prev.tgt); for (const p of st.ds.parts) if (prev.hidden.has(p.name)) { p.mesh.visible = false; p.li.querySelector('input').checked = false; } for (const g of st.groups || []) syncGroup(g); }
    else { fit(0); setView('iso'); }
    $('vstate').textContent = `${man.n_triangles.toLocaleString('es')} triángulos · ${st.ds.parts.length} superficies${st.ds.parts.length < man.parts.length ? ` (+${man.parts.length - st.ds.parts.length} vacías)` : ''}${man.exported ? ' · ' + man.exported : ''}`;
    fadeIn();
  } catch (e) { if (gen !== V.gen) return; toast('No pude cargar las superficies: ' + e.message, 'error'); clearDataset(); }
  if (gen !== V.gen) return;
  $('vbusy').hidden = true; syncOverlays();
}
function fadeIn() {  // las superficies aparecen suaves
  const t0 = performance.now();
  const step = t => { const k = Math.min(1, (t - t0) / 500); for (const m of V.meshes) m.material.opacity = k * targetOpacity(m.userData.part); V.needs = true; if (k < 1) requestAnimationFrame(step); else applyGhost(); };
  requestAnimationFrame(step);
}
// «Carcasa translúcida»: las superficies exteriores (voluta, shroud, casing) al 25 % para ver los álabes
const targetOpacity = p => (V.ghost && OUTER.test(p.name) && st.ds?.parts.some(q => !OUTER.test(q.name))) ? 0.25 : 1;
function applyGhost() {
  if (!st.ds) return;
  for (const p of st.ds.parts) { const o = targetOpacity(p); p.mesh.material.transparent = o < 1; p.mesh.material.opacity = o; p.mesh.material.depthWrite = o >= 1; p.mesh.renderOrder = o < 1 ? 1 : 0; p.mesh.material.needsUpdate = true; if (p.edges) p.edges.material.opacity = 0.55 * o; }
  $('ghost').setAttribute('aria-pressed', V.ghost); V.needs = true;
}
// Región de cada superficie: manifest.boundaries trae «región/frontera» en el mismo orden que las partes del EnSight
// (se usa por índice si cuadra; si no, por nombre; lo que no casa va a «Otras»)
function regionOf(parts, bounds) {
  const out = new Map();
  if (bounds && bounds.length === st.ds.manifest.parts.length) {
    const byName = new Map(st.ds.manifest.parts.map((mp, i) => [mp.name, bounds[i]]));
    for (const p of parts) { const b = byName.get(p.name); out.set(p, b && b.includes('/') ? b.split('/')[0] : 'Otras'); }
    return out;
  }
  for (const p of parts) { const b = (bounds || []).find(x => x.split('/').slice(1).join('/') === p.name); out.set(p, b ? b.split('/')[0] : 'Otras'); }
  return out;
}
function syncGroup(g) {  // la casilla de la región refleja a sus hijas: marcada, vacía o indeterminada
  const n = g.parts.filter(p => p.mesh.visible).length;
  g.cb.checked = n === g.parts.length; g.cb.indeterminate = n > 0 && n < g.parts.length;
  g.count.textContent = `${n}/${g.parts.length}`;
}
function renderParts() {
  const ul = $('parts'); ul.innerHTML = '';
  const reg = regionOf(st.ds.parts, st.ds.manifest.boundaries);
  const groups = new Map();
  for (const p of st.ds.parts) { const r = reg.get(p); if (!groups.has(r)) groups.set(r, []); groups.get(r).push(p); }
  const open = new Set(JSON.parse(LS.get('scc_open_regions', '[]')));
  st.groups = [];
  for (const [name, parts] of groups) {
    const li = document.createElement('li'); li.className = 'grp';
    const det = document.createElement('details'); det.open = open.has(name);
    det.innerHTML = `<summary title="${esc(name)} · clic en la flecha: ver sus superficies · casilla: ocultar o mostrar toda la región"><input type="checkbox" checked aria-label="ver región ${esc(name)}"><span class="n">${esc(name)}</span><span class="c"></span></summary><ul class="parts sub"></ul>`;
    const g = { name, parts, cb: det.querySelector('input'), count: det.querySelector('.c') };
    g.cb.onclick = e => e.stopPropagation();  // la casilla no pliega ni despliega
    g.cb.onchange = () => { for (const p of parts) { p.mesh.visible = g.cb.checked; p.li.querySelector('input').checked = g.cb.checked; } syncGroup(g); V.needs = true; };
    det.ontoggle = () => { const s2 = new Set(JSON.parse(LS.get('scc_open_regions', '[]'))); det.open ? s2.add(name) : s2.delete(name); LS.set('scc_open_regions', JSON.stringify([...s2])); };
    det.querySelector('summary').onmouseenter = () => { for (const p of parts) p.mesh.material.emissive.setHex(0x335577); V.needs = true; };
    det.querySelector('summary').onmouseleave = () => { for (const p of parts) if (p !== V.hot) p.mesh.material.emissive.setHex(0); V.needs = true; };
    li.appendChild(det); ul.appendChild(li);
    for (const p of parts) { p.group = g; renderPart(p, det.querySelector('ul')); }
    syncGroup(g); st.groups.push(g);
  }
}
function renderPart(p, ul) {
  const li = document.createElement('li'); p.li = li; li.tabIndex = 0; li.setAttribute('role', 'option'); li.title = `${p.name} · clic o Enter: volar a la superficie`;
  li.innerHTML = `<input type="checkbox" checked aria-label="ver ${esc(p.name)}"><span class="sw" style="background:#${p.color.toString(16).padStart(6, '0')}"></span><span class="n">${esc(p.name)}</span><span class="rb"></span><span class="c">${(p.ni / 3).toLocaleString('es')}</span>`;
  paintRoleBadge(p);
  li.querySelector('input').onchange = e => { p.mesh.visible = e.target.checked; if (p.group) syncGroup(p.group); V.needs = true; };
  li.onclick = e => { if (e.target.tagName !== 'INPUT') flyTo(p); };
  li.onkeydown = e => { if (e.key === 'Enter') flyTo(p); else if (e.key === ' ') { e.preventDefault(); const c = li.querySelector('input'); c.checked = !c.checked; c.onchange({ target: c }); } };
  li.onmouseenter = () => setHot(p); li.onmouseleave = () => setHot(null);
  ul.appendChild(li);
}
function applyColors(anim = false) {
  if (!st.ds) return;
  const from = anim && !matchMedia('(prefers-reduced-motion: reduce)').matches ? st.ds.parts.map(p => Float32Array.from(p.mesh.geometry.getAttribute('color').array)) : null;
  const a = st.scalar ? st.ds.scal[st.scalar] : null;
  const meta = st.ds.manifest.scalars.find(s => s.name === st.scalar);
  let lo = meta?.min ?? 0, hi = meta?.max ?? 1;
  if (st.range) { lo = st.range[0]; hi = st.range[1]; }
  $('rmin').value = a ? +lo.toPrecision(5) : ''; $('rmax').value = a ? +hi.toPrecision(5) : '';
  for (const id of ['rmin', 'rmax', 'cmap', 'rauto']) $(id).disabled = !a;  // en modo (geometría) no hay campo que escalar
  const c = [0, 0, 0];
  for (const p of st.ds.parts) {
    const col = p.mesh.geometry.getAttribute('color'); const arr = col.array;
    if (V.rolesMode || !a) { const base = new THREE.Color(V.rolesMode ? (ROLE_COLOR[roleOf(p)] ?? 0xc9d1da) : p.color); for (let i = 0; i < p.nv; i++) { arr[3 * i] = base.r; arr[3 * i + 1] = base.g; arr[3 * i + 2] = base.b; } }
    else for (let i = 0; i < p.nv; i++) { const v = a[p.v0 + i]; if (!Number.isFinite(v)) { arr[3 * i] = arr[3 * i + 1] = arr[3 * i + 2] = 0.6; continue; } cmapColor((v - lo) / ((hi - lo) || 1), c); arr[3 * i] = c[0]; arr[3 * i + 1] = c[1]; arr[3 * i + 2] = c[2]; }
    col.needsUpdate = true;
  }
  drawLegend(a && !V.rolesMode ? st.scalar : null, lo, hi); V.needs = true;
  if (from) {  // transición de 400 ms entre el color anterior y el nuevo
    const gen = V.gen, tgt = st.ds.parts.map(p => Float32Array.from(p.mesh.geometry.getAttribute('color').array)), t0 = performance.now();
    st.ds.parts.forEach((p, i) => p.mesh.geometry.getAttribute('color').array.set(from[i]));
    const step = t => { if (gen !== V.gen || !st.ds) return; const k = Math.min(1, (t - t0) / 400), e = k * (2 - k);
      st.ds.parts.forEach((p, i) => { const col = p.mesh.geometry.getAttribute('color'), arr = col.array; for (let j = 0; j < arr.length; j++) arr[j] = from[i][j] + (tgt[i][j] - from[i][j]) * e; col.needsUpdate = true; });
      V.needs = true; if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
}
function drawLegend(name, lo, hi) {
  syncOverlays(); if (!name) return;
  $('lgtitle').textContent = labelOf(name) + (unitOf(name) ? ` (${unitOf(name).trim()})` : '');
  const cv = $('lgbar'), ctx = cv.getContext('2d'); const c = [0, 0, 0];
  for (let y = 0; y < cv.height; y++) { cmapColor(1 - y / (cv.height - 1), c); ctx.fillStyle = `rgb(${c[0] * 255 | 0},${c[1] * 255 | 0},${c[2] * 255 | 0})`; ctx.fillRect(0, y, cv.width, 1); }
  // un único formato para todas las marcas del eje (científico si algún valor es muy grande o pequeño)
  const m = Math.max(Math.abs(lo), Math.abs(hi)), sc = m >= 1e5 || (m > 0 && m < 1e-2), dec = hi - lo >= 100 ? 0 : hi - lo >= 10 ? 1 : hi - lo >= 1 ? 2 : 3;
  $('lgticks').innerHTML = [1, 0.75, 0.5, 0.25, 0].map(t => { const v = lo + (hi - lo) * t; return `<span>${(sc ? v.toExponential(2) : v.toFixed(dec)).replace('.', ',')}</span>`; }).join('');
}
$('scalar').onchange = () => { st.scalar = $('scalar').value; LS.set('scc_scalar', st.scalar); st.range = null; applyColors(true); };
$('cmap').value = st.cmap; $('cmap').onchange = () => { st.cmap = $('cmap').value; LS.set('scc_cmap', st.cmap); applyColors(); };
const setRange = () => { const a = parseFloat($('rmin').value), b = parseFloat($('rmax').value); if (Number.isFinite(a) && Number.isFinite(b) && b > a) { st.range = [a, b]; applyColors(); } else { toast('Máx debe ser mayor que Mín', 'warn'); applyColors(); } };
$('rmin').onchange = setRange; $('rmax').onchange = setRange;
$('rauto').onclick = () => { st.range = null; applyColors(); };
for (const b of $('vactions').querySelectorAll('[data-view]')) b.onclick = () => setView(b.dataset.view);
$('fit').onclick = () => fit();
$('spin').onclick = () => { V.spin = !V.spin; $('spin').setAttribute('aria-pressed', V.spin); };
V.ghost = LS.get('scc_ghost', '1') === '1';
$('ghost').onclick = () => { V.ghost = !V.ghost; LS.set('scc_ghost', V.ghost ? '1' : '0'); applyGhost(); };
// Qué gira y sobre qué eje, para cualquier turbomáquina:
// 1) manifest.rotation (marcos rotatorios leídos de STAR-CCM+ al exportar: región, eje, origen, rpm);
// 2) si no, las regiones cuyo nombre indica rotor (rotor, impeller, runner, rodete…) o, sin regiones, las superficies con
//    nombre de rotor; eje = el de menor espesor de su caja (disco de una bomba centrífuga) salvo que sea casi cúbica,
//    entonces Z (convención de CFturbo); centro = centro de la caja de ESAS superficies (no de toda la máquina).
const ROTOR_REGION = /rotor|impell|runner|rodete|rotating|rotat|blade_row|wheel/i;
function rotorRigs() {
  const parts = st.ds.parts, rot = st.ds.manifest.rotation || [];
  if (rot.length) return rot.map(r => ({ meshes: parts.filter(p => p.group && p.group.name === r.region).map(p => p.mesh),
    axis: new THREE.Vector3(...r.axis).normalize(), origin: new THREE.Vector3(...r.origin), sign: Math.sign(r.rpm) || 1, rpm: r.rpm, from: 'STAR-CCM+' })).filter(r => r.meshes.length);
  let sel = parts.filter(p => p.group && ROTOR_REGION.test(p.group.name));
  if (!sel.length) sel = parts.filter(p => ROTOR.test(p.name));
  if (!sel.length) return [];
  const box = new THREE.Box3(); for (const p of sel) { p.mesh.geometry.computeBoundingBox(); box.union(p.mesh.geometry.boundingBox); }
  const size = box.getSize(new THREE.Vector3()), dims = [size.x, size.y, size.z], k = dims.indexOf(Math.min(...dims));
  const flat = Math.min(...dims) < 0.7 * Math.max(...dims);
  const axis = new THREE.Vector3(0, 0, 0).setComponent(flat ? k : 2, 1);
  const rpm = parseFloat(String(st.data?.params?.rpm ?? '').replace(',', '.'));
  return [{ meshes: sel.map(p => p.mesh), axis, origin: box.getCenter(new THREE.Vector3()), sign: Math.sign(rpm) || 1, rpm, from: 'estimado' }];
}
function setRotor(on) {
  V.rotor = on && !!st.ds; $('rotor').setAttribute('aria-pressed', V.rotor);
  for (const m of V.meshes) { m.quaternion.identity(); m.position.set(0, 0, 0); }
  V.spinRig = V.rotor ? rotorRigs() : null;
  if (V.rotor && !V.spinRig.length) { V.rotor = false; $('rotor').setAttribute('aria-pressed', false); toast('No encuentro superficies que giren (sin marco rotatorio en el dataset ni región rotor)', 'warn'); }
  else if (V.rotor) { const r = V.spinRig[0], ax = ['X', 'Y', 'Z'][[r.axis.x, r.axis.y, r.axis.z].map(Math.abs).indexOf(Math.max(...[r.axis.x, r.axis.y, r.axis.z].map(Math.abs)))];
    $('vstate').title = `Rotor: ${V.spinRig.length} marco(s), eje ${ax} (${r.from})${Number.isFinite(r.rpm) ? ', ' + r.rpm + ' rpm' : ''}`; }
  V.needs = true;
}
$('rotor').onclick = () => setRotor(!V.rotor);
// ---------------------------------------------------------------- modo Fronteras: el usuario dice qué cara es qué
// Papel por «región/frontera», guardado en cases/<caso>/fronteras.json (la IA lo usa tal cual al poner las condiciones).
const ROLE_COLOR = { inlet: 0x1d6fd1, outlet: 0xd1495b, wall: 0x8d99ae, interface: 0xe0a800, symmetry: 0x2a9d3f };
const ROLE_TXT = { inlet: 'Entrada', outlet: 'Salida', wall: 'Pared', interface: 'Interfaz', symmetry: 'Simetría' };
st.roles = {};
const roleKey = p => `${p.group?.name || ''}/${p.name}`;
const roleOf = p => st.roles[roleKey(p)];
function paintRoleBadge(p) {
  const b = p.li?.querySelector('.rb'); if (!b) return; const r = roleOf(p);
  b.textContent = r ? ROLE_TXT[r] : ''; b.className = 'rb' + (r ? ' r-' + r : '');
}
async function loadRoles() {
  st.roles = {}; if (!st.case) return;
  try { st.roles = (await api(`/api/cases/${encodeURIComponent(st.case)}/roles`)).roles || {}; } catch {}
  if (st.ds) { for (const p of st.ds.parts) paintRoleBadge(p); if (V.rolesMode) applyColors(); }
  renderRolesBar();
}
function setRolesMode(on) {
  V.rolesMode = on && !!st.ds; $('rolesbtn').setAttribute('aria-pressed', V.rolesMode); $('rolemenu').hidden = true;
  if (V.rolesMode && V.ghost) { V.ghost = false; applyGhost(); }  // en modo Fronteras todo opaco: se elige lo que se ve
  applyColors(); renderRolesBar();
  if (V.rolesMode) toast('Fronteras: haz clic en una cara y elige su papel. Doble clic sigue volando a ella.', 'ok');
}
function renderRolesBar() {
  let bar = $('rolesbar');
  if (!bar) { bar = document.createElement('div'); bar.id = 'rolesbar'; bar.className = 'rolesbar'; $('viewer').appendChild(bar); }
  bar.hidden = !V.rolesMode;
  if (!V.rolesMode) return;
  const n = r => Object.values(st.roles).filter(v => v === r).length;
  const ok = n('inlet') > 0 && n('outlet') > 0;
  bar.innerHTML = `<b>Fronteras</b>${['inlet', 'outlet', 'interface', 'wall', 'symmetry'].map(r => `<span class="chip-r"><i class="r-${r}"></i>${ROLE_TXT[r]} ${n(r)}</span>`).join('')}
    <span class="mut small">sin marcar = pared</span><span class="sp"></span>
    <button class="sm pri" id="rolesapply" ${ok ? '' : 'disabled title="Marca al menos una entrada y una salida"'}>Aplicar con la IA</button><button class="sm" id="rolesexit">Salir</button>`;
  $('rolesexit').onclick = () => setRolesMode(false);
  $('rolesapply').onclick = () => {
    if (busyChat()) return;
    const by = r => Object.entries(st.roles).filter(([, v]) => v === r).map(([k]) => k);
    const lst = r => by(r).join(', ') || '—';
    $('chattext').value = `En cases/${st.case} marqué en el visor el papel de cada frontera (cases/${st.case}/fronteras.json). ` +
      `Entrada: ${lst('inlet')}. Salida: ${lst('outlet')}. Interfaz: ${lst('interface')}. Simetría: ${lst('symmetry')}. El resto, paredes. ` +
      `Aplica exactamente esos tipos (entrada mass flow inlet con el caudal del caso, salida pressure outlet 0 Pa), revisa que las interfaces casen, ` +
      `reinicia la solución (clearSolution) y vuelve a iterar hasta el criterio escribiendo reports/convergencia.csv; si vuelve a divergir, para y dímelo.`;
    sendChat();
  };
}
function openRoleMenu(p, x, y) {
  const m = $('rolemenu'); $('rmname').textContent = roleKey(p); m.hidden = false;
  const r = m.getBoundingClientRect(); m.style.left = Math.min(x, innerWidth - r.width - 8) + 'px'; m.style.top = Math.min(y, innerHeight - r.height - 8) + 'px';
  for (const b of m.querySelectorAll('[data-role]')) b.onclick = async () => {
    m.hidden = true; const k = roleKey(p);
    if (b.dataset.role) st.roles[k] = b.dataset.role; else delete st.roles[k];
    paintRoleBadge(p); applyColors(); renderRolesBar();
    try { await api(`/api/cases/${encodeURIComponent(st.case)}/roles`, { roles: st.roles }); } catch (e) { toast('No pude guardar: ' + e.message, 'error'); }
  };
  m.querySelector('[data-role]').focus();
}
$('rolesbtn').onclick = () => setRolesMode(!V.rolesMode);
addEventListener('keydown', e => { if (e.key === 'Escape') $('rolemenu').hidden = true; });
$('wire').onclick = () => { V.wire = !V.wire; $('wire').setAttribute('aria-pressed', V.wire); for (const m of V.meshes) m.material.wireframe = V.wire; V.needs = true; };
function updateClip() {
  const on = $('clipon').checked; const ax = $('clipax').value; const t = +$('clipv').value / 1000;
  if (V.bbox) { const n = { X: [-1, 0, 0], Y: [0, -1, 0], Z: [0, 0, -1] }[ax]; const i = 'XYZ'.indexOf(ax);
    const v = V.bbox.min.getComponent(i) + (V.bbox.max.getComponent(i) - V.bbox.min.getComponent(i)) * t;
    V.clip.normal.set(...n); V.clip.constant = v; }
  for (const m of V.meshes) { m.material.clippingPlanes = on ? [V.clip] : []; m.material.needsUpdate = true; const e = m.userData.part?.edges; if (e) { e.material.clippingPlanes = m.material.clippingPlanes; e.material.needsUpdate = true; } }
  V.needs = true;
}
$('clipon').onchange = updateClip; $('clipax').onchange = updateClip; $('clipv').oninput = updateClip;
$('help').onclick = () => toast('Atajos: F encuadrar · 1 iso · 2 axial · 3 lateral · doble clic vuela a la superficie · ` pliega el dock · T pliega la simulación · C pliega la IA · B marca las fronteras · Esc cierra la imagen');
// en pantallas estrechas (apilado) la rueda debe desplazar la página, no hacer zoom: el zoom se activa al tocar el modelo
function narrowZoom() { V.controls.enableZoom = !NARROW.matches || !!V.zoomOn; syncOverlays(); }
$('gl').addEventListener('pointerdown', () => { if (NARROW.matches && !V.zoomOn) { V.zoomOn = true; narrowZoom(); } });
NARROW.addEventListener('change', () => { V.zoomOn = false; narrowZoom(); });

// exportar del solver
$('exportbtn').onclick = e => { e.preventDefault(); e.stopPropagation(); $('expdlg').showModal(); };
$('expcancel').onclick = () => $('expdlg').close();
$('expform').onsubmit = async e => {
  e.preventDefault(); $('expdlg').close();
  if (!st.status.alive) { toast('Hace falta un solver vivo: pide a la IA server_start con sims/' + st.case + '.sim', 'warn'); return; }
  const t0 = Date.now(); $('vbusy').hidden = false;
  const clock = setInterval(() => { $('vbusytxt').textContent = `exportando superficies del solver… ${Math.round((Date.now() - t0) / 1000)} s`; }, 500);
  try {
    const r = await api('/api/surface', { case: st.case, name: $('e_name').value.trim(), pattern: $('e_pat').value.trim(), funcs: $('e_fun').value.trim() });
    toast(`Superficies «${r.name}»: ${r.manifest.n_triangles.toLocaleString('es')} triángulos, ${r.manifest.scalars.length} campos en ${r.manifest.seconds} s`, 'ok');
    LS.set('scc_ds_' + st.case, r.name); await loadDatasets();
  } catch (err) { toast(err.message, 'error'); }
  clearInterval(clock); $('vbusy').hidden = true;
};

// ---------------------------------------------------------------- escenas PNG (pestañas sobre el visor)
function renderScenes(d) {
  const tabs = $('scenetabs'), ul = $('scenes');
  $('b-scenes').textContent = d.images.length || '';
  const url = im => `/files/${encodeURIComponent(d.name)}/images/${encodeURIComponent(im.file)}?v=${im.mtime}`;
  tabs.innerHTML = d.images.map(im => `<button role="tab" data-view="${esc(im.file)}" aria-selected="false" title="${esc(im.file)}">${esc(im.label)}</button>`).join('');
  ul.innerHTML = d.images.map(im => `<li data-f="${esc(im.file)}" role="option" tabindex="0"><span>${esc(im.label)}</span><button class="sm mini regen" data-n="${esc(im.file.replace(/\.png$/, ''))}" title="Volver a exportar desde el solver (export_scene)">↻</button></li>`).join('') || '<li class="mut">sin escenas en images/</li>';
  for (const b of [...tabs.querySelectorAll('[role=tab]'), ...ul.querySelectorAll('li[data-f]')]) {
    const f = b.dataset.view || b.dataset.f; const im = d.images.find(x => x.file === f);
    b.onclick = e => { if (e.target.classList.contains('regen')) return; showView(f, url(im)); };
    if (b.tagName === 'LI') b.onkeydown = e => { if (e.key === 'Enter') showView(f, url(im)); };
  }
  for (const b of ul.querySelectorAll('.regen')) b.onclick = async e => {
    e.stopPropagation(); b.disabled = true; b.textContent = '…';
    try { const r = await api('/api/scene', { name: b.dataset.n, case: d.name }); toast(`«${b.dataset.n}» exportada en ${r.seconds} s`, 'ok'); await openCase(d.name); showView(b.dataset.n + '.png'); }
    catch (err) { toast(err.message, 'warn'); b.disabled = false; b.textContent = '↻'; }
  };
  showView(st.view === '3d' ? '3d' : (d.images.some(i => i.file === st.view) ? st.view : '3d'));
}
function showView(v, src) {
  st.view = v;
  for (const b of document.querySelectorAll('.vtabs [role=tab]')) b.setAttribute('aria-selected', b.dataset.view === v);
  for (const li of $('scenes').querySelectorAll('li[data-f]')) li.setAttribute('aria-selected', li.dataset.f === v);
  const img = $('sceneimg'); const is3d = v === '3d';
  img.hidden = is3d; syncOverlays();
  if (!is3d) { const im = st.data?.images.find(x => x.file === v); if (im) img.src = src || `/files/${encodeURIComponent(st.case)}/images/${encodeURIComponent(im.file)}?v=${im.mtime}`; img.onclick = () => { $('lightbox').querySelector('img').src = img.src; $('lightbox').querySelector('.lb-cap').textContent = v; $('lightbox').hidden = false; }; }
  else V.needs = true;
}
document.querySelector('.vtabs [data-view="3d"]').onclick = () => showView('3d');
$('lightbox').onclick = () => { $('lightbox').hidden = true; };

// ---------------------------------------------------------------- árbol del .sim (inspect tree)
const KINDS = { solver: 'Solver', part: 'Partes', region: 'Regiones', boundary: 'Fronteras', physics: 'Física', model: 'Modelos', mesh_op: 'Operaciones de malla', mesher: 'Malladores', report: 'Reportes', monitor: 'Monitores', scene: 'Escenas', continuum: 'Continuos', interface: 'Interfaces' };
async function loadTree(refresh) {
  if (refresh) { $('treerefresh').disabled = true; $('treestate').textContent = 'leyendo del solver…'; $('n-sim').open = true; }
  let r; try { r = await api('/api/tree?case=' + encodeURIComponent(st.case || '') + (refresh ? '&refresh=1' : '')); } catch (e) { $('treestate').textContent = e.message; $('treerefresh').disabled = false; return; }
  $('treerefresh').disabled = false;
  if (!r.tree) { $('treestate').textContent = 'sin lectura: pulsa ↻ con el solver vivo (~10 s)'; $('simtree').innerHTML = ''; $('b-sim').textContent = ''; return; }
  const at = new Date(r.at * 1000);
  $('treestate').textContent = `${r.derived ? 'datos' : 'leído'} ${at.toDateString() === new Date().toDateString() ? 'a las ' + at.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }) : 'el ' + at.toLocaleString('es')}${r.derived ? ' · reconstruido del disco (sin solver; sin regiones ni modelos)' : r.from_disk ? ' · guardado' : ''}${r.alive ? '' : ' (solver apagado)'}`;
  $('b-sim').textContent = Object.values(r.tree).reduce((n, v) => n + v.length, 0);
  $('simtree').innerHTML = Object.entries(r.tree).map(([k, items]) => `<details><summary>${esc(KINDS[k] || k)} <span class="badge">${items.length}</span></summary><ul>${items.map(it => `<li><span>${esc(it.name)}</span>${it.type ? `<span class="t">${esc(it.type)}</span>` : ''}${it.value != null ? `<span class="v">${esc(it.value)}</span>` : ''}</li>`).join('')}</ul></details>`).join('');
}
$('treerefresh').onclick = e => { e.preventDefault(); e.stopPropagation(); loadTree(true); };

// ---------------------------------------------------------------- dock: salida, gráficos, resumen
function openTab(t) {
  st.tab = t; LS.set('scc_tab', t);
  for (const b of document.querySelectorAll('.dock-tabs [role=tab]')) b.setAttribute('aria-selected', b.dataset.tab === t);
  for (const id of ['out', 'plots', 'res', 'chat']) $('tab-' + id).hidden = id !== t;
  $('stage').classList.toggle('chat-open', t === 'chat');
  if (t === 'chat') $('stage').classList.remove('dock-collapsed');
  if (t === 'out') loadProgress();
}
for (const b of document.querySelectorAll('.dock-tabs [role=tab]')) b.onclick = () => openTab(b.dataset.tab);
// < 1100 px el chat vive en el dock (pestaña «Claude»); en escritorio vuelve a su columna
function placeChat() {
  const col = $('chatcol');
  if (NARROW.matches) { if (col.parentElement !== $('tab-chat')) $('tab-chat').appendChild(col); }
  else { if (col.parentElement !== $('app')) $('app').appendChild(col); if (st.tab === 'chat') openTab('out'); }
}
NARROW.addEventListener('change', placeChat);
$('docktoggle').onclick = () => { const c = $('stage').classList.toggle('dock-collapsed'); $('docktoggle').textContent = c ? '▴' : '▾'; };
(() => { let y0 = 0, h0 = 0; const rs = $('dockresize');
  rs.onpointerdown = e => { y0 = e.clientY; h0 = parseInt(getComputedStyle($('stage')).getPropertyValue('--dock-h')) || 230; rs.setPointerCapture(e.pointerId); };
  rs.onpointermove = e => { if (!rs.hasPointerCapture(e.pointerId)) return; const h = Math.max(34, Math.min(innerHeight * 0.7, h0 + (y0 - e.clientY))); $('stage').style.setProperty('--dock-h', h + 'px'); };
})();

function chart(x, y, label, unit) {
  const W = 420, H = 200, L = 52, R = 14, T = 16, B = 30;
  const xs = x.filter((_, i) => y[i] != null), ys = y.filter(v => v != null); if (!ys.length) return '';
  const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin0 = Math.min(...ys), ymax0 = Math.max(...ys);
  const pad = (ymax0 - ymin0 || Math.abs(ymax0) || 1) * 0.15, ymin = ymin0 - pad, ymax = ymax0 + pad;
  const sx = v => L + (xmax === xmin ? 0.5 : (v - xmin) / (xmax - xmin)) * (W - L - R), sy = v => T + (1 - (v - ymin) / (ymax - ymin)) * (H - T - B);
  const dec = Math.abs(ymax - ymin) < 2 ? 3 : Math.abs(ymax - ymin) < 20 ? 2 : 1;
  const grid = [0, 1 / 3, 2 / 3, 1].map(t => ymin + (ymax - ymin) * t).map(v => `<line x1="${L}" x2="${W - R}" y1="${sy(v)}" y2="${sy(v)}" class="grid"/><text x="${L - 6}" y="${sy(v) + 4}" class="tick" text-anchor="end">${fmt(v, dec)}</text>`).join('');
  const xt = [0, 0.2, 0.4, 0.6, 0.8, 1].map(t => xmin + (xmax - xmin) * t).filter((v, i, a) => xmax !== xmin || i === 0).map(v => `<text x="${sx(v)}" y="${H - 10}" class="tick" text-anchor="middle">${Math.round(v)}</text>`).join('');
  const path = xs.map((v, i) => `${i ? 'L' : 'M'}${sx(v).toFixed(1)},${sy(ys[i]).toFixed(1)}`).join(' ');
  const dots = xs.length > 200 ? '' : xs.map((v, i) => `<circle cx="${sx(v)}" cy="${sy(ys[i])}" r="4" class="pt"><title>iter ${v}: ${label} = ${fmt(ys[i], dec)} ${unit}</title></circle>`).join('');
  const last = `<text x="${sx(xs[xs.length - 1]) - 6}" y="${sy(ys[ys.length - 1]) - 8}" class="lbl" text-anchor="end">${fmt(ys[ys.length - 1], dec)} ${unit}</text>`;
  return `<figure class="chart"><figcaption>${esc(label)} <span class="mut">(${esc(unit)}) frente a iteración</span></figcaption><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)} frente a iteración">${grid}<line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" class="axis"/>${xt}<path d="${path}" class="line"/>${dots}${last}</svg></figure>`;
}
function renderConv(d) {
  const c = $('conv'), cv = d.convergencia;
  if (!cv || !cv.rows.length) { c.innerHTML = '<p class="mut">Sin reports/convergencia.csv. Pide a la IA que corra iteraciones y lo escriba.</p>'; return; }
  // un remallado reinicia el contador: se grafica y se juzga solo el último tramo (donde iter crece)
  const ik = cv.columns.indexOf('iter'); const iter0 = cv.rows.map((r, i) => ik < 0 ? i + 1 : r[ik]);
  let a0 = 0, segs = 1; for (let i = 1; i < iter0.length; i++) if (iter0[i] == null || iter0[i - 1] == null || iter0[i] <= iter0[i - 1]) { a0 = i; segs++; }
  const rows = cv.rows.slice(a0);
  const col = n => { const k = cv.columns.indexOf(n); return k < 0 ? null : rows.map(r => r[k]); };
  const it = ik < 0 ? rows.map((_, i) => a0 + i + 1) : col('iter');
  const units = { H: 'm', M: 'N·m' };
  const charts = ['H', 'M'].map(k => col(k) ? chart(it, col(k), k, units[k]) : '').join('');
  // criterio de CLAUDE.md: variación de H y M < 0,5 % en 100 iteraciones -> se compara la última fila con la de ≥ 100 iteraciones antes
  const last = it[it.length - 1]; let j = it.length - 2; while (j > 0 && last - it[j] < 100) j--;
  const span = j >= 0 ? last - it[j] : null;
  const delta = k => { const v = col(k); if (!v || j < 0 || !v[v.length - 1] || v[j] == null) return null; return Math.abs((v[v.length - 1] - v[j]) / v[v.length - 1] * 100); };
  const dH = delta('H'), dM = delta('M');
  const crit = dH != null ? `<p class="small">Últimas ${span} iteraciones (${it[j]} → ${last}): ΔH ${fmt(dH, 2)} % · ΔM ${fmt(dM, 2)} % ${dH < 0.5 && dM < 0.5 && span >= 100 ? '<span class="tag ok">convergido (&lt; 0,5 % en ≥ 100 iter)</span>' : span < 100 ? '<span class="tag warn">faltan iteraciones para juzgar (&lt; 100)</span>' : '<span class="tag warn">aún no (&gt; 0,5 %)</span>'}</p>` : '';
  const table = `<table class="data"><tr>${cv.columns.map(h => `<th>${esc(h)}</th>`).join('')}</tr>${cv.rows.map(r => '<tr>' + r.map((v, i) => `<td class="num">${v == null ? '–' : i === 0 ? v : sci(v)}</td>`).join('') + '</tr>').join('')}</table>`;
  const seg = segs > 1 ? `<p class="small mut">tramo ${segs} de ${segs} (reinicio del contador en la fila ${a0 + 1}: remallado)</p>` : '';
  c.innerHTML = `<div class="charts">${charts}</div>${seg}${crit}<details><summary>${esc(cv.file)} · ${cv.rows.length} filas</summary><div id="convtable"></div></details>`;
  c.querySelector('details').ontoggle = ev => { const t = $('convtable'); if (ev.target.open && t && !t.innerHTML) t.innerHTML = table; };
}

// salida (la «terminal»)
const prog = { key: '' };
const hlLine = l => { const c = /AGENT_ERROR|Exception|error|Error|FAIL/.test(l) ? 'err' : /AGENT_BEGIN|AGENT_END|Playing macro|SAVED|PNG |SCENE |CASE /.test(l) ? 'hl' : /complete|Server::start|converged/i.test(l) ? 'ok' : ''; return c ? `<span class="${c}">${esc(l)}</span>` : esc(l); };
async function loadProgress() {
  let p; try { p = await api('/api/progress'); } catch (e) { $('macrostate').textContent = e.message; return; }
  const m = p.macro; $('progdot').hidden = !(m && m.running && st.status.alive);
  liveIngest(m);
  if (m) { const t0 = new Date(m.started * 1000).toLocaleTimeString('es');
    $('macrostate').innerHTML = m.running && st.status.alive ? `Macro <b>${esc(m.file)}</b> en marcha desde ${t0} <span class="tag ok">corriendo</span>` : `Última macro <b>${esc(m.file)}</b> · ${t0}${m.finished ? ' → ' + new Date(m.finished * 1000).toLocaleTimeString('es') : ''} <span class="tag">${m.running ? 'sin salida' : 'terminada'}</span>`; }
  else $('macrostate').textContent = 'Sin macros inyectadas todavía.';
  const key = `${p.server_log.file}|${p.server_log.size}|${(p.agent_log || []).slice(-1)[0] || ''}|${m?.file}|${m?.out?.length}|${m?.out?.slice(-1)[0]}`;
  if (key !== prog.key) { prog.key = key;
    // orden: la macro actual (en vivo: iteraciones, SCENE, SAVED…) primero; debajo el log del servidor y agent.log
    const lines = p.server_log.tail.length ? p.server_log.tail : ['(sin log del servidor todavía)'];
    $('term').innerHTML = (m?.out?.length ? `<span class="hl">--- ${esc(m.file)}${m.running ? ' (en marcha)' : ''}</span>\n` + m.out.map(hlLine).join('\n') + '\n\n' : '') + '<span class="hl">--- servidor</span>\n' + lines.map(hlLine).join('\n') + (p.agent_log.length ? '\n\n<span class="hl">--- agent.log</span>\n' + p.agent_log.map(esc).join('\n') : '');
    if ($('progfollow').checked) $('term').scrollTop = 1e9; }
}
// el sondeo también corre mientras hay una macro en marcha: así las curvas en vivo se llenan aunque se mire otra pestaña
setInterval(() => { if ((st.tab === 'out' && !$('stage').classList.contains('dock-collapsed')) || st.tab === 'plots' || LIVE.running || st.chatting) loadProgress(); }, 3000);

// ---------------------------------------------------------------- convergencia EN VIVO (de la salida del solver, sin coste extra)
// STAR-CCM+ imprime en cada iteración una fila con residuales y reportes bajo la cabecera «Iteration Continuity …».
// Se acumulan las filas de la macro en marcha (la salida llega en vivo al .out) y se pintan: residuales en escala
// logarítmica y las magnitudes de ingeniería (H, M, eta…) cada una en su gráfico.
const LIVE = { file: null, cols: null, rows: new Map(), running: false };
const LIVE_RES = /^(Continuity|X-momentum|Y-momentum|Z-momentum|Tke|Sdr|Energy)$/;
function liveIngest(m) {
  if (!m || !m.out) return;
  if (m.file !== LIVE.file) {  // una macro nueva solo reinicia si trae iteraciones (no borra la curva por un inspect)
    if (!m.out.some(l => /^\s*Iteration\s{2,}/.test(l))) { LIVE.running = false; renderLive(); return; }
    LIVE.file = m.file; LIVE.cols = null; LIVE.rows = new Map();
  }
  for (const l of m.out) {
    if (/^\s*Iteration\s{2,}/.test(l)) { LIVE.cols = l.trim().split(/\s{2,}/); continue; }
    if (!LIVE.cols || !/^\s+\d+\s+[-+\d.]/.test(l)) continue;
    const v = l.trim().split(/\s+/).map(Number); if (v.length !== LIVE.cols.length || !v.every(Number.isFinite)) continue;
    LIVE.rows.set(v[0], v);
  }
  LIVE.running = !!m.running; renderLive();
}
function svgLines(series, { log = false, label = '', unit = '' } = {}) {  // varias series en un eje; log10 si se pide
  const W = 420, H = 190, L = 54, R = 10, T = 14, B = 28, PAL = ['#0b63b4', '#d1495b', '#2a9d3f', '#e09f3e', '#7b2cbf', '#3a86ff', '#6c757d'];
  const pts = series.flatMap(s => s.xy).filter(([, y]) => Number.isFinite(y) && (!log || y > 0)); if (!pts.length) return '';
  const tr = y => log ? Math.log10(y) : y, xs = pts.map(p => p[0]), ys = pts.map(p => tr(p[1]));
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), pad = (y1 - y0 || 1) * 0.08;
  const sx = x => L + (x1 === x0 ? 0.5 : (x - x0) / (x1 - x0)) * (W - L - R), sy = y => T + (1 - (tr(y) - (y0 - pad)) / ((y1 + pad) - (y0 - pad))) * (H - T - B);
  const ticks = log ? Array.from({ length: Math.floor(y1 + pad) - Math.ceil(y0 - pad) + 1 }, (_, i) => Math.ceil(y0 - pad) + i).filter((_, i, a) => a.length < 8 || i % 2 === 0)
    : [0, 0.25, 0.5, 0.75, 1].map(t => (y0 - pad) + ((y1 + pad) - (y0 - pad)) * t);
  const grid = ticks.map(t => { const yy = log ? 10 ** t : t; return `<line x1="${L}" x2="${W - R}" y1="${sy(yy)}" y2="${sy(yy)}" class="grid"/><text x="${L - 5}" y="${sy(yy) + 3}" class="tick" text-anchor="end">${log ? '1e' + t : sci(yy)}</text>`; }).join('');
  const lines = series.map((s, k) => { const d = s.xy.filter(([, y]) => Number.isFinite(y) && (!log || y > 0)).map(([x, y], i) => `${i ? 'L' : 'M'}${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(' ');
    return d ? `<path d="${d}" fill="none" stroke="${PAL[k % PAL.length]}" stroke-width="1.6"><title>${esc(s.name)}</title></path>` : ''; }).join('');
  const legend = series.length > 1 ? `<div class="lg-inline">${series.map((s, k) => `<span><i style="background:${PAL[k % PAL.length]}"></i>${esc(s.name)}</span>`).join('')}</div>` : '';
  const lastV = series.length === 1 && series[0].xy.length ? `<text x="${W - R}" y="${T - 2}" class="lbl" text-anchor="end">${sci(series[0].xy[series[0].xy.length - 1][1])} ${esc(unit)}</text>` : '';
  return `<figure class="chart"><figcaption>${esc(label)}</figcaption><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">${grid}<line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" class="axis"/><text x="${L}" y="${H - 8}" class="tick">${x0}</text><text x="${W - R}" y="${H - 8}" class="tick" text-anchor="end">iter ${x1}</text>${lines}${lastV}</svg>${legend}</figure>`;
}
function renderLive() {
  const box = $('live'); if (!box) return;
  const rows = [...LIVE.rows.values()].sort((a, b) => a[0] - b[0]);
  $('livedot').hidden = !LIVE.running;
  if (!LIVE.cols || rows.length < 2) { box.hidden = true; renderLive.sig = ''; return; }
  const sig = `${LIVE.file}|${rows.length}|${rows[rows.length - 1][0]}|${LIVE.running}`;
  if (sig === renderLive.sig && !box.hidden) return;  // mismas filas: los gráficos ya están pintados
  renderLive.sig = sig; box.hidden = false;
  const col = i => rows.map(r => [r[0], r[i]]);
  const res = LIVE.cols.map((c, i) => [c, i]).filter(([c]) => LIVE_RES.test(c)).map(([c, i]) => ({ name: c, xy: col(i) }));
  const eng = LIVE.cols.map((c, i) => [c, i]).filter(([c, i]) => i > 0 && !LIVE_RES.test(c) && /^(H|M|eta|Q_out|pt_out|P_eje)\b/.test(c));
  const last = rows[rows.length - 1], cont = res.find(s => s.name === 'Continuity');
  const contLast = cont ? cont.xy[cont.xy.length - 1][1] : null, contMin = cont ? Math.min(...cont.xy.map(p => p[1])) : null;
  // aviso sencillo: residuo de continuidad > 1 o 1000 veces por encima de su mínimo = el cálculo se está yendo
  const diverge = contLast != null && (contLast > 1 || contLast > 1e3 * contMin);
  box.innerHTML = `<div class="livehead"><b>${LIVE.running ? 'Iterando en vivo' : 'Última corrida'}</b> · iteración ${last[0]} · ${rows.length} filas
    ${diverge ? '<span class="tag warn" title="El residuo de continuidad crece: revisa entradas, salidas y paredes">⚠ posible divergencia</span>' : (contLast != null && contLast < 1e-4 ? '<span class="tag ok">residuo &lt; 1e-4</span>' : '')}</div>
    <div class="charts">${svgLines(res, { log: true, label: 'Residuales (escala log)' })}${eng.map(([c, i]) => svgLines([{ name: c, xy: col(i) }], { label: c, unit: '' })).join('')}</div>`;
}

// ---------------------------------------------------------------- estado del solver
function renderStatus(s) {
  st.status = s;
  const dot = s.alive ? 'ok' : s.stale ? 'busy' : 'off';
  const txt = s.stopping ? 'apagando solver…' : s.alive ? `solver vivo · puerto ${s.port} · ${s.idle_min ?? '?'} min sin actividad` : s.stale ? 'solver caído (.server.json viejo)' : 'solver apagado';
  const sh = `<span class="dot ${dot}"></span><span>${esc(txt)}</span>` ;
  if (renderStatus.last !== sh) { renderStatus.last = sh; $('solver').innerHTML = sh; }
  $('stopsolver').hidden = !s.alive; $('stopsolver').disabled = !!s.stopping || !!s.chatting;
  const remote = st.where === 'server';
  $('opengui').disabled = !!s.alive || remote; $('opengui').title = remote ? 'Solo en local: la GUI abre el .sim de este PC' : s.alive ? 'Hay un servidor batch vivo: apágalo antes de abrir la GUI' : 'Abre este .sim en la GUI de STAR-CCM+ (la licencia PoD cobra por hora)';
  $('solvertag').innerHTML = (s.alive ? '<span class="tag ok">vivo</span>' : s.stale ? '<span class="tag warn">caído</span>' : '<span class="tag">apagado</span>') + (remote ? ' <span class="tag ok">servidor</span>' : '');
  const rows = (s.alive || s.stale ? [['pid', s.pid], ['puerto', s.port], ['sim', s.sim ? s.sim.split(/[\\/]/).pop() : '(nueva)'], ['procesos', s.np], ['arranque', s.started ? s.started.replace('T', ' ') : '–'], ['inactivo', s.idle_min != null ? `${fmt(s.idle_min, 0)} / ${s.idle_limit_min} min` : '–']] : [['apagado por inactividad', `${s.idle_limit_min} min`]]).map(r => [r, '']);
  const kv = [...whereRows(), ...rows].map(([[k, v], cls]) => `<tr class="${cls}"><td class="mut">${esc(k)}</td><td class="mono" title="${esc(v)}">${esc(v)}</td></tr>`).join('');
  if (renderStatus.kv !== kv) { renderStatus.kv = kv; $('solverkv').querySelector('tbody').innerHTML = kv; }
}
async function poll() {
  try { renderStatus(await api('/api/status')); $('offline').hidden = true; }
  catch (e) { $('offline').hidden = false; $('offlinetxt').textContent = 'Sin conexión con el servidor local: ' + e.message; }
}
$('retry').onclick = poll; setInterval(poll, 5000);
$('solverbtn').onclick = e => { e.stopPropagation(); const o = $('solverpop').hidden; $('solverpop').hidden = !o; $('solverbtn').setAttribute('aria-expanded', o); };
addEventListener('click', e => { if (!$('solverpop').hidden && !e.target.closest('#solverpop,#solverbtn')) { $('solverpop').hidden = true; $('solverbtn').setAttribute('aria-expanded', 'false'); } });
// confirm() del navegador no aparece en el panel embebido de la app: confirmación en la página (segundo clic)
function armed(btn, label, ms = 5000) {
  if (btn.dataset.armed) { clearTimeout(+btn.dataset.t); delete btn.dataset.armed; btn.textContent = btn.dataset.orig; return true; }
  btn.dataset.orig = btn.textContent; btn.dataset.armed = '1'; btn.textContent = label;
  btn.dataset.t = setTimeout(() => { delete btn.dataset.armed; btn.textContent = btn.dataset.orig; }, ms);
  return false;
}
$('stopsolver').onclick = async () => {
  if (!armed($('stopsolver'), '¿Guardar y apagar? Pulsa otra vez')) return;
  $('stopsolver').disabled = true; $('solver').innerHTML = '<span class="dot busy"></span><span>apagando solver…</span>';
  try { const r = await api('/api/server/stop', { save: true }); toast(r.stopped ? `Solver apagado en ${r.seconds} s${r.saved ? ' · guardado ' + r.saved.split(/[\\/]/).pop() : ''}${r.forced ? ' (forzado)' : ''}` : 'No había servidor', r.stopped ? 'ok' : 'warn'); }
  catch (e) { toast('No pude apagar: ' + e.message, 'error'); }
  poll();
};
$('opengui').onclick = async () => {
  if (!st.case) return;
  if (!armed($('opengui'), 'PoD cobra por hora · ¿abrir? Pulsa otra vez', 6000)) return;
  $('opengui').disabled = true;
  try { const r = await api('/api/open_gui', { case: st.case }); toast(`GUI lanzada (pid ${r.pid}); tarda unos segundos en abrir`, 'ok'); }
  catch (e) { toast(e.message, 'error'); }
  $('opengui').disabled = false;
};

// ---------------------------------------------------------------- chat con Claude Code (SSE)
function placeQuick() { const empty = !$('chatlog').querySelector('.m'); $('chatempty').hidden = !empty; if (empty) $('chatempty').appendChild($('quick')); else $('chatin').before($('quick')); }
function addMsg(cls, html) { const d = document.createElement('div'); d.className = 'm ' + cls; d.innerHTML = html; $('chatlog').appendChild(d); placeQuick(); $('chatlog').scrollTop = 1e9; return d; }
function toolSummary(name, inp = {}) {
  const bits = [inp.name, inp.path, inp.query && `«${inp.query}»`, inp.n != null && `${inp.n} iter`, inp.sim_path && String(inp.sim_path).split(/[\\/]/).pop(), inp.body && `${String(inp.body).split('\n').length} líneas Java`].filter(Boolean);
  return [name, ...bits].join(' · ');
}
const setChatState = html => { if ($('chatstate').innerHTML !== html) $('chatstate').innerHTML = html; };
function setChatting(on) { st.chatting = on; $('chatdot').hidden = !on; document.documentElement.classList.toggle('chat-busy', on); $('send').disabled = on; $('stopchat').disabled = !on; if (st.status.alive != null) renderStatus(st.status); }
function onChatEvent(ev, ctx) {
  if (['result', 'error'].includes(ev.kind) && /No conversation found/i.test(ev.text || '')) { ctx.stale = true; return; }
  if (ev.kind === 'result' && ev.turns === 0 && ev.subtype !== 'success' && !ev.text) return;
  if (ev.kind === 'init') { st.session = ev.session_id; LS.set('scc_session', st.session); $('chatstate').textContent = `sesión ${st.session.slice(0, 8)} · ${ev.model || ''}`; }
  else if (ev.kind === 'text') {
    const q = parseQuestion(ev.text);
    if (q.rest.trim()) addMsg('bot', md(q.rest));
    if (q.q) showQuestion(q.q, ctx);
    ctx.tool = ''; $('chatstate').textContent = q.q ? 'esperando tu respuesta' : 'pensando…'; }
  else if (ev.kind === 'tool') {
    const lab = ev.label || toolSummary(ev.name, ev.input || {});
    ctx.step = addMsg('step', `<span class="ic">▶</span><span class="lab">${esc(lab)}</span><span class="dur"></span><details><summary>detalle</summary>${esc(JSON.stringify(ev.input || {}, null, 1)).slice(0, 2000)}</details>`);
    ctx.tool = ev.name; ctx.t0 = Date.now(); setChatState(`ejecutando ${esc(ev.name)}…<span id="chatsecs" aria-hidden="true"></span>`);
    if (/server_|export_scene|iterate|run_java|save/.test(ev.name)) ctx.refresh = true;
  }
  else if (ev.kind === 'tool_result') {
    if (ctx.step) { const s = Math.round((Date.now() - ctx.t0) / 1000); ctx.step.classList.add(ev.is_error ? 'bad' : 'ok');
      ctx.step.querySelector('.ic').textContent = ev.is_error ? '✗' : '✓'; ctx.step.querySelector('.dur').textContent = ctx.replay ? '' : ` ${s} s`; ctx.step = null; }
    if (ev.is_error) addMsg('tool bad', 'Error: ' + esc(ev.text)); else if (/server_/.test(ctx.tool)) poll(); if (st.tab === 'out') loadProgress(); }
  else if (ev.kind === 'status') $('chatstate').textContent = ev.text;
  else if (ev.kind === 'ping') { if (!ctx.tool) $('chatstate').textContent = `trabajando… ${ev.t} s`; }
  else if (ev.kind === 'error') addMsg('err', /conversación en curso/.test(ev.text) ? 'Ya hay una conversación en curso. Espera o pulsa Detener.' : esc(ev.text));
  else if (ev.kind === 'result') { ctx.tool = ''; if (ev.text) addMsg('err', esc(ev.text)); $('chatstate').textContent = `listo · ${ev.turns ?? '?'} turnos · ${ev.seconds} s`; }
  else if (ev.kind === 'stopped') { addMsg('bot mut', 'Detenido por el usuario.'); ctx.tool = ''; $('chatstate').textContent = 'detenido'; }
  else if (ev.kind === 'done') { ctx.done = true; if (ev.rc && ev.rc !== 0 && !/listo|detenido/.test($('chatstate').textContent)) $('chatstate').textContent = `terminó con código ${ev.rc}`; }
  if (!ctx.login && ['text', 'result', 'error'].includes(ev.kind) && /401|not logged in|OAuth|auth login/i.test(ev.text || '')) { ctx.login = true; addMsg('err', 'La CLI de la IA no tiene sesión. En una terminal ejecuta: <code>claude auth login</code>'); }
}
const chatClock = ctx => setInterval(() => { if (ctx.tool) { const secs = $('chatsecs'); if (secs) secs.textContent = ` ${Math.round((Date.now() - ctx.t0) / 1000)} s`; } }, 1000);  // segundos de la herramienta en curso
// ---------------------------------------------------------------- preguntas de la IA con opciones (bloque ```pregunta {json}```)
function parseQuestion(text) {
  const m = /```\s*pregunta\s*\n?([\s\S]*?)```/i.exec(text || '');
  if (!m) return { rest: text || '', q: null };
  let q = null; try { q = JSON.parse(m[1].trim()); } catch { return { rest: text, q: null }; }
  if (!q || typeof q.pregunta !== 'string') return { rest: text, q: null };
  q.opciones = Array.isArray(q.opciones) ? q.opciones.map(String).slice(0, 8) : [];
  return { rest: text.replace(m[0], ''), q };
}
function showQuestion(q, ctx) {
  const multi = !!q.multiple;
  const d = addMsg('ask', `<div class="q-t">${esc(q.pregunta)}</div><div class="q-opts">${q.opciones.map((o, i) =>
    `<button class="sm q-o" data-i="${i}" aria-pressed="false">${esc(o)}</button>`).join('')}</div>
    <div class="q-row"><input class="q-other" placeholder="u otra respuesta…" aria-label="Otra respuesta">${multi ? '<button class="sm pri q-send">Responder</button>' : '<button class="sm q-send">Enviar</button>'}</div>`);
  const answer = txt => {
    if (!txt || st.chatting) { if (st.chatting) toast('La IA aún está terminando; espera un momento', 'warn'); return; }
    for (const b of d.querySelectorAll('button,input')) b.disabled = true; d.classList.add('done');
    $('chattext').value = txt; sendChat();
  };
  d.querySelectorAll('.q-o').forEach(b => b.onclick = () => {
    if (!multi) return answer(q.opciones[+b.dataset.i]);
    b.setAttribute('aria-pressed', b.getAttribute('aria-pressed') !== 'true');
  });
  const send = () => { const other = d.querySelector('.q-other').value.trim();
    const sel = [...d.querySelectorAll('.q-o[aria-pressed="true"]')].map(b => q.opciones[+b.dataset.i]);
    answer([...sel, other].filter(Boolean).join('; ')); };
  d.querySelector('.q-send').onclick = send;
  d.querySelector('.q-other').onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); send(); } };
  if (!ctx?.replay) showWhat(q);
}
// «ver»: la IA enseña lo que no tiene claro (fronteras dudosas, una escena, el visor o la convergencia)
function showWhat(q) {
  const v = String(q.ver || '').trim(); if (!v) return;
  if (v === 'graficos') { openTab('plots'); return; }
  if (v.startsWith('escena:')) { const f = v.slice(7).trim(); refreshCaseList().then(() => openCase(st.case)).then(() => showView(f)); return; }
  showView('3d');
  if (v === 'fronteras') {
    const go = () => { if (!st.ds) return; setRolesMode(true);
      const keys = new Set((q.caras || []).map(String));
      const dud = st.ds.parts.filter(p => keys.has(`${p.group?.name || ''}/${p.name}`));
      for (const p of dud) { p.li?.classList.add('doubt'); if (p.group) { const det = p.li?.closest('details'); if (det) det.open = true; } }
      if (dud.length) flyTo(dud[0]);
      toast(dud.length ? `La IA duda de ${dud.length} cara(s), marcadas en el árbol: haz clic en cada una y elige su papel` : 'Marca en el 3D qué cara es entrada y cuál salida', 'ok'); };
    st.ds ? go() : loadDatasets().then(go);
  }
}
async function readSSE(r, ctx) {  // cuenta los eventos (ctx.n) para poder reengancharse desde ahí
  const reader = r.body.getReader(), dec = new TextDecoder(); let buf = '';
  while (true) { const { value, done } = await reader.read(); if (done) break; buf += dec.decode(value, { stream: true });
    let idx; while ((idx = buf.indexOf('\n\n')) >= 0) { const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2); if (!chunk.startsWith('data: ')) continue;
      let ev; try { ev = JSON.parse(chunk.slice(6)); } catch { continue; } if (ev.kind !== 'ping') ctx.n = (ctx.n || 0) + 1; onChatEvent(ev, ctx); } }
}
async function reattach(ctx) {
  try {
    const cur = await api('/api/chat/current'); if (!cur.id) return false;
    if (ctx.rid && cur.id !== ctx.rid) return false; ctx.rid = cur.id;
    const r = await fetch(`/api/chat/stream?id=${cur.id}&frm=${ctx.n || 0}`); if (!r.ok || !r.body) return false;
    await readSSE(r, ctx); return true;
  } catch { await new Promise(res => setTimeout(res, 2000)); return true; }
}
// al cargar la página: si la IA está trabajando (p. ej. tras recargar), se muestra lo hecho y se sigue en vivo
async function resumeChat() {
  let cur; try { cur = await api('/api/chat/current'); } catch { return; }
  if (!cur.running) return;
  if (document.documentElement.classList.contains('chat-off')) setChatOpen(true);
  addMsg('user', esc(cur.message || '(mensaje)'));
  setChatting(true); $('chatstate').textContent = 'retomando la conversación en curso…';
  const ctx = { t0: Date.now(), tool: '', login: false, done: false, refresh: true, rid: cur.id, n: 0, replay: true };
  const clock = chatClock(ctx);
  try {
    const r = await fetch(`/api/chat/stream?id=${cur.id}&frm=0`);
    if (r.ok && r.body) { setTimeout(() => { ctx.replay = false; }, 1500); await readSSE(r, ctx); }
    for (let k = 0; k < 20 && !ctx.done && st.chatting; k++) { if (!(await reattach(ctx))) break; }
  } catch {}
  clearInterval(clock); setChatting(false); poll();
  refreshCaseList().then(() => { if (st.case) openCase(st.case); });
}
async function sendChat(retry = false) {
  if (document.documentElement.classList.contains('chat-off')) setChatOpen(true);
  if (NARROW.matches && st.tab !== 'chat') openTab('chat');  // los parámetros viven en Propiedades: al pedir, se muestra la conversación
  const text = $('chattext').value.trim(); if (!text || st.chatting) return;
  $('chattext').value = ''; st.lastMsg = text; if (!retry) addMsg('user', esc(text));
  setChatting(true); $('chatstate').textContent = 'pensando…';
  const ctx = { t0: Date.now(), tool: '', login: false, done: false, refresh: false, n: 0 };
  const clock = chatClock(ctx);
  try {
    const r = await fetch('/api/chat', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ message: text, session_id: st.session, case: st.case }) });
    if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
    await readSSE(r, ctx);
    // la conversación vive en el servidor: si el flujo se corta, se vuelve a enganchar donde iba
    for (let k = 0; k < 20 && !ctx.done && st.chatting; k++) { if (!(await reattach(ctx))) break; }
    if (!ctx.done && st.chatting) throw new Error('el flujo se cortó');
  } catch (e) {
    const d = addMsg('err', `Se cortó la conexión con el chat (${esc(String(e.message || e))}). Tu mensaje no se perdió:<div class="actions"><button class="sm">Reenviar</button></div>`);
    d.querySelector('button').onclick = () => { $('chattext').value = text; sendChat(); }; $('chatstate').textContent = 'conexión perdida';
  }
  clearInterval(clock); setChatting(false); poll();
  if (ctx.refresh) refreshCaseList().then(() => { if (st.case) openCase(st.case); });
  if (ctx.stale && !retry) { st.session = null; LS.set('scc_session', null); addMsg('bot mut', 'La conversación anterior ya no existe; empiezo una nueva con tu mensaje.'); $('chattext').value = text; sendChat(true); }
}
$('send').onclick = () => sendChat();
$('chattext').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); } else if (e.key === 'ArrowUp' && !$('chattext').value && st.lastMsg) { e.preventDefault(); $('chattext').value = st.lastMsg; } });
$('stopchat').onclick = () => { $('stopchat').disabled = true; $('chatstate').textContent = 'deteniendo…'; api('/api/chat/stop', {}).then(j => { if (!j.stopped) $('chatstate').textContent = 'no había nada que detener'; }).catch(e => { $('chatstate').textContent = 'no pude detener: ' + e.message; }); };
$('newchat').onclick = () => {
  if (busyChat()) return;
  if (!armed($('newchat'), '¿Seguro?', 4000)) return;
  st.session = null; LS.set('scc_session', null);
  for (const m of $('chatlog').querySelectorAll('.m')) m.remove(); placeQuick(); $('chatstate').textContent = 'nueva conversación'; };
const busyChat = () => { if (st.chatting) { toast('La IA está trabajando; espera o pulsa Detener', 'warn'); return true; } return false; };
for (const b of $('quick').querySelectorAll('[data-q]')) b.onclick = () => { if (busyChat()) return; $('chattext').value = b.dataset.q.replace('<caso>', st.case || 'caso'); sendChat(); };
st.session = LS.get('scc_session'); if (st.session) $('chatstate').textContent = `sesión ${st.session.slice(0, 8)} (continúa)`;
resumeChat();

// parámetros -> prompt (la página nunca edita el .sim)
const PARAMS = [['p_rpm', v => `velocidad de giro del rotor a ${v} rpm (MRF)`], ['p_mdot', v => `caudal másico de entrada a ${v} kg/s`], ['p_base', v => `tamaño base de malla a ${v} mm (remallar las 3 operaciones)`], ['p_iter', v => `luego corre ${v} iteraciones (en bloques de 100 con iterate)`]];
$('paskbtn').onclick = () => {
  if (busyChat()) return;
  const parts = PARAMS.map(([id, f]) => { const v = $(id).value.trim(); return v ? f(v) : ''; }).filter(Boolean);
  if (!parts.length) { toast('Rellena al menos un parámetro', 'warn'); return; }
  $('chattext').value = `En la simulación sims/${st.case}.sim (server_start la reutiliza si está viva): cambia ${parts.join('; ')}. Precompila cada macro y usa las recetas bomba-*. Al terminar, añade las filas a cases/${st.case}/reports/convergencia.csv, vuelve a exportar las escenas de presión, velocidad e y+ a images/, exporta las superficies con campo (receta exportar-superficies-ensight) y dime H, M y eficiencia en una tabla frente a los valores anteriores.`;
  sendChat();
};
$('pclear').onclick = () => { for (const [id] of PARAMS) { $(id).value = ''; $(id).classList.remove('edited'); } };
// valores actuales del caso, sacados del RESUMEN.md con regex (placeholder gris + resumen en la cabecera); lo editado se marca
function fillParams(d) {
  const r = d.resumen || ''; const num = s => s && s.replace(/\s/g, '').replace(',', '.');
  const cur = { p_rpm: num((r.match(/[−-]?\s*(\d[\d\s]*)\s*rpm/) || [])[1]), p_mdot: num((r.match(/ṁ\s*=\s*([\d.,]+)\s*kg\/s/) || r.match(/([\d.,]+)\s*kg\/s/) || [])[1]),
    p_base: num((r.match(/base\s*([\d.,]+)\s*mm/i) || [])[1]), p_iter: (r.match(/(\d+)\s*iteraciones/) || [])[1] };
  for (const [id] of PARAMS) { const el = $(id); el.placeholder = cur[id] || ''; el.value = ''; el.classList.remove('edited'); el.oninput = () => el.classList.toggle('edited', !!el.value.trim() && el.value.trim() !== el.placeholder); }
  $('params').hidden = !d.pump;  // los parámetros son de bomba (pump.py): sin él no se muestran
  $('pnow').textContent = [cur.p_rpm && `${cur.p_rpm} rpm`, cur.p_mdot && `${cur.p_mdot.replace('.', ',')} kg/s`, cur.p_base && `base ${cur.p_base} mm`, cur.p_iter && `${cur.p_iter} iter`].filter(Boolean).join(' · ');
}
$('params').ontoggle = () => LS.set('scc_params', $('params').open ? '1' : '0'); $('params').open = LS.get('scc_params', '0') === '1';

// acciones del visor desde el chat: se ejecutan en el cliente, sin solver ni Claude
function viewerCmd(c) {
  if (!st.ds) { toast('No hay superficies 3D en este caso', 'warn'); return; }
  showView('3d');
  const find = re => st.ds.manifest.scalars.find(x => re.test(x.name));
  if (c === 'rotor') { setRotor(!V.rotor); toast(V.rotor ? 'Rotor girando (animación del visor, 0,25 rev/s)' : 'Rotor detenido', 'ok'); return; }
  const sc = c === 'pressure' ? find(/^Pressure$/i) || find(/pressure/i) : find(/velocity/i);
  if (!sc) { toast('Este dataset no trae ese campo', 'warn'); return; }
  st.scalar = sc.name; $('scalar').value = sc.name; LS.set('scc_scalar', sc.name); st.range = null; applyColors(true);
  if (c === 'pressure') { if (!V.ghost) { V.ghost = true; LS.set('scc_ghost', '1'); applyGhost(); } const bl = st.ds.parts.find(p => /blade/i.test(p.name)); if (bl) flyTo(bl); }
  else fit();
}
for (const b of $('chips').querySelectorAll('[data-vc]')) b.onclick = () => viewerCmd(b.dataset.vc);

// ---------------------------------------------------------------- árbol de la simulación (desde datos en disco, sin solver) + propiedades
const OUT_NODES = [['geo', 'Geometría'], ['phys', 'Física'], ['mesh', 'Malla'], ['solv', 'Solucionadores'], ['rep', 'Reportes'], ['mon', 'Monitores'], ['plots', 'Gráficos']];
let outSel = LS.get('scc_outnode', 'geo'); if (outSel === 'scn') outSel = 'geo';
const resLines = re => (st.data?.resumen || '').split('\n').map(l => l.replace(/[*`|#]/g, '').replace(/^\s*[-]\s*/, '').trim()).filter(l => l && re.test(l));
function propsFor(id) {
  const d = st.data || {}, cv = d.convergencia, last = cv?.rows.length ? Object.fromEntries(cv.columns.map((c, i) => [c, cv.rows[cv.rows.length - 1][i]])) : null;
  const txt = (re, n = 8) => resLines(re).slice(0, n).map((l, i) => [i ? '' : 'RESUMEN.md', l]);
  if (id === 'geo') { const m = st.ds?.manifest; if (!m) return [['superficies', 'sin dataset 3D']]; const sz = V.bbox.getSize(new THREE.Vector3());
    return [['dataset', st.ds.name], ['vértices', m.n_vertices.toLocaleString('es')], ['campos', m.scalars.map(x => labelOf(x.name)).join(', ') || '–'], ['caja (m)', [sz.x, sz.y, sz.z].map(v => fmt(v, 3)).join(' × ')], ['exportado', m.exported || '–']]; }
  if (id === 'phys') return txt(/k-?\s?(ω|omega|w)|sst|turbul|MRF|estacion|agua|densidad|líquido|segregad/i);
  if (id === 'mesh') return txt(/celdas|malla|prism|poli|base/i);
  if (id === 'solv') return [['iteraciones', last?.iter != null ? String(last.iter) : '–'], ['filas de convergencia', cv ? String(cv.rows.length) : '0'], ...txt(/iteraci|residual|under|relaj/i, 4)];
  if (id === 'rep') return last ? Object.entries(last).filter(([k]) => k !== 'iter').map(([k, v]) => [k, sci(v)]) : [['reportes', 'sin convergencia.csv']];
  if (id === 'mon') return cv ? [['columnas', cv.columns.join(', ')], ['archivo', cv.file]] : [['monitores', 'sin convergencia.csv']];
  if (id === 'plots') return [['gráficos', 'H y M frente a iteración (pestaña Gráficos)'], ['filas', cv ? String(cv.rows.length) : '0']];
  return [];
}
// resultados de un vistazo (última fila de convergencia.csv), con el mismo formato que la leyenda y Reportes
function renderKpis() {
  const cv = st.data?.convergencia, el = $('kpis');
  if (!cv?.rows.length) { el.hidden = true; el.innerHTML = ''; return; }
  const last = Object.fromEntries(cv.columns.map((c, i) => [c, cv.rows[cv.rows.length - 1][i]]));
  const defs = [['H', 'H', 'm'], ['M', 'M', 'N·m'], ['eta', 'η', ''], ['continuity', 'continuidad', ''], ['iter', 'iter', '']];
  const items = defs.filter(([k]) => last[k] != null).map(([k, l, u]) => {
    const cls = k === 'continuity' ? (Math.abs(last[k]) < 1e-5 ? 'ok' : 'warn') : '';
    return `<button class="kpi ${cls}" data-k="${k}" title="${esc(l)}: ver la gráfica en el dock">${esc(l)} <b>${k === 'iter' ? last[k] : sci(last[k])}</b>${u ? ` <span class="u">${u}</span>` : ''}</button>`; });
  el.innerHTML = items.join(''); el.hidden = !items.length;
  for (const b of el.querySelectorAll('.kpi')) b.onclick = () => { $('stage').classList.remove('dock-collapsed'); $('docktoggle').textContent = '▾'; openTab('plots'); };
}
function renderOutline() {
  renderKpis();
  const ul = $('outline'); if (!st.data) { ul.innerHTML = ''; return; }
  const cnt = { geo: st.ds ? st.ds.parts.length : '', rep: st.data.convergencia ? 'H M' : '', plots: st.data.convergencia?.rows.length || '' };
  ul.innerHTML = OUT_NODES.map(([id, n]) => `<li role="option" tabindex="0" data-n="${id}" aria-selected="${id === outSel}"><span>${n}</span><span class="c">${esc(cnt[id] ?? '')}</span></li>`).join('');
  for (const li of ul.querySelectorAll('li')) { li.onclick = () => selectNode(li.dataset.n); li.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectNode(li.dataset.n); } }; }
  renderProps();
}
function renderProps() {
  const rows = propsFor(outSel), name = (OUT_NODES.find(n => n[0] === outSel) || [])[1] || '';
  $('props').innerHTML = rows.length ? `<h4>Propiedades · ${esc(name)}</h4><table class="kv"><tbody>${rows.map(([k, v]) => `<tr><td class="mut">${esc(k)}</td><td title="${esc(v)}" style="white-space:normal;max-width:none">${esc(v)}</td></tr>`).join('')}</tbody></table>` : '';
}
function selectNode(id) {
  outSel = id; LS.set('scc_outnode', id);
  for (const li of $('outline').querySelectorAll('li')) li.setAttribute('aria-selected', li.dataset.n === id);
  renderProps();
  if (id === 'plots') openTab('plots'); else if (id === 'geo') showView('3d');
}

// chat plegable (solo escritorio): el visor gana ancho; se abre solo al enviar un mensaje
function setChatOpen(on) {
  document.documentElement.classList.toggle('chat-off', !on); $('chattoggle').setAttribute('aria-pressed', on); $('chattoggle').textContent = on ? '»' : '«'; LS.set('scc_chatopen', on ? '1' : '0'); setTimeout(() => { V.needs = true; }, 0);
}
$('chattoggle').onclick = () => setChatOpen(document.documentElement.classList.contains('chat-off'));
setChatOpen(LS.get('scc_chatopen', '1') === '1');
// panel de la simulación (izquierda) plegable, igual que el de la IA; se recuerda
function setTreeOpen(on) {
  document.documentElement.classList.toggle('tree-off', !on); $('treetoggle').setAttribute('aria-pressed', on); $('treetoggle').textContent = on ? '«' : '»'; LS.set('scc_treeopen', on ? '1' : '0'); setTimeout(() => { V.needs = true; }, 0);
}
$('treetoggle').onclick = () => setTreeOpen(document.documentElement.classList.contains('tree-off'));
setTreeOpen(LS.get('scc_treeopen', '1') === '1');
// ancho del panel de IA: arrastrar el borde izquierdo (o flechas con el foco), doble clic restablece; se recuerda
(() => { const rs = $('chatresize'), root = document.documentElement, MIN = 260, DEF = 330;
  const maxW = () => Math.max(MIN, Math.min(720, innerWidth * 0.55));
  const set = (w, save) => { w = Math.round(Math.max(MIN, Math.min(maxW(), w))); root.style.setProperty('--chat-w', w + 'px'); rs.setAttribute('aria-valuenow', w); if (save) LS.set('scc_chatw', String(w)); V.needs = true; return w; };
  set(parseInt(LS.get('scc_chatw', DEF), 10) || DEF, false);
  rs.onpointerdown = e => { e.preventDefault(); rs.setPointerCapture(e.pointerId); const x0 = e.clientX, w0 = $('chatcol').getBoundingClientRect().width; root.classList.add('resizing');
    rs.onpointermove = ev => set(w0 + (x0 - ev.clientX), false);
    rs.onpointerup = rs.onpointercancel = ev => { rs.onpointermove = rs.onpointerup = rs.onpointercancel = null; root.classList.remove('resizing'); set(w0 + (x0 - ev.clientX), true); }; };
  rs.ondblclick = () => set(DEF, true);
  rs.onkeydown = e => { if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return; e.preventDefault(); set($('chatcol').getBoundingClientRect().width + (e.key === 'ArrowLeft' ? 24 : -24), true); };
  addEventListener('resize', () => set($('chatcol').getBoundingClientRect().width || DEF, false));
})();
// ---------------------------------------------------------------- tema y teclado
const theme = LS.get('scc_theme', 'light'); document.documentElement.dataset.theme = theme;
$('theme').onclick = () => { const nx = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = nx; LS.set('scc_theme', nx); };
addEventListener('keydown', e => {
  if (e.key === 'Escape') { $('lightbox').hidden = true; return; }
  if (e.ctrlKey || e.metaKey || e.altKey || e.target.matches('input,textarea,select')) return;
  if (e.key === 'f' || e.key === 'F') fit(); else if (e.key === '1') setView('iso'); else if (e.key === '2') setView('axial'); else if (e.key === '3') setView('lateral');
  else if (e.key === '`') $('docktoggle').click(); else if (e.key === 'c' || e.key === 'C') $('chattoggle').click(); else if (e.key === 't' || e.key === 'T') $('treetoggle').click(); else if (e.key === 'b' || e.key === 'B') $('rolesbtn').click();
});

// ---------------------------------------------------------------- arranque
initViewer(); narrowZoom(); placeChat(); placeQuick(); openTab(['out', 'plots', 'res', 'chat'].includes(st.tab) && (st.tab !== 'chat' || NARROW.matches) ? st.tab : 'out'); poll();
loadSettings().then(() => loadCases()).catch(e => { toast('No pude leer los casos: ' + e.message, 'error'); });
