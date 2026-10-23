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
const sci = x => x == null || isNaN(x) ? '–' : (Math.abs(x) >= 1e5 || (Math.abs(x) < 1e-2 && x !== 0)) ? x.toExponential(2).replace('.', ',') : fmt(x, Math.abs(x) < 10 ? 3 : 1);
const st = { cases: [], case: null, data: null, status: {}, chatting: false, session: null, lastMsg: '', tab: LS.get('scc_tab', 'out'),
  view: '3d', datasets: [], ds: null, scalar: '', cmap: LS.get('scc_cmap', 'ccm'), range: null };

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
async function loadCases() {
  st.cases = await api('/api/cases');
  const sel = $('case');
  sel.innerHTML = st.cases.map(c => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('') || '<option value="">(sin casos)</option>';
  const want = LS.get('scc_case');
  const name = st.cases.some(c => c.name === want) ? want : st.cases[0]?.name;
  if (name) { sel.value = name; await openCase(name); }
}
$('case').onchange = () => openCase($('case').value);
async function openCase(name) {
  st.case = name; LS.set('scc_case', name);
  try { st.data = await api('/api/cases/' + encodeURIComponent(name)); }
  catch (e) { toast('No pude abrir el caso: ' + e.message, 'error'); return; }
  const d = st.data;
  $('simname').textContent = `${d.title || d.name} · sims/${d.name}.sim`;
  $('bconv').textContent = d.convergencia ? d.convergencia.rows.length : '';
  $('resumen').innerHTML = d.resumen ? md(d.resumen) : '<p class="mut">Este caso no tiene RESUMEN.md</p>';
  renderScenes(d); renderConv(d);
  await loadDatasets();
  loadTree(false);
}

// ---------------------------------------------------------------- visor 3D (three.js)
const V = { renderer: null, scene: null, camera: null, controls: null, group: null, meshes: [], lights: null, raycaster: new THREE.Raycaster(),
  axes: null, axesCam: null, hot: null, anim: null, spin: false, bbox: null, clip: null, needs: true, wire: false };
function initViewer() {
  const canvas = $('gl');
  V.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  V.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  V.renderer.localClippingEnabled = true;
  V.scene = new THREE.Scene();
  V.camera = new THREE.PerspectiveCamera(40, 1, 0.001, 100);
  V.camera.position.set(0.5, -0.5, 0.4); V.camera.up.set(0, 0, 1);
  V.controls = new OrbitControls(V.camera, canvas);
  V.controls.enableDamping = true; V.controls.dampingFactor = 0.08; V.controls.screenSpacePanning = true;
  V.controls.addEventListener('change', () => { V.needs = true; });
  const hemi = new THREE.HemisphereLight(0xffffff, 0x8899aa, 0.9);
  const key = new THREE.DirectionalLight(0xffffff, 1.1); key.position.set(1, -1, 1.2);
  const fill = new THREE.DirectionalLight(0xffffff, 0.45); fill.position.set(-1, 0.6, -0.4);
  V.lights = new THREE.Group(); V.lights.add(hemi, key, fill); V.scene.add(V.lights);
  V.group = new THREE.Group(); V.scene.add(V.group);
  V.clip = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
  // tríada de ejes en la esquina (escena aparte, misma orientación que la cámara)
  V.axes = new THREE.Scene();
  const mk = (dir, col) => { const a = new THREE.ArrowHelper(new THREE.Vector3(...dir), new THREE.Vector3(), 0.8, col, 0.25, 0.12); V.axes.add(a); };
  mk([1, 0, 0], 0xd62828); mk([0, 1, 0], 0x2a9d3f); mk([0, 0, 1], 0x1d6fd1);
  V.axesCam = new THREE.PerspectiveCamera(40, 1, 0.1, 10); V.axesCam.up.set(0, 0, 1);
  new ResizeObserver(resize).observe($('viewer'));
  resize();
  canvas.addEventListener('pointermove', onHover);
  canvas.addEventListener('pointerleave', () => { $('vtip').hidden = true; setHot(null); });
  canvas.addEventListener('dblclick', e => { const hit = pick(e); if (hit) flyTo(hit.object.userData.part); });
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
  if (V.spin) { V.controls.autoRotate = true; V.needs = true; } else V.controls.autoRotate = false;
  V.controls.update();
  if (!V.needs) return;
  V.needs = false;
  const r = V.renderer; const w = $('viewer').clientWidth, h = $('viewer').clientHeight;
  r.setViewport(0, 0, w, h); r.setScissorTest(false); r.render(V.scene, V.camera);
  // tríada
  const s = 76; V.axesCam.position.copy(V.camera.position).sub(V.controls.target).normalize().multiplyScalar(3); V.axesCam.lookAt(0, 0, 0);
  r.setViewport(8, 8, s, s); r.setScissor(8, 8, s, s); r.setScissorTest(true); r.autoClear = false; r.render(V.axes, V.axesCam); r.autoClear = true; r.setScissorTest(false);
}
function fit(ms = 600) {
  if (!V.bbox) return;
  const c = V.bbox.getCenter(new THREE.Vector3()), size = V.bbox.getSize(new THREE.Vector3()).length();
  const dir = V.camera.position.clone().sub(V.controls.target).normalize();
  if (!dir.length()) dir.set(0.6, -0.7, 0.5);
  const dist = size / (2 * Math.tan(V.camera.fov * Math.PI / 360)) * 1.15;
  tween(c.clone().add(dir.multiplyScalar(dist)), c, ms);
  V.camera.near = size / 500; V.camera.far = size * 20; V.camera.updateProjectionMatrix();
}
function tween(p1, c1, ms = 600) {
  V.anim = { t0: performance.now(), ms, p0: V.camera.position.clone(), p1, c0: V.controls.target.clone(), c1 };
}
function setView(name) {
  if (!V.bbox) return;
  const c = V.bbox.getCenter(new THREE.Vector3()), size = V.bbox.getSize(new THREE.Vector3()).length();
  const dist = size / (2 * Math.tan(V.camera.fov * Math.PI / 360)) * 1.15;
  const dir = { iso: [0.6, -0.7, 0.5], axial: [0, 0, 1], lateral: [0, -1, 0.0001] }[name];
  tween(c.clone().add(new THREE.Vector3(...dir).normalize().multiplyScalar(dist)), c);
}
function flyTo(part) {
  if (!part) return;
  const m = part.mesh; m.geometry.computeBoundingBox(); const b = m.geometry.boundingBox;
  const c = b.getCenter(new THREE.Vector3()), size = Math.max(b.getSize(new THREE.Vector3()).length(), V.bbox.getSize(new THREE.Vector3()).length() / 8);
  const dir = V.camera.position.clone().sub(V.controls.target).normalize();
  tween(c.clone().add(dir.multiplyScalar(size / (2 * Math.tan(V.camera.fov * Math.PI / 360)) * 1.3)), c, 700);
}
function pick(e) {
  const r = $('gl').getBoundingClientRect();
  const p = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  V.raycaster.setFromCamera(p, V.camera);
  const hits = V.raycaster.intersectObjects(V.meshes.filter(m => m.visible), false);
  return hits[0] || null;
}
let hoverT = 0;
function onHover(e) {
  if (st.view !== '3d' || !V.meshes.length) return;
  const now = performance.now(); if (now - hoverT < 40) return; hoverT = now;
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
const unitOf = n => /pressure/i.test(n) ? ' Pa' : /velocity/i.test(n) ? ' m/s' : /yplus/i.test(n) ? '' : '';

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
  clearDataset();
  if (!st.case) return;
  try { st.datasets = (await api('/api/surfaces?case=' + encodeURIComponent(st.case))).datasets; } catch (e) { st.datasets = []; }
  const dsel = $('datasets');
  $('b-geo').textContent = st.datasets.length || '';
  if (!st.datasets.length) { dsel.innerHTML = 'Sin superficies exportadas.'; $('vempty').hidden = false; return; }
  dsel.innerHTML = `<select id="dsel" aria-label="Dataset">${st.datasets.map(d => `<option value="${esc(d.name)}">${esc(d.name)} · ${new Date(d.mtime * 1000).toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</option>`).join('')}</select>`;
  // por defecto el más nuevo que no sea «demo» (el sintético de prueba), salvo preferencia guardada
  const want = LS.get('scc_ds_' + st.case);
  const pick = (want && want !== 'demo' && st.datasets.find(d => d.name === want)) || st.datasets.find(d => d.name !== 'demo') || st.datasets[0];
  $('dsel').value = pick.name; $('dsel').onchange = () => loadDataset(st.datasets.find(d => d.name === $('dsel').value));
  await loadDataset(pick);
}
function clearDataset() {
  for (const m of V.meshes) { V.group.remove(m); m.geometry.dispose(); m.material.dispose(); }
  V.meshes = []; st.ds = null; V.bbox = null; V.hot = null; $('parts').innerHTML = ''; $('legend').hidden = true;
  $('scalar').innerHTML = '<option value="">(geometría)</option>'; V.needs = true;
}
async function loadDataset(d) {
  clearDataset(); LS.set('scc_ds_' + st.case, d.name);
  $('vbusy').hidden = false; $('vbusytxt').textContent = `cargando ${d.name}…`; $('vempty').hidden = true;
  try {
    const man = d.manifest;
    const [pos, idx] = await Promise.all([fetch(`${d.url}/positions.f32?v=${d.mtime}`).then(r => r.arrayBuffer()), fetch(`${d.url}/indices.u32?v=${d.mtime}`).then(r => r.arrayBuffer())]);
    const P = new Float32Array(pos), I = new Uint32Array(idx);
    const scal = {};
    await Promise.all(man.scalars.map(async s => { scal[s.name] = new Float32Array(await fetch(`${d.url}/${s.file}?v=${d.mtime}`).then(r => r.arrayBuffer())); }));
    st.ds = { ...d, P, I, scal, parts: [] };
    V.bbox = new THREE.Box3();
    man.parts.forEach((p, k) => {
      if (!p.ni) return;
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(P.subarray(p.v0 * 3, (p.v0 + p.nv) * 3), 3));
      const li = new Uint32Array(p.ni); for (let i = 0; i < p.ni; i++) li[i] = I[p.i0 + i] - p.v0;
      g.setIndex(new THREE.BufferAttribute(li, 1));
      g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(p.nv * 3), 3));
      g.computeVertexNormals(); g.computeBoundingBox(); V.bbox.union(g.boundingBox);
      const mat = new THREE.MeshStandardMaterial({ vertexColors: true, side: THREE.DoubleSide, roughness: 0.7, metalness: 0.05, clippingPlanes: $('clipon').checked ? [V.clip] : [], transparent: true, opacity: 0 });
      const mesh = new THREE.Mesh(g, mat); const part = { ...p, mesh, color: PART_COLORS[k % PART_COLORS.length], k };
      mesh.userData.part = part; V.group.add(mesh); V.meshes.push(mesh); st.ds.parts.push(part);
    });
    $('scalar').innerHTML = '<option value="">(geometría)</option>' + man.scalars.map(s => `<option value="${esc(s.name)}">${esc(s.name)}</option>`).join('');
    const ws = LS.get('scc_scalar'); st.scalar = man.scalars.some(s => s.name === ws) ? ws : (man.scalars[0]?.name || '');
    $('scalar').value = st.scalar; st.range = null;
    renderParts(); applyColors(); fit(0); setView('iso');
    $('vstate').textContent = `${man.n_triangles.toLocaleString('es')} triángulos · ${man.parts.length} superficies${man.exported ? ' · ' + man.exported : ''}`;
    fadeIn();
  } catch (e) { toast('No pude cargar las superficies: ' + e.message, 'error'); $('vempty').hidden = false; }
  $('vbusy').hidden = true;
}
function fadeIn() {  // las superficies aparecen suaves
  const t0 = performance.now();
  const step = t => { const k = Math.min(1, (t - t0) / 500); for (const m of V.meshes) m.material.opacity = k; V.needs = true; if (k < 1) requestAnimationFrame(step); else for (const m of V.meshes) m.material.transparent = false; };
  requestAnimationFrame(step);
}
function renderParts() {
  const ul = $('parts'); ul.innerHTML = '';
  for (const p of st.ds.parts) {
    const li = document.createElement('li'); p.li = li;
    li.innerHTML = `<input type="checkbox" checked aria-label="ver"><span class="sw" style="background:#${p.color.toString(16).padStart(6, '0')}"></span><span class="n" title="${esc(p.name)}">${esc(p.name)}</span><span class="c">${(p.ni / 3).toLocaleString('es')}</span>`;
    li.querySelector('input').onchange = e => { p.mesh.visible = e.target.checked; V.needs = true; };
    li.onclick = e => { if (e.target.tagName !== 'INPUT') flyTo(p); };
    li.onmouseenter = () => setHot(p); li.onmouseleave = () => setHot(null);
    ul.appendChild(li);
  }
}
function applyColors() {
  if (!st.ds) return;
  const a = st.scalar ? st.ds.scal[st.scalar] : null;
  const meta = st.ds.manifest.scalars.find(s => s.name === st.scalar);
  let lo = meta?.min ?? 0, hi = meta?.max ?? 1;
  if (st.range) { lo = st.range[0]; hi = st.range[1]; }
  $('rmin').value = a ? +lo.toPrecision(5) : ''; $('rmax').value = a ? +hi.toPrecision(5) : '';
  const c = [0, 0, 0];
  for (const p of st.ds.parts) {
    const col = p.mesh.geometry.getAttribute('color'); const arr = col.array;
    if (!a) { const base = new THREE.Color(p.color); for (let i = 0; i < p.nv; i++) { arr[3 * i] = base.r; arr[3 * i + 1] = base.g; arr[3 * i + 2] = base.b; } }
    else for (let i = 0; i < p.nv; i++) { const v = a[p.v0 + i]; if (!Number.isFinite(v)) { arr[3 * i] = arr[3 * i + 1] = arr[3 * i + 2] = 0.6; continue; } cmapColor((v - lo) / ((hi - lo) || 1), c); arr[3 * i] = c[0]; arr[3 * i + 1] = c[1]; arr[3 * i + 2] = c[2]; }
    col.needsUpdate = true;
  }
  drawLegend(a ? st.scalar : null, lo, hi); V.needs = true;
}
function drawLegend(name, lo, hi) {
  const lg = $('legend'); if (!name) { lg.hidden = true; return; }
  lg.hidden = false; $('lgtitle').textContent = name + (unitOf(name) ? ` (${unitOf(name).trim()})` : '');
  const cv = $('lgbar'), ctx = cv.getContext('2d'); const c = [0, 0, 0];
  for (let y = 0; y < cv.height; y++) { cmapColor(1 - y / (cv.height - 1), c); ctx.fillStyle = `rgb(${c[0] * 255 | 0},${c[1] * 255 | 0},${c[2] * 255 | 0})`; ctx.fillRect(0, y, cv.width, 1); }
  $('lgticks').innerHTML = [1, 0.75, 0.5, 0.25, 0].map(t => `<span>${sci(lo + (hi - lo) * t)}</span>`).join('');
}
$('scalar').onchange = () => { st.scalar = $('scalar').value; LS.set('scc_scalar', st.scalar); st.range = null; applyColors(); };
$('cmap').value = st.cmap; $('cmap').onchange = () => { st.cmap = $('cmap').value; LS.set('scc_cmap', st.cmap); applyColors(); };
const setRange = () => { const a = parseFloat($('rmin').value), b = parseFloat($('rmax').value); if (Number.isFinite(a) && Number.isFinite(b) && b > a) { st.range = [a, b]; applyColors(); } };
$('rmin').onchange = setRange; $('rmax').onchange = setRange;
$('rauto').onclick = () => { st.range = null; applyColors(); };
for (const b of $('vactions').querySelectorAll('[data-view]')) b.onclick = () => setView(b.dataset.view);
$('fit').onclick = () => fit();
$('spin').onclick = () => { V.spin = !V.spin; $('spin').setAttribute('aria-pressed', V.spin); };
$('wire').onclick = () => { V.wire = !V.wire; $('wire').setAttribute('aria-pressed', V.wire); for (const m of V.meshes) m.material.wireframe = V.wire; V.needs = true; };
function updateClip() {
  const on = $('clipon').checked; const ax = $('clipax').value; const t = +$('clipv').value / 1000;
  if (V.bbox) { const n = { X: [-1, 0, 0], Y: [0, -1, 0], Z: [0, 0, -1] }[ax]; const i = 'XYZ'.indexOf(ax);
    const v = V.bbox.min.getComponent(i) + (V.bbox.max.getComponent(i) - V.bbox.min.getComponent(i)) * t;
    V.clip.normal.set(...n); V.clip.constant = v; }
  for (const m of V.meshes) { m.material.clippingPlanes = on ? [V.clip] : []; m.material.needsUpdate = true; }
  V.needs = true;
}
$('clipon').onchange = updateClip; $('clipax').onchange = updateClip; $('clipv').oninput = updateClip;

