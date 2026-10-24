"""Superficies con campo para el visor 3D: EnSight Gold (lo que exporta ImportManager.export de
STAR-CCM+ con un .case) -> un dataset compacto para three.js.

Dataset en cases/<caso>/surfaces/<nombre>/:
  manifest.json   {parts:[{name, v0, nv, i0, ni}], scalars:[{name, min, max}], bbox, n_vertices, n_triangles}
  positions.f32   xyz por vértice (float32, little-endian), todas las partes seguidas
  indices.u32     triángulos (uint32, índices globales)
  <scalar>.f32    un valor por vértice (float32); los «por elemento» se promedian a los vértices

También lee STL (ASCII o binario) como geometría sin campo (p.ej. la de CFturbo).
Sin numpy: array/struct puros; una bomba de ~200 k triángulos tarda unos segundos.
"""
from __future__ import annotations

import array
import json
import math
import re
import struct
import sys
from pathlib import Path

ELEM_NODES = {"point": 1, "bar2": 2, "bar3": 3, "tria3": 3, "tria6": 6, "quad4": 4, "quad8": 8,
              "tetra4": 4, "tetra10": 10, "pyramid5": 5, "pyramid13": 13, "penta6": 6, "penta15": 15,
              "hexa8": 8, "hexa20": 20}
SURFACE_ELEMS = {"tria3", "tria6", "quad4", "quad8", "nsided"}
ELEM_KEYWORDS = set(ELEM_NODES) | {"nsided", "nfaced"}


