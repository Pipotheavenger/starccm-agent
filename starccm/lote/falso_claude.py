"""Ejecutor y revisor falsos para `orquestador.py --seco`: escriben lo que escribirían los de verdad, sin solver ni modelo.
Ejecutor (prompt «Caso <ID>…»): resultado_solver.json, ejecucion.json, RESUMEN.md, monitores_historial.csv, 9 PNG y el .sim.
Las variantes (_V) salen con H al 30 % del diseño (fallo grave) para probar REINTENTAR → REVISAR.
Revisor (prompt «Revisa el caso…»): decide con chequeos.json; en la base propone un cambio de parámetro con límites."""
import json
import re
import sys
from pathlib import Path

ST = Path(__file__).resolve().parent.parent
prompt = sys.argv[sys.argv.index("-p") + 1]
gid = re.search(r"(?:Caso|caso) (\S+?)[ :]", prompt).group(1)
caso = ST / "cases" / gid
lote = json.loads((caso / "lote.json").read_text(encoding="utf-8"))
mala = "_V" in gid
print(json.dumps({"type": "system", "subtype": "init", "session_id": "falso"}))
if prompt.startswith("Caso"):
    H = lote["H_diseno_m"] * (0.3 if mala else 1.2)
    filas = ["Iteration,H Monitor: H Monitor,M Monitor: M Monitor (N-m),eta Monitor: eta Monitor"]
    for it in range(1, 1001):
        filas.append(f"{it},{H * (1 + 0.01 * ((it % 7) - 3) / 3)},{-40.0},{0.6}")
    (caso / "reports" / "monitores_historial.csv").write_text("\n".join(filas) + "\n", encoding="utf-8")
    D2 = (lote["D2_cfturbo_mm"] if mala else lote["D2_esperado_mm"]) or 250.0
    res = {"iteracion": 1000, "celdas": 1500000, "celdas_region": {"estator": 20000, "rotor": 1000000, "voluta": 380000,
           "ext_entrada": 50000, "ext_salida": 50000}, "reportes": {"H": H, "M": -40.0, "eta": 0.6, "Q_in": -7.0, "Q_out": 7.0},
           "balance_masa_pct": 0.01, "r_salida_alabe_m": D2 / 2000.0, "yplus_alabes_medio": 9.0, "yplus_alabes_max": 80.0}
    (caso / "resultado_solver.json").write_text(json.dumps(res), encoding="utf-8")
    (caso / "ejecucion.json").write_text(json.dumps({"estado": "COMPLETO", "remallados": 0, "base_mm": lote["base_mm"]}), encoding="utf-8")
    (caso / "RESUMEN.md").write_text(f"# {gid} (falso)\n", encoding="utf-8")
    for n in ("presion_alabes", "velocidad_plano", "yplus", "fluido_medio", "vectores_medio", "fluido_meridional",
              "vectores_meridional", "malla", "plano_vectores"):
        (caso / "images" / f"{n}.png").write_bytes(b"\x89PNG falso")
    (ST / "sims" / f"{gid}.sim").write_bytes(b"sim falso")
else:
    chq = json.loads((caso / "chequeos.json").read_text(encoding="utf-8"))
    if chq["graves_fallidos"]:
        est = "REINTENTAR" if lote["intento"] == 1 else "REVISAR"
        ver = {"estado": est, "motivo": "falla: " + ", ".join(chq["graves_fallidos"]), "instrucciones_reintento": "remallar"}
    else:
        ver = {"estado": "OK", "motivo": "todo bien", "leccion": ""}
        (ST / "lote" / "propuestas.json").write_text(json.dumps([{"parametro": "min_rotor_pct", "valor": 99, "razon": "prueba de límite"},
                                                                {"parametro": "iteraciones", "valor": 2000, "razon": "prohibido"}]), encoding="utf-8")
    (caso / "veredicto.json").write_text(json.dumps(ver), encoding="utf-8")
print(json.dumps({"type": "result", "subtype": "success", "total_cost_usd": 0.0, "num_turns": 1}))