// exportar del solver
$('exportbtn').onclick = e => { e.preventDefault(); e.stopPropagation(); $('expdlg').showModal(); };
$('expcancel').onclick = () => $('expdlg').close();
$('expform').onsubmit = async e => {
  e.preventDefault(); $('expdlg').close();
  if (!st.status.alive) { toast('Hace falta un solver vivo: pide a Claude server_start con sims/' + st.case + '.sim', 'warn'); return; }
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
  ul.innerHTML = d.images.map(im => `<li data-f="${esc(im.file)}"><span>${esc(im.label)}</span><button class="sm mini regen" data-n="${esc(im.file.replace(/\.png$/, ''))}" title="Volver a exportar desde el solver (export_scene)">↻</button></li>`).join('') || '<li class="mut">sin escenas en images/</li>';
  for (const b of [...tabs.querySelectorAll('[role=tab]'), ...ul.querySelectorAll('li[data-f]')]) {
    const f = b.dataset.view || b.dataset.f; const im = d.images.find(x => x.file === f);
    b.onclick = e => { if (e.target.classList.contains('regen')) return; showView(f, url(im)); };
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
  img.hidden = is3d; $('vtools').hidden = !is3d; $('vactions').hidden = !is3d; $('legend').hidden = !is3d || !st.scalar || !st.ds; $('vempty').hidden = !is3d || !!st.ds;
  if (!is3d) { const im = st.data?.images.find(x => x.file === v); if (im) img.src = src || `/files/${encodeURIComponent(st.case)}/images/${encodeURIComponent(im.file)}?v=${im.mtime}`; img.onclick = () => { $('lightbox').querySelector('img').src = img.src; $('lightbox').querySelector('.lb-cap').textContent = v; $('lightbox').hidden = false; }; }
  else V.needs = true;
}
document.querySelector('.vtabs [data-view="3d"]').onclick = () => showView('3d');
$('lightbox').onclick = () => { $('lightbox').hidden = true; };

// ---------------------------------------------------------------- árbol del .sim (inspect tree)
const KINDS = { solver: 'Solver', part: 'Partes', region: 'Regiones', boundary: 'Fronteras', physics: 'Física', model: 'Modelos', mesh_op: 'Operaciones de malla', mesher: 'Malladores', report: 'Reportes', monitor: 'Monitores', scene: 'Escenas', continuum: 'Continuos', interface: 'Interfaces' };
async function loadTree(refresh) {
  if (refresh) { $('treerefresh').disabled = true; $('treestate').textContent = 'leyendo del solver…'; $('n-sim').open = true; }
  let r; try { r = await api('/api/tree' + (refresh ? '?refresh=1' : '')); } catch (e) { $('treestate').textContent = e.message; $('treerefresh').disabled = false; return; }
  $('treerefresh').disabled = false;
  if (!r.tree) { $('treestate').textContent = 'sin lectura: pulsa ↻ con el solver vivo'; $('simtree').innerHTML = ''; $('b-sim').textContent = ''; return; }
  $('treestate').textContent = `leído ${new Date(r.at * 1000).toLocaleTimeString('es')}${r.alive ? '' : ' (solver apagado)'}`;
  $('b-sim').textContent = Object.values(r.tree).reduce((n, v) => n + v.length, 0);
  $('simtree').innerHTML = Object.entries(r.tree).map(([k, items]) => `<details><summary>${esc(KINDS[k] || k)} <span class="badge">${items.length}</span></summary><ul>${items.map(it => `<li><span>${esc(it.name)}</span>${it.type ? `<span class="t">${esc(it.type)}</span>` : ''}${it.value != null ? `<span class="v">${esc(it.value)}</span>` : ''}</li>`).join('')}</ul></details>`).join('');
}
$('treerefresh').onclick = e => { e.preventDefault(); e.stopPropagation(); loadTree(true); };

// ---------------------------------------------------------------- dock: salida, gráficos, resumen
function openTab(t) {
  st.tab = t; LS.set('scc_tab', t);
  for (const b of document.querySelectorAll('.dock-tabs [role=tab]')) b.setAttribute('aria-selected', b.dataset.tab === t);
  for (const id of ['out', 'plots', 'res']) $('tab-' + id).hidden = id !== t;
  if (t === 'out') loadProgress();
}
for (const b of document.querySelectorAll('.dock-tabs [role=tab]')) b.onclick = () => openTab(b.dataset.tab);
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
  const xt = xs.map(v => `<text x="${sx(v)}" y="${H - 10}" class="tick" text-anchor="middle">${v}</text>`).join('');
  const path = xs.map((v, i) => `${i ? 'L' : 'M'}${sx(v).toFixed(1)},${sy(ys[i]).toFixed(1)}`).join(' ');
  const dots = xs.map((v, i) => `<circle cx="${sx(v)}" cy="${sy(ys[i])}" r="4" class="pt"><title>iter ${v}: ${label} = ${fmt(ys[i], dec)} ${unit}</title></circle>`).join('');
  const last = `<text x="${sx(xs[xs.length - 1]) - 6}" y="${sy(ys[ys.length - 1]) - 8}" class="lbl" text-anchor="end">${fmt(ys[ys.length - 1], dec)} ${unit}</text>`;
  return `<figure class="chart"><figcaption>${esc(label)} <span class="mut">(${esc(unit)}) frente a iteración</span></figcaption><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)} frente a iteración">${grid}<line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" class="axis"/>${xt}<path d="${path}" class="line"/>${dots}${last}</svg></figure>`;
}
function renderConv(d) {
  const c = $('conv'), cv = d.convergencia;
  if (!cv || !cv.rows.length) { c.innerHTML = '<p class="mut">Sin reports/convergencia.csv. Pide a Claude que corra iteraciones y lo escriba.</p>'; return; }
  const col = n => { const k = cv.columns.indexOf(n); return k < 0 ? null : cv.rows.map(r => r[k]); };
  const it = col('iter') || cv.rows.map((_, i) => i + 1);
  const units = { H: 'm', M: 'N·m' };
  const charts = ['H', 'M'].map(k => col(k) ? chart(it, col(k), k, units[k]) : '').join('');
  const delta = k => { const v = col(k); if (!v || v.length < 2 || !v[v.length - 1]) return null; return Math.abs((v[v.length - 1] - v[v.length - 2]) / v[v.length - 1] * 100); };
  const dH = delta('H'), dM = delta('M');
  const crit = dH != null ? `<p class="small">Último bloque: ΔH ${fmt(dH, 2)} % · ΔM ${fmt(dM, 2)} % ${dH < 0.5 && dM < 0.5 ? '<span class="tag ok">convergido (&lt; 0,5 %)</span>' : '<span class="tag warn">aún no (&gt; 0,5 %)</span>'}</p>` : '';
  const table = `<table class="data"><tr>${cv.columns.map(h => `<th>${esc(h)}</th>`).join('')}</tr>${cv.rows.map(r => '<tr>' + r.map((v, i) => `<td class="num">${v == null ? '–' : i === 0 ? v : sci(v)}</td>`).join('') + '</tr>').join('')}</table>`;
  c.innerHTML = `<div class="charts">${charts}</div>${crit}<details><summary>${esc(cv.file)} · ${cv.rows.length} filas</summary>${table}</details>`;
}

