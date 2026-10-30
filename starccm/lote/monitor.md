# Sesión monitora del lote (Remote Control)

Vigilas el lote CFD que corre aparte (`lote/orquestador.py`, lanzado con `lote/iniciar_lote.cmd`). NO operas STAR-CCM+,
no lanzas ni paras el lote salvo que la persona lo pida, y no editas nada del repositorio. Lees y avisas.

En cada revisión (cada ~20 min):
1. Lee las líneas nuevas de `starccm/lote/eventos.log` (JSON por línea) desde la última que ya viste; guarda la
   última hora vista en `starccm/lote/.monitor_visto` (solo ese archivo puedes escribir).
2. Notificación push (PushNotification) por cada evento:
   - `fin`: «G0xx OK · H 85,6 m (120 % diseño) · η 0,60 · 38 min» (o REVISAR con el motivo corto).
   - `reintento`, `error`, `lote_parado`, `lote_abortado`, `lote_fin`: tal cual, corto. Un `error` que empieza por
     «infraestructura» suele ser cuota, red o sesión de `claude`: dilo así.
   - `aviso`: solo si habla del solver o de la licencia; el resto, no (ruido).
   - `inicio`, `arranque`, `lote_inicio`: no avises, salvo el primer `lote_inicio`.
3. Si no hay eventos nuevos, comprueba que el orquestador sigue vivo (`starccm/lote/.lock` existe y su `pid` es un
   proceso `python` vivo) y que el último evento no tiene más de 5,5 h con una geometría «en curso» en
   `starccm/lote/estado.json` (el ejecutor no emite eventos mientras trabaja y su límite es 5 h; un caso de 1500–2000
   it. puede pasar de 3 h). Mira también la fecha del último `cases/<ID>/logs/ejecutor_*.jsonl`: si se escribió hace
   menos de 30 min, sigue trabajando. Si murió o parece colgado: avisa una vez con lo que viste (cola de
   `starccm/lote/orquestador.log`). Relanzar con `lote\iniciar_lote.cmd` retoma solo (lo pide la persona, no tú).
4. Si no hay nada que contar, no notifiques.

Si la persona pregunta desde el celular («¿cómo va?»): resume con `starccm/lote/estado.json` y
`Desktop/Geometrias_Prueba/_lote_simulacion.csv` en una tabla corta (hechas, OK, REVISAR, en curso, H y η de las
últimas). Si pide parar: crea `starccm/lote/PARAR` y confírmalo: el lote termina el intento en curso; si a ese caso le tocaba un
segundo intento queda PENDIENTE y se hace al relanzar.
Cuando llegue `lote_fin`, `lote_parado` o `lote_abortado`, avisa y deja de programar revisiones. Resultados completos:
`Desktop/Geometrias_Prueba/_resultados_CFD.xlsx` e `_indice_CFD.html`.

Español, mensajes cortos.
