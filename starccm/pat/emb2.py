r"""Segunda ronda de embalamiento (Sebastián, 2026-11-15): 0,35 y 0,3 Qn a 3000 rpm en las 5 bombas que a 0,4 Qn
seguían en turbina con M_turb casi nulo (G004, G010, G019, G027, G029). Misma orquestación que emb.py.

    python emb2.py plan / tablero      → http://localhost:8773/tablero.html

Carpetas: pat/emb2/ y C:\trabajo\PAT-2026-11_PAT1_emb2. El Excel junta los puntos de las dos rondas (emb.excel_bomba)."""
import json, pathlib, sys

AQUI = pathlib.Path(__file__).parent
sys.path.insert(0, str(AQUI))
import emb, pat, doe   # noqa: E402

SOLO = ("G004", "G010", "G019", "G027", "G029")
DIR = "PAT-2026-11_PAT1_emb2"
emb.EMB = AQUI / "emb2"
emb.FQ_EXTRA = [0.35, 0.3]
doe.AQUI, doe.PLAN, doe.DOE = emb.EMB, emb.EMB / "plan.json", DIR
doe.REMOTO = rf"C:\trabajo\{DIR}"
pat.AQUI = emb.EMB


def _base() -> list[dict]:
    return [r for r in emb._base_pat() if r["id"].startswith(SOLO)]


emb._base = pat._base = _base   # emb.geo, rango.todas y pat.preparar lo buscan por nombre global

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "plan":
        for r in _base():
            g = emb.geo(r["id"])
            print(f"{g['id']:<13} Q {', '.join(f'{x:.1f}' for x in g['Q_m3h'])} m³/h a 3000 rpm")
    elif cmd == "tablero":
        doe.tablero(puerto=8773)
    elif cmd in ("crear", "lanzar", "traer", "podar"):
        getattr(doe, cmd)(sys.argv[2])
    elif cmd == "preparar":
        pat.preparar(sys.argv[2], sys.argv[3])