// salida (la «terminal»)
const prog = { key: '' };
const hlLine = l => { const c = /AGENT_ERROR|Exception|error|Error|FAIL/.test(l) ? 'err' : /AGENT_BEGIN|AGENT_END|Playing macro|SAVED|PNG |SCENE |CASE /.test(l) ? 'hl' : /complete|Server::start|converged/i.test(l) ? 'ok' : ''; return c ? `<span class="${c}">${esc(l)}</span>` : esc(l); };
async function loadProgress() {
  let p; try { p = await api('/api/progress'); } catch (e) { $('macrostate').textContent = e.message; return; }
  const m = p.macro; $('progdot').hidden = !(m && m.running && st.status.alive);
  if (m) { const t0 = new Date(m.started * 1000).toLocaleTimeString('es');
    $('macrostate').innerHTML = m.running && st.status.alive ? `Macro <b>${esc(m.file)}</b> en marcha desde ${t0} <span class="tag ok">corriendo</span>` : `Última macro <b>${esc(m.file)}</b> · ${t0}${m.finished ? ' → ' + new Date(m.finished * 1000).toLocaleTimeString('es') : ''} <span class="tag">${m.running ? 'sin salida' : 'terminada'}</span>`; }
  else $('macrostate').textContent = 'Sin macros inyectadas todavía.';
  const key = `${p.server_log.file}|${p.server_log.size}|${(p.agent_log || []).slice(-1)[0] || ''}|${m?.file}|${m?.out?.length}`;
  if (key !== prog.key) { prog.key = key;
    const lines = p.server_log.tail.length ? p.server_log.tail : ['(sin log del servidor todavía)'];
    $('term').innerHTML = lines.map(hlLine).join('\n') + (m?.out?.length ? `\n\n<span class="hl">--- ${esc(m.file)} salida</span>\n` + m.out.map(hlLine).join('\n') : '') + (p.agent_log.length ? '\n\n<span class="hl">--- agent.log</span>\n' + p.agent_log.map(esc).join('\n') : '');
    if ($('progfollow').checked) $('term').scrollTop = 1e9; }
}
setInterval(() => { if (st.tab === 'out' && !$('stage').classList.contains('dock-collapsed')) loadProgress(); }, 3000);