class Dataset:
    def __init__(self) -> None:
        self.parts: list[dict] = []          # name, v0, nv, i0, ni, (part_id)
        self.xyz = array.array("f")
        self.idx = array.array("I")
        self.scalars: dict[str, array.array] = {}

    # ---- construcción
    def add_part(self, name: str, xyz: array.array, tris: array.array, part_id: int | None = None) -> dict:
        v0, i0 = len(self.xyz) // 3, len(self.idx)
        self.xyz.extend(xyz)
        self.idx.extend(array.array("I", (t + v0 for t in tris)))
        p = {"name": name, "v0": v0, "nv": len(xyz) // 3, "i0": i0, "ni": len(tris), "id": part_id}
        self.parts.append(p)
        return p

    # ---- escritura
    def write(self, out: Path, extra: dict | None = None) -> dict:
        out.mkdir(parents=True, exist_ok=True)
        (out / "positions.f32").write_bytes(_le(self.xyz).tobytes())
        (out / "indices.u32").write_bytes(_le(self.idx).tobytes())
        scal = []
        for name, vals in self.scalars.items():
            fn = _safe(name) + ".f32"
            (out / fn).write_bytes(_le(vals).tobytes())
            finite = [v for v in vals if math.isfinite(v)]
            scal.append({"name": name, "file": fn, "min": min(finite) if finite else 0.0, "max": max(finite) if finite else 0.0})
        xs, ys, zs = self.xyz[0::3], self.xyz[1::3], self.xyz[2::3]
        man = {"parts": [{k: v for k, v in p.items() if k != "id"} for p in self.parts], "scalars": scal,
               "n_vertices": len(self.xyz) // 3, "n_triangles": len(self.idx) // 3,
               "bbox": [[min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]] if len(xs) else None,
               **(extra or {})}
        (out / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        return man


def _le(a: array.array) -> array.array:
    if sys.byteorder == "big":
        b = array.array(a.typecode, a)
        b.byteswap()
        return b
    return a


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", s).strip("_") or "x"


def _fan(poly: list[int]) -> list[int]:
    out: list[int] = []
    for k in range(1, len(poly) - 1):
        out += [poly[0], poly[k], poly[k + 1]]
    return out


def _add_surface_elem(tris: array.array, per_elem: list[list[int]], et: str, poly: list[int]) -> None:
    """Triangula un elemento de superficie (abanico; tria6 y quad8 solo con sus vértices de esquina) y apunta sus triángulos."""
    t = _fan(poly[:3] if et == "tria6" else poly[:4] if et == "quad8" else poly)
    per_elem.append(list(range(len(tris) // 3, len(tris) // 3 + len(t) // 3)))
    tris.extend(t)


# ---------------------------------------------------------------- EnSight Gold: .case
def read_case(case_file: Path) -> dict:
    """{'geometry': Path, 'scalars': [{'name', 'file', 'per': 'node'|'element'}], 'vectors': [...]}"""
    d = case_file.parent
    out: dict = {"geometry": None, "scalars": [], "vectors": []}
    for raw in case_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        low = line.lower()
        if low.startswith("model:"):
            toks = line.split(":", 1)[1].split()
            toks = [t for t in toks if not t.isdigit()]
            if toks:
                out["geometry"] = d / toks[-1].replace("*", "0")  # ponytail: sin series temporales
        elif low.startswith(("scalar per node:", "scalar per element:", "vector per node:", "vector per element:")):
            kind, rest = line.split(":", 1)
            toks = rest.split()
            while toks and toks[0].isdigit():
                toks.pop(0)
            if len(toks) < 2:
                continue
            fn = toks[-1].replace("*", "0")  # STAR-CCM+ escribe «nombre*****.Pressure»: índice 00000 sin series temporales
            name = " ".join(toks[:-1])
            item = {"name": name, "file": d / fn, "per": "node" if "node" in kind.lower() else "element"}
            out["scalars" if kind.lower().startswith("scalar") else "vectors"].append(item)
    return out


def _is_binary(p: Path) -> bool:
    head = p.read_bytes()[:80]
    return b"Binary" in head or b"binary" in head


class _Bin:
    """Lector de EnSight «C Binary»: cadenas de 80 bytes, int32 y float32; detecta el orden de bytes."""

    def __init__(self, data: bytes) -> None:
        self.b = memoryview(data)
        self.pos = 0
        self.e = "<"

    def s80(self) -> str:
        self._need(80)
        s = bytes(self.b[self.pos:self.pos + 80]).split(b"\0", 1)[0].decode("latin-1").strip()
        self.pos += 80
        return s

    def i(self) -> int:
        self._need(4)
        v = struct.unpack_from(self.e + "i", self.b, self.pos)[0]
        self.pos += 4
        return v

    def _need(self, n: int) -> None:
        if n < 0 or self.pos + n > len(self.b):
            raise ValueError(f"EnSight truncado en el byte {self.pos} (faltan {self.pos + n - len(self.b)} bytes)")

    def _arr(self, code: str, n: int) -> array.array:
        self._need(4 * n)
        a = array.array(code)
        a.frombytes(bytes(self.b[self.pos:self.pos + 4 * n]))
        self.pos += 4 * n
        if (self.e == "<") != (sys.byteorder == "little"):
            a.byteswap()
        return a

    def ints(self, n: int) -> array.array:
        return self._arr("i", n)

    def floats(self, n: int) -> array.array:
        return self._arr("f", n)

    def peek_s80(self) -> str:
        p = self.pos
        s = self.s80()
        self.pos = p
        return s

    def eof(self) -> bool:
        return self.pos >= len(self.b)


def _sane_count(n: int) -> bool:
    return 0 <= n < 65536  # un part id real es pequeño; en el orden equivocado un id <= 11 daría >= 16 777 216


def read_geometry(geo: Path) -> tuple[Dataset, dict]:
    """Devuelve el dataset (solo elementos de superficie) y, por parte, el mapa de elementos para los
    campos «por elemento»: {part_id: [(tipo, n_elem, [índices de triángulo por elemento])]}."""
    return (_read_geo_binary if _is_binary(geo) else _read_geo_ascii)(geo)


def _read_geo_ascii(geo: Path) -> tuple[Dataset, dict]:
    lines = geo.read_text(encoding="utf-8", errors="replace").splitlines()
    ds, emap = Dataset(), {}
    node_id_given = element_id_given = False
    k = 0
    n = len(lines)

    def tok(i: int) -> str:
        return lines[i].strip()

    while k < n and tok(k).lower() != "part":
        low = tok(k).lower()
        if low.startswith("node id") and ("given" in low or "ignore" in low):
            node_id_given = True
        if low.startswith("element id") and ("given" in low or "ignore" in low):
            element_id_given = True
        k += 1
    while k < n:
        if tok(k).lower() != "part":
            k += 1
            continue
        pid = int(tok(k + 1))
        name = tok(k + 2) or f"part {pid}"
        k += 3
        xyz = array.array("f")
        if k < n and tok(k).lower() == "coordinates":
            nv = int(tok(k + 1))
            k += 2
            if node_id_given:
                k += nv
            xs = [float(tok(k + i)) for i in range(nv)]
            ys = [float(tok(k + nv + i)) for i in range(nv)]
            zs = [float(tok(k + 2 * nv + i)) for i in range(nv)]
            k += 3 * nv
            for i in range(nv):
                xyz.extend((xs[i], ys[i], zs[i]))
        tris = array.array("I")
        elems: list[tuple[str, int, list[list[int]]]] = []
        while k < n and tok(k).lower() != "part":
            et = tok(k).lower()
            if et not in ELEM_KEYWORDS:
                k += 1
                continue
            ne = int(tok(k + 1))
            k += 2
            if element_id_given:
                k += ne
            per_elem: list[list[int]] = []
            if et == "nsided":
                counts = [int(tok(k + i)) for i in range(ne)]
                k += ne
                for c in counts:
                    _add_surface_elem(tris, per_elem, et, [int(x) - 1 for x in lines[k].split()])
                    k += 1
            elif et == "nfaced":  # volumen: saltar
                nf = [int(tok(k + i)) for i in range(ne)]
                k += ne
                total = sum(nf)
                k += total  # cuentas de nodos por cara
                k += total  # nodos de cada cara
                per_elem = [[] for _ in range(ne)]
            else:
                nn = ELEM_NODES[et]
                for _ in range(ne):
                    poly = [int(x) - 1 for x in lines[k].split()[:nn]]
                    k += 1
                    if et in SURFACE_ELEMS:
                        _add_surface_elem(tris, per_elem, et, poly)
                    else:
                        per_elem.append([])
            elems.append((et, ne, per_elem))
        p = ds.add_part(name, xyz, tris, pid)
        emap[pid] = (p, elems)
    return ds, emap


def _read_geo_binary(geo: Path) -> tuple[Dataset, dict]:
    r = _Bin(geo.read_bytes())
    ds, emap = Dataset(), {}
    r.s80()  # C Binary
    r.s80(); r.s80()  # descripciones
    s = r.s80()
    node_id_given = "given" in s or "ignore" in s
    s = r.s80()
    element_id_given = "given" in s or "ignore" in s
    if r.peek_s80().lower().startswith("extents"):
        r.s80(); r.floats(6)
    while not r.eof():
        s = r.s80()
        if s.lower() != "part":
            break
        pid = r.i()
        if not _sane_count(pid):
            alt = struct.unpack(">i" if r.e == "<" else "<i", struct.pack(r.e + "i", pid))[0]
            if _sane_count(alt):  # solo si el otro orden da un id plausible
                r.e = ">" if r.e == "<" else "<"
                pid = alt
        name = r.s80() or f"part {pid}"
        xyz = array.array("f")
        if r.peek_s80().lower() == "coordinates":
            r.s80()
            nv = r.i()
            if node_id_given:
                r.ints(nv)
            xs, ys, zs = r.floats(nv), r.floats(nv), r.floats(nv)
            for i in range(nv):
                xyz.extend((xs[i], ys[i], zs[i]))
        tris = array.array("I")
        elems: list[tuple[str, int, list[list[int]]]] = []
        while not r.eof() and r.peek_s80().lower() != "part":
            et = r.s80().lower()
            if et not in ELEM_KEYWORDS:
                break
            ne = r.i()
            if element_id_given:
                r.ints(ne)
            per_elem: list[list[int]] = []
            if et == "nsided":
                counts = r.ints(ne)
                nodes = r.ints(sum(counts))
                pos = 0
                for c in counts:
                    _add_surface_elem(tris, per_elem, et, [x - 1 for x in nodes[pos:pos + c]])
                    pos += c
            elif et == "nfaced":
                nf = r.ints(ne)
                npf = r.ints(sum(nf))
                r.ints(sum(npf))
                per_elem = [[] for _ in range(ne)]
            else:
                nn = ELEM_NODES[et]
                conn = r.ints(ne * nn)
                for e in range(ne):
                    poly = [x - 1 for x in conn[e * nn:(e + 1) * nn]]
                    if et in SURFACE_ELEMS:
                        _add_surface_elem(tris, per_elem, et, poly)
                    else:
                        per_elem.append([])
            elems.append((et, ne, per_elem))
        p = ds.add_part(name, xyz, tris, pid)
        emap[pid] = (p, elems)
    return ds, emap


def read_scalar(var: Path, per: str, ds: Dataset, emap: dict, ncomp: int = 1, binary: bool | None = None) -> array.array:
    """Un valor por vértice del dataset. per='element' -> promedio en los vértices del elemento.
    ncomp=3 (vector) -> magnitud. binary: el formato lo fija la geometría (los archivos de variables
    binarios no llevan la cabecera «C Binary»: su primera línea es la descripción)."""
    vals = array.array("f", [math.nan]) * (len(ds.xyz) // 3)
    if binary is None:
        binary = _is_binary(var)
    if binary:
        r = _Bin(var.read_bytes())
        r.s80()
        while not r.eof():
            s = r.s80().lower()
            if s != "part":
                break
            pid = r.i()
            if pid not in emap:
                break
            p, elems = emap[pid]
            if per == "node":
                r.s80()  # coordinates
                comps = [r.floats(p["nv"]) for _ in range(ncomp)]
                for i in range(p["nv"]):
                    vals[p["v0"] + i] = _mag(comps, i)
            else:
                for et, ne, per_elem in elems:
                    r.s80()
                    comps = [r.floats(ne) for _ in range(ncomp)]
                    _spread(vals, ds, p, per_elem, [_mag(comps, e) for e in range(ne)])
        return vals
    lines = var.read_text(encoding="utf-8", errors="replace").splitlines()
    k = 1
    n = len(lines)
    while k < n:
        if lines[k].strip().lower() != "part":
            k += 1
            continue
        pid = int(lines[k + 1])
        k += 2
        if pid not in emap:
            break
        p, elems = emap[pid]
        if per == "node":
            k += 1  # coordinates
            comps = [[float(lines[k + c * p["nv"] + i]) for i in range(p["nv"])] for c in range(ncomp)]
            k += ncomp * p["nv"]
            for i in range(p["nv"]):
                vals[p["v0"] + i] = _mag(comps, i)
        else:
            for et, ne, per_elem in elems:
                k += 1  # tipo de elemento
                comps = [[float(lines[k + c * ne + i]) for i in range(ne)] for c in range(ncomp)]
                k += ncomp * ne
                _spread(vals, ds, p, per_elem, [_mag(comps, e) for e in range(ne)])
    return vals


def _mag(comps, i: int) -> float:
    if len(comps) == 1:
        return comps[0][i]
    return math.sqrt(sum(c[i] * c[i] for c in comps))


def _spread(vals, ds: Dataset, p: dict, per_elem: list[list[int]], ev: list[float]) -> None:
    acc: dict[int, list[float]] = {}
    t0 = p["i0"] // 3  # los índices de triángulo de per_elem son locales a la parte
    for e, tris in enumerate(per_elem):
        for t in tris:
            for v in ds.idx[3 * (t0 + t):3 * (t0 + t) + 3]:
                acc.setdefault(v, []).append(ev[e])
    for v, xs in acc.items():
        vals[v] = sum(xs) / len(xs)


def convert_case(case_file: Path, out: Path, extra: dict | None = None) -> dict:
    info = read_case(case_file)
    if not info["geometry"] or not Path(info["geometry"]).is_file():
        raise FileNotFoundError(f"el .case no apunta a una geometría legible: {info['geometry']}")
    ds, emap = read_geometry(Path(info["geometry"]))
    binary = _is_binary(Path(info["geometry"]))
    for s in info["scalars"]:
        if Path(s["file"]).is_file():
            ds.scalars[s["name"]] = read_scalar(Path(s["file"]), s["per"], ds, emap, 1, binary)
    for v in info["vectors"]:
        if Path(v["file"]).is_file():
            ds.scalars[v["name"] + " |mag|"] = read_scalar(Path(v["file"]), v["per"], ds, emap, 3, binary)
    return ds.write(out, {"source": case_file.name, **(extra or {})})


# ---------------------------------------------------------------- STL (geometría sin campo)
def read_stl_solids(p: Path) -> list[tuple[str, array.array, array.array]]:
    """[(nombre, xyz, tris)] por «solid» (STL ASCII multi-sólido: STAR-CCM+ escribe uno por superficie de la parte);
    un STL binario es un solo sólido sin nombre. Vértices fusionados por coordenadas (sombreado suave)."""
    data = p.read_bytes()
    out = []

    def new():
        verts: dict[tuple, int] = {}
        xyz, tris = array.array("f"), array.array("I")

        def vid(x: float, y: float, z: float) -> int:
            key = (round(x, 7), round(y, 7), round(z, 7))
            i = verts.get(key)
            if i is None:
                i = len(xyz) // 3
                verts[key] = i
                xyz.extend((x, y, z))
            return i
        return xyz, tris, vid

    # STAR-CCM+ (exportStlPart ASCII) escribe « solid PRO2STL version 1.0»: con espacio delante y un solo sólido por parte
    if data.lstrip()[:5].lower() == b"solid" and b"facet" in data[:2000]:
        for m in re.finditer(rb"(?m)^[ \t]*solid[ \t]*([^\r\n]*)\r?\n(.*?)endsolid", data, re.S):
            xyz, tris, vid = new()
            nums = re.findall(rb"vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", m.group(2))
            for k in range(0, len(nums) - 2, 3):
                tris.extend(vid(*map(float, nums[k + j])) for j in range(3))
            name = m.group(1).decode("utf-8", "replace").strip()
            if len(tris):
                out.append(("" if name.upper().startswith("PRO2STL") else name, xyz, tris))
    else:
        xyz, tris, vid = new()
        n = struct.unpack_from("<I", data, 80)[0]
        for k in range(n):
            f = struct.unpack_from("<12f", data, 84 + k * 50)
            tris.extend((vid(f[3], f[4], f[5]), vid(f[6], f[7], f[8]), vid(f[9], f[10], f[11])))
        out.append(("", xyz, tris))
    return out


def read_stl(p: Path) -> tuple[array.array, array.array]:
    """(xyz, tris) del primer sólido."""
    s = read_stl_solids(p)
    return (s[0][1], s[0][2]) if s else (array.array("f"), array.array("I"))


def convert_stls(files: list[Path], out: Path, extra: dict | None = None, names: dict[str, str] | None = None) -> dict:
    """Un STL por parte (names: archivo -> nombre de la parte); cada sólido se llama «parte/cara» como las fronteras."""
    ds = Dataset()
    for f in files:
        part = (names or {}).get(f.name) or f.stem
        solids = read_stl_solids(f)
        for sname, xyz, tris in solids:
            sname = sname.rsplit("-", 1)[-1] if sname.startswith(("[", part)) else sname  # «[Impeller_1]-Flow domain-Hub» -> «Hub»
            ds.add_part(f"{part}/{sname}" if sname and sname != part else part, xyz, tris)
    return ds.write(out, {"source": "stl", **(extra or {})})


# ---------------------------------------------------------------- prueba: caso EnSight ASCII diminuto
def write_mini_case(d: Path) -> Path:
    """Dos partes: un cuadrado (quad4) con presión por nodo y un triángulo (nsided) con y+ por elemento."""
    d.mkdir(parents=True, exist_ok=True)
    (d / "mini.case").write_text("FORMAT\ntype: ensight gold\nGEOMETRY\nmodel: mini.geo\nVARIABLES\n"
                                 "scalar per node: Pressure mini.pre\nscalar per element: WallYplus mini.ypl\n"
                                 "vector per node: Velocity mini.vel\n", encoding="utf-8")
    (d / "mini.geo").write_text("mini\ngeo\nnode id off\nelement id off\npart\n1\nplano\ncoordinates\n4\n"
                                "0\n1\n1\n0\n0\n0\n1\n1\n0\n0\n0\n0\nquad4\n1\n1 2 3 4\n"
                                "part\n2\ntri\ncoordinates\n3\n2\n3\n2\n0\n0\n1\n0\n0\n0\nnsided\n1\n3\n1 2 3\n", encoding="utf-8")
    (d / "mini.pre").write_text("Pressure\npart\n1\ncoordinates\n100\n200\n300\n400\npart\n2\ncoordinates\n5\n6\n7\n", encoding="utf-8")
    (d / "mini.ypl").write_text("WallYplus\npart\n1\nquad4\n30\npart\n2\nnsided\n45\n", encoding="utf-8")
    (d / "mini.vel").write_text("Velocity\npart\n1\ncoordinates\n" + "\n".join(["3"] * 4 + ["4"] * 4 + ["0"] * 4) +
                                "\npart\n2\ncoordinates\n" + "\n".join(["1"] * 3 + ["0"] * 3 + ["0"] * 3) + "\n", encoding="utf-8")
    return d / "mini.case"


if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    man = convert_case(src, dst) if src.suffix == ".case" else convert_stls([src], dst)
    print(json.dumps({k: v for k, v in man.items() if k != "parts"}, indent=1), len(man["parts"]), "partes")
