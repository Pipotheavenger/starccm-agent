"""CLI de Claude Code falsa para el selftest de ui/: imprime stream-json como `claude -p --output-format stream-json`
(init, un texto, una tool run_java con su resultado, otro texto y el resultado), con pausas para probar el reenganche."""
import json
import sys
import time

pause = float(sys.argv[sys.argv.index("--fake-pause") + 1]) if "--fake-pause" in sys.argv else 0.6


def out(o):
    print(json.dumps(o), flush=True)


out({"type": "system", "subtype": "init", "session_id": "fake-0001", "model": "fake", "mcp_servers": []})
out({"type": "assistant", "message": {"content": [{"type": "text", "text": "Importo la geometría."}]}})
time.sleep(pause)
out({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "mcp__starccm__run_java",
                                                   "input": {"body": "// QUE: importar los STEP del caso\npim.importCadPart(x);"}}]}})
time.sleep(pause)
out({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}})
time.sleep(pause)
out({"type": "assistant", "message": {"content": [{"type": "text", "text": "Listo: 3 partes importadas."}]}})
out({"type": "result", "subtype": "success", "session_id": "fake-0001", "num_turns": 2})
