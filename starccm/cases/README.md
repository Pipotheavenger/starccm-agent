# cases

Un directorio por caso: `cases/<caso>/`

```
cases/<caso>/
├── cad/         geometría de entrada (STEP/Parasolid) tal como la entregó el usuario
├── reports/     tablas y CSV exportados (monitores, reportes, curvas)
├── images/      escenas PNG (presión en álabes, velocidad en plano medio, y+)
└── RESUMEN.md   geometría, malla, parámetros, resultados y tiempo, al cerrar el caso
```

El `.sim` del caso vive en `../sims/<caso>.sim` (no va a git). `cases/_scenes/` recibe los PNG de
`export_scene` cuando no se da ruta. El contenido de los casos no va a git salvo este README.
