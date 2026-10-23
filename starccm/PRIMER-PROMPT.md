# Primer prompt: fontanería contra STAR-CCM+ real (este PC)

Requisito previo: `starccm/.env` con `STARCCM_PODKEY` (ver `.env.example`) y sesión de Claude Code
reiniciada para que aparezcan las tools del MCP `starccm`.

---

Lee `starccm/CLAUDE.md` completo. Es el brief del proyecto y manda sobre cualquier otra cosa.

Hoy comprobamos la fontanería contra STAR-CCM+ real. Orden:

1. `server_status`, luego `server_start()` sin .sim. Dime en 3 líneas: segundos de arranque,
   pid, puerto, y la cola del log del servidor en `sims/nuevo.server.log` (sin la clave).
2. `run_java('sim.println("PING");')` y mide el tiempo. Si el cliente batch apaga el servidor
   o no devuelve la salida, prueba el plan B de CLAUDE.md. Anota en CLAUDE.md > Lecciones cuál
   funcionó en 2410 y cuánto tarda una inyección.
3. `inspect("tree")` sobre la simulación vacía: tiene que responder sin excepción. Si alguna
   línea Java de `_INSPECT` falla en 2410, corrígela con `docs_search` y anota la lección.
4. Crea una geometría de prueba en 3D-CAD por macro (un cilindro con entrada y salida basta),
   mállala, ponle agua y flujo segregado, corre 50 iteraciones con `iterate(50)` y dame
   residuales y caudal. Guarda cada snippet que funcione como receta (`recipe_save`).
5. `save("prueba-cilindro")`, `export_scene` de una escena de malla, `server_stop()`.

Reglas para hoy:
- Antes de escribir Java nuevo busca en `recipes/` y en el javadoc (`docs_search`). Si inventas
  un nombre de clase y falla, consulta el javadoc antes del segundo intento.
- Cada `run_java` exitoso con algo nuevo -> `recipe_save`.
- Si un paso te cuesta más de dos intentos, anota la lección en CLAUDE.md.
- No toques nada fuera de `starccm/`.
- Al terminar cada paso, dos líneas de estado y sigue. No me preguntes salvo que estés bloqueado.

---

# Segundo prompt: primera bomba real

Cuando el paso 4 funcione, en una sesión nueva:

---

Lee `starccm/CLAUDE.md`. Tengo la bomba en `starccm/cases/<nombre>/cad/<archivo>.step`.
Datos: <rpm> rpm, caudal nominal <Q> m3/h, agua a 20 °C, eje de giro <X/Y/Z>.
Sigue el flujo estándar de bomba de CLAUDE.md de punta a punta y dame altura, torque,
potencia y eficiencia en el punto nominal, más las tres escenas.
Si el CAD tiene problemas de superficie que no puedes arreglar en 3 intentos, dime exactamente
qué cara y qué diagnóstico, y para.
Guarda recetas y el RESUMEN.md del caso.

---

# Tercer prompt: curva

---

Con el caso `starccm/cases/<nombre>` convergido, haz el barrido de 5 caudales de CLAUDE.md en la
misma sesión de servidor, reusando malla. Tabla final: Q, H, M, P_eje, eficiencia, iteraciones,
desbalance de masa. Gráfica H vs Q y eficiencia vs Q como PNG.
