# Primer prompt para Claude Code en la MV

Pega esto en la primera sesión de `claude` dentro de `~/starccm-agent`.

---

Lee CLAUDE.md completo. Es el brief del proyecto y manda sobre cualquier otra cosa.

Hoy construimos el MCP y comprobamos la fontanería contra STAR-CCM+ real. Orden:

1. Verifica el entorno: `starccm+ -version`, que `$STARCCM_PODKEY` y `$STARCCM_HOME` existen,
   que `$STARCCM_HOME/doc` tiene el javadoc. Dime qué encontraste en 5 líneas.
2. Averigua cuál de los tres métodos de inyección de macros de CLAUDE.md funciona en esta versión.
   Levanta un servidor con un .sim vacío, inyecta una macro que imprima `PING` y mide el tiempo.
   Anota el resultado en CLAUDE.md, sección Lecciones.
3. Escribe `mcp_server.py` con las tools de CLAUDE.md. Un solo archivo. Incluye `--selftest`
   que levante servidor, haga `run_java` con `sim.println("OK")`, `inspect("regions")`,
   `recipe_save` y `recipe_search`, y apague el servidor.
4. Regístralo en `.mcp.json` del proyecto y confirma que las tools aparecen en esta sesión.
5. Con el MCP ya funcionando desde aquí: crea una geometría de prueba en 3D-CAD por macro
   (un cilindro con entrada y salida basta), mállala, ponle agua y flujo segregado, corre 50
   iteraciones y dame residuales y caudal. Guarda cada snippet que funcione como receta.

Reglas para hoy:
- Antes de escribir Java nuevo busca en `recipes/` y en el javadoc. Si inventas un nombre de
  clase y falla, consulta el javadoc antes del segundo intento.
- Cada `run_java` exitoso con algo nuevo -> `recipe_save`.
- Si un paso te cuesta más de dos intentos, anota la lección en CLAUDE.md.
- No toques nada fuera de `~/starccm-agent`.
- Al terminar cada paso, dos líneas de estado y sigue. No me preguntes salvo que estés bloqueado.

---

# Segundo prompt: primera bomba real

Cuando el paso 5 funcione, en una sesión nueva:

---

Lee CLAUDE.md. Tengo la bomba en `cases/<nombre>/cad/<archivo>.step`.
Datos: <rpm> rpm, caudal nominal <Q> m3/h, agua a 20 °C, eje de giro <X/Y/Z>.
Sigue el flujo estándar de bomba de CLAUDE.md de punta a punta y dame altura, torque,
potencia y eficiencia en el punto nominal, más las tres escenas.
Si el CAD tiene problemas de superficie que no puedes arreglar en 3 intentos, dime exactamente
qué cara y qué diagnóstico, y para.
Guarda recetas y el RESUMEN.md del caso.

---

# Tercer prompt: curva

---

Con el caso `cases/<nombre>` convergido, haz el barrido de 5 caudales de CLAUDE.md en la misma
sesión de servidor, reusando malla. Tabla final: Q, H, M, P_eje, eficiencia, iteraciones,
desbalance de masa. Gráfica H vs Q y eficiencia vs Q como PNG.
