#!/usr/bin/env bash
# Comprobación NO destructiva del servidor Linux de STAR-CCM+ (no arranca el solver, no usa licencia).
# Uso desde Windows (Git Bash):  bash starccm/vm/remote_check.sh [usuario@host]
# Uso en el servidor:            bash remote_check.sh --local
# Nunca imprime la clave PoD: solo dice si la variable existe.
H="${1:-investigacion@172.17.76.78}"
if [ "$H" != "--local" ]; then
  exec ssh -o BatchMode=yes -o ConnectTimeout=10 "$H" 'bash -s -- --local' < "$0" 2> >(grep -v -E 'post-quantum|store now|server may need' >&2)
fi
ok=0; bad=0
chk(){ if [ "$2" = ok ]; then echo "OK    $1"; ok=$((ok+1)); else echo "FALLA $1 ($3)"; bad=$((bad+1)); fi; }
ENVF=$HOME/.starccm-agent.env
[ -f "$ENVF" ] && chk "env file" ok || chk "env file" no "falta $ENVF"
if [ -f "$ENVF" ]; then
  [ "$(stat -c %a "$ENVF")" = 600 ] && chk "env chmod 600" ok || chk "env chmod 600" no "$(stat -c %a "$ENVF")"
  set -a; . "$ENVF"; set +a
fi
for v in STARCCM_PODKEY STARCCM_LICPATH STARCCM_HOME STARCCM_NP; do
  [ -n "${!v}" ] && chk "variable $v presente" ok || chk "variable $v presente" no vacía
done
X="$STARCCM_HOME/star/bin/starccm+"
[ -x "$X" ] && chk "lanzador $X" ok || chk "lanzador" no "no ejecutable"
if [ -x "$X" ]; then
  v=$("$X" -version 2>&1 | grep -i -m1 -E 'STAR-CCM\+|[0-9]{4}\.[0-9]{4}')
  echo "      versión: $v"; echo "$v" | grep -q 2502 && chk "versión 2502" ok || chk "versión 2502" no "$v"
fi
J=$(find "$(dirname "$STARCCM_HOME")/jdk" -name javac -type f 2>/dev/null | head -1)
[ -n "$J" ] && chk "javac incluido" ok || chk "javac incluido" no "no encontrado"
[ -d "$STARCCM_HOME/doc/client/html/star" ] && chk "javadoc doc/client/html" ok || chk "javadoc" no "no está"
for d in sims macros cases; do [ -d "$HOME/starccm-agent/$d" ] && chk "carpeta ~/starccm-agent/$d" ok || chk "carpeta $d" no "falta"; done
echo "      núcleos: $(nproc)  RAM libre: $(free -g | awk '/Mem:/{print $7}') GiB  disco libre /: $(df -h / | awk 'NR==2{print $4}')"
if [ "${STARCCM_NP:-0}" -gt "$(nproc)" ] 2>/dev/null; then chk "NP <= núcleos" no "$STARCCM_NP > $(nproc)"; fi
n=$(pgrep -fc 'star/bin/starccm|starccm\+ ' || true)
echo "      procesos starccm vivos: $n"
pgrep -af 'starccm' | grep -v -E 'pgrep|remote_check|bash -s' | sed -e "s/-podkey [^ ]*/-podkey ****/g" | head
(echo > /dev/tcp/127.0.0.1/${STARCCM_PORT:-47827}) 2>/dev/null && echo "      puerto ${STARCCM_PORT:-47827}: ocupado (servidor vivo)" || echo "      puerto ${STARCCM_PORT:-47827}: libre"
echo "resultado: $ok ok, $bad fallas"; [ "$bad" = 0 ]
