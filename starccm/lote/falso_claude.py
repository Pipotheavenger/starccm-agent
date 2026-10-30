"""Ejecutor y revisor falsos para `orquestador.py --seco`: escriben lo que escribirían los de verdad, sin solver ni modelo.
Ejecutor (prompt «Caso <ID>…»): resultado_solver.json, ejecucion.json, RESUMEN.md, monitores_historial.csv, PNG y el .sim.
- Bases: en el intento 1 H deriva (sube ~4 %/100 it.) → el orquestador debe extender solo; al extender, H plana → OK.
- Variantes (_V): el par sale con signo de turbina (M_signo_ok false, fallo grave) → REINTENTAR → REVISAR.
- FALSO_CAIDO=<clave>[:n]|todos: claude «caído» (sin salida, rc 1), siempre o las n primeras veces (FALSO_DIR guarda la
  cuenta), para probar la espera y el reintento, ERROR_INFRA y la parada del lote.
- FALSO_PARAR=<clave>: tras ejecutar ese caso crea FALSO_DIR/PARAR (alguien pide parar a mitad).
- FALSO_LIMITE=1: cuota agotada (línea result con is_error y «usage limit», rc 1).
Revisor (prompt «Revisa el caso…»): decide con chequeos.json; en un OK propone un cambio con límite y uno prohibido."""
import json
import os
import re
import sys
from pathlib import Path

ST = Path(__file__).resolve().parent.parent
prompt = sys.argv[sys.argv.index("-p") + 1]
gid = re.search(r"(?:Caso|caso) (\S+?)[ :(]", prompt).group(1)
if os.environ.get("FALSO_LIMITE"):                  # así sale claude -p con la cuota agotada: result de error, rc 1
    print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "num_turns": 1,
                      "result": "Claude AI usage limit reached|1793300000", "total_cost_usd": 0.0}))
    sys.exit(1)
if os.environ.get("FALSO_SIN_EJECUTOR") and prompt.startswith("Caso"):   # el ejecutor no debía ser llamado
    sys.exit(1)
caido = os.environ.get("FALSO_CAIDO", "")          # «todos», «G033» o «G033:2» (solo las 2 primeras veces)
if caido == "todos":
    sys.exit(1)
if caido and caido.split(":")[0] in gid:
    veces = int(caido.split(":")[1]) if ":" in caido else 10 ** 6
    cnt = Path(os.environ.get("FALSO_DIR", ".")) / f"caido_{gid}.txt"
    n = int(cnt.read_text()) if cnt.is_file() else 0
    if n < veces:
        cnt.write_text(str(n + 1))
        sys.exit(1)
caso = ST / "cases" / gid
lote = json.loads((caso / "lote.json").read_text(encoding="utf-8"))
mala = "_V" in gid
print(json.dumps({"type": "system", "subtype": "init", "session_id": "falso"}))
if prompt.startswith("Caso"):
    n_it = lote["iteraciones"]
    H = lote["H_diseno_m"] * (0.3 if mala else 1.2)
    deriva = lote["intento"] == 1 and not mala
    filas = ["Iteration,H Monitor: H Monitor,M Monitor: M Monitor (N-m),eta Monitor: eta Monitor"]
    for it in range(1, n_it + 1):
        h = H * (1 + 0.04 * (it - n_it) / 100) if deriva else H
        filas.append(f"{it},{h * (1 + 0.002 * ((it % 7) - 3) / 3)},{40.0},{0.6}")
    (caso / "reports" / "monitores_historial.csv").write_text("\n".join(filas) + "\n", encoding="utf-8")
    D2 = lote["D2_esperado_mm"] or 250.0
    res = {"iteracion": n_it, "celdas": 1500000, "celdas_region": {"estator": 20000, "rotor": 1000000, "voluta": 400000,
           "ext_entrada": 40000, "ext_salida": 40000}, "reportes": {"H": H, "M": 40.0, "eta": 0.6, "Q_in": -lote["masa_kg_s"],
           "Q_out": lote["masa_kg_s"]}, "balance_masa_pct": 0.01, "r_te_max_m": D2 / 2000.0, "r_salida_alabe_m": D2 / 2000.0,
           "M_signo_ok": not mala, "yplus_alabes_medio": 9.0, "yplus_alabes_max": 80.0}
    (caso / "resultado_solver.json").write_text(json.dumps(res), encoding="utf-8")
    (caso / "ejecucion.json").write_text(json.dumps({"estado": "COMPLETO", "remallados": 0, "base_mm": lote["base_mm"]}), encoding="utf-8")
    (caso / "RESUMEN.md").write_text(f"# {gid} (falso)\n", encoding="utf-8")
    for n in ("presion_alabes", "velocidad_plano", "yplus", "fluido_medio", "fluido_meridional", "vectores_meridional", "malla"):
        (caso / "images" / f"{n}.png").write_bytes(b"\x89PNG falso")
    (ST / "sims" / f"{gid}.sim").write_bytes(b"sim falso")
    if os.environ.get("FALSO_PARAR") and os.environ["FALSO_PARAR"] in gid:   # alguien pide PARAR mientras corre
        (Path(os.environ["FALSO_DIR"]) / "PARAR").write_text("")
else:
    chq = json.loads((caso / "chequeos.json").read_text(encoding="utf-8"))
    if chq["graves_fallidos"]:
        est = "REINTENTAR" if lote["intento"] == 1 else "REVISAR"
        ver = {"estado": est, "motivo": "falla: " + ", ".join(chq["graves_fallidos"]), "reintento": "rehacer",
               "instrucciones_reintento": "comprobar el sentido de giro", "leccion": "par con signo de turbina en variante falsa"}
    else:
        ver = {"estado": "OK", "motivo": "todo bien", "leccion": ""}
        Path(os.environ["LOTE_PROPUESTAS"]).write_text(json.dumps([
            {"parametro": "min_rotor_pct", "valor": 99, "razon": "prueba de límite"},
            {"parametro": "iteraciones", "valor": 2000, "razon": "prohibido"}]), encoding="utf-8")
    (caso / "veredicto.json").write_text(json.dumps(ver), encoding="utf-8")
print(json.dumps({"type": "result", "subtype": "success", "total_cost_usd": 0.0, "num_turns": 1}))