// ---------------------------------------------------------------- estado del solver
function renderStatus(s) {
  st.status = s;
  const dot = s.alive ? 'ok' : s.stale ? 'busy' : 'off';
  const txt = s.stopping ? 'apagando solver…' : s.alive ? `solver vivo · puerto ${s.port} · ${s.idle_min ?? '?'} min sin actividad` : s.stale ? 'solver caído (.server.json viejo)' : 'solver apagado';
  $('solver').innerHTML = `<span class="dot ${dot}"></span><span>${esc(txt)}</span>` + ((s.chatting || st.chatting) ? ' <span class="dot chat"></span><span>Claude trabajando</span>' : '');
  $('stopsolver').hidden = !s.alive; $('stopsolver').disabled = !!s.stopping;
  $('opengui').disabled = !!s.alive; $('opengui').title = s.alive ? 'Hay un servidor batch vivo: apágalo antes de abrir la GUI' : 'Abre este .sim en la GUI de STAR-CCM+ (la licencia PoD cobra por hora)';
  $('solvertag').innerHTML = s.alive ? '<span class="tag ok">vivo</span>' : s.stale ? '<span class="tag warn">caído</span>' : '<span class="tag">apagado</span>';
  const rows = s.alive || s.stale ? [['pid', s.pid], ['puerto', s.port], ['sim', s.sim ? s.sim.split(/[\\/]/).pop() : '(nueva)'], ['procesos', s.np], ['arranque', s.started ? s.started.replace('T', ' ') : '–'], ['inactivo', s.idle_min != null ? `${fmt(s.idle_min, 0)} / ${s.idle_limit_min} min` : '–']] : [['apagado por inactividad', `${s.idle_limit_min} min`]];
  $('solverkv').querySelector('tbody').innerHTML = rows.map(([k, v]) => `<tr><td class="mut">${esc(k)}</td><td class="mono" title="${esc(v)}">${esc(v)}</td></tr>`).join('');
}
async function poll() {
  try { renderStatus(await api('/api/status')); $('offline').hidden = true; }
  catch (e) { $('offline').hidden = false; $('offlinetxt').textContent = 'Sin conexión con el servidor local: ' + e.message; }
}
$('retry').onclick = poll; setInterval(poll, 5000);
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
function setChatting(on) { st.chatting = on; $('send').disabled = on; $('stopchat').disabled = !on; if (st.status.alive != null) renderStatus(st.status); }
function onChatEvent(ev, ctx) {
  if (['result', 'error'].includes(ev.kind) && /No conversation found/i.test(ev.text || '')) { ctx.stale = true; return; }
  if (ev.kind === 'result' && ev.turns === 0 && ev.subtype !== 'success' && !ev.text) return;
  if (ev.kind === 'init') { st.session = ev.session_id; LS.set('scc_session', st.session); $('chatstate').textContent = `sesión ${st.session.slice(0, 8)} · ${ev.model || ''}`; }
  else if (ev.kind === 'text') { addMsg('bot', md(ev.text)); ctx.tool = ''; $('chatstate').textContent = 'pensando…'; }
  else if (ev.kind === 'tool') {
    addMsg('tool', `<details><summary>Tool: ${esc(toolSummary(ev.name, ev.input || {}))}</summary>${esc(JSON.stringify(ev.input || {}, null, 1)).slice(0, 2000)}</details>`);
    ctx.tool = ev.name; ctx.t0 = Date.now(); $('chatstate').textContent = `ejecutando ${ev.name}…`;
    if (/server_|export_scene|iterate|run_java|save/.test(ev.name)) ctx.refresh = true;
  }
  else if (ev.kind === 'tool_result') { if (ev.is_error) addMsg('tool bad', 'Error de tool: ' + esc(ev.text)); else if (/server_/.test(ctx.tool)) poll(); if (st.tab === 'out') loadProgress(); }
  else if (ev.kind === 'status') $('chatstate').textContent = ev.text;
  else if (ev.kind === 'ping') { if (!ctx.tool) $('chatstate').textContent = `trabajando… ${ev.t} s`; }
  else if (ev.kind === 'error') addMsg('err', /conversación en curso/.test(ev.text) ? 'Ya hay una conversación en curso. Espera o pulsa Detener.' : esc(ev.text));
  else if (ev.kind === 'result') { ctx.tool = ''; if (ev.text) addMsg('err', esc(ev.text)); $('chatstate').textContent = `listo · ${ev.turns ?? '?'} turnos · ${ev.seconds} s`; }
  else if (ev.kind === 'stopped') { addMsg('bot mut', 'Detenido por el usuario.'); ctx.tool = ''; $('chatstate').textContent = 'detenido'; }
  else if (ev.kind === 'done') { ctx.done = true; if (ev.rc && ev.rc !== 0 && !/listo|detenido/.test($('chatstate').textContent)) $('chatstate').textContent = `terminó con código ${ev.rc}`; }
  if (!ctx.login && ['text', 'result', 'error'].includes(ev.kind) && /401|not logged in|OAuth|auth login/i.test(ev.text || '')) { ctx.login = true; addMsg('err', 'La CLI de Claude Code no tiene sesión. En una terminal ejecuta: <code>claude auth login</code>'); }
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
    while (true) { const { value, done } = await reader.read(); if (done) break; buf += dec.decode(value, { stream: true });
      let idx; while ((idx = buf.indexOf('\n\n')) >= 0) { const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2); if (!chunk.startsWith('data: ')) continue; let ev; try { ev = JSON.parse(chunk.slice(6)); } catch { continue; } onChatEvent(ev, ctx); } }
    if (!ctx.done && st.chatting) throw new Error('el flujo se cortó');
  } catch (e) {
    const d = addMsg('err', `Se cortó la conexión con el chat (${esc(String(e.message || e))}). Tu mensaje no se perdió:<div class="actions"><button class="sm">Reenviar</button></div>`);
    d.querySelector('button').onclick = () => { $('chattext').value = text; sendChat(); }; $('chatstate').textContent = 'conexión perdida';
  }
  clearInterval(clock); setChatting(false); poll();
  if (ctx.refresh && st.case) openCase(st.case);
  if (ctx.stale && !retry) { st.session = null; LS.set('scc_session', null); addMsg('bot mut', 'La conversación anterior ya no existe; empiezo una nueva con tu mensaje.'); $('chattext').value = text; sendChat(true); }
}
$('send').onclick = () => sendChat();
$('chattext').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); } else if (e.key === 'ArrowUp' && !$('chattext').value && st.lastMsg) { e.preventDefault(); $('chattext').value = st.lastMsg; } });
$('stopchat').onclick = () => { $('stopchat').disabled = true; $('chatstate').textContent = 'deteniendo…'; api('/api/chat/stop', {}).then(j => { if (!j.stopped) $('chatstate').textContent = 'no había nada que detener'; }).catch(e => { $('chatstate').textContent = 'no pude detener: ' + e.message; }); };
$('newchat').onclick = () => {
  if (!armed($('newchat'), '¿Seguro?', 4000)) return;
  st.session = null; LS.set('scc_session', null);
  for (const m of $('chatlog').querySelectorAll('.m')) m.remove(); placeQuick(); $('chatstate').textContent = 'nueva conversación'; };
for (const b of $('quick').querySelectorAll('[data-q]')) b.onclick = () => { $('chattext').value = b.dataset.q.replace('<caso>', st.case || 'caso'); sendChat(); };
st.session = LS.get('scc_session'); if (st.session) $('chatstate').textContent = `sesión ${st.session.slice(0, 8)} (continúa)`;

// parámetros -> prompt (la página nunca edita el .sim)
const PARAMS = [['p_rpm', v => `velocidad de giro del rotor a ${v} rpm (MRF)`], ['p_mdot', v => `caudal másico de entrada a ${v} kg/s`], ['p_base', v => `tamaño base de malla a ${v} mm (remallar las 3 operaciones)`], ['p_iter', v => `luego corre ${v} iteraciones (en bloques de 100 con iterate)`]];
$('paskbtn').onclick = () => {
  const parts = PARAMS.map(([id, f]) => { const v = $(id).value.trim(); return v ? f(v) : ''; }).filter(Boolean);
  if (!parts.length) { toast('Rellena al menos un parámetro', 'warn'); return; }
  $('chattext').value = `En la simulación sims/${st.case}.sim (server_start la reutiliza si está viva): cambia ${parts.join('; ')}. Precompila cada macro y usa las recetas bomba-*. Al terminar, añade las filas a cases/${st.case}/reports/convergencia.csv, vuelve a exportar las escenas de presión, velocidad e y+ a images/, exporta las superficies con campo (receta exportar-superficies-ensight) y dime H, M y eficiencia en una tabla frente a los valores anteriores.`;
  sendChat();
};
$('pclear').onclick = () => { for (const [id] of PARAMS) $(id).value = ''; };

// ---------------------------------------------------------------- tema y teclado
const theme = LS.get('scc_theme', 'light'); document.documentElement.dataset.theme = theme;
$('theme').onclick = () => { const nx = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = nx; LS.set('scc_theme', nx); };
addEventListener('keydown', e => {
  if (e.target.matches('input,textarea,select')) return;
  if (e.key === 'f' || e.key === 'F') fit(); else if (e.key === '1') setView('iso'); else if (e.key === '2') setView('axial'); else if (e.key === '3') setView('lateral');
  else if (e.key === '`') $('docktoggle').click(); else if (e.key === 'Escape') { $('lightbox').hidden = true; }
});

// ---------------------------------------------------------------- arranque
initViewer(); placeQuick(); openTab(['out', 'plots', 'res'].includes(st.tab) ? st.tab : 'out'); poll();
loadCases().catch(e => { toast('No pude leer los casos: ' + e.message, 'error'); });
