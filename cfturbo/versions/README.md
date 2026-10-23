# versions

Corridas que el usuario guardó (botón "Guardar versión" o tool `cft_save`). Cada carpeta trae el
`.cft` resultante, el batch, el log, los STEP para STAR-CCM+ y los STL del visor, más `run.json`.
Las corridas no guardadas viven en la carpeta temporal del sistema (`%TEMP%\cfturbo-agent`) y se
podan solas. Esta carpeta no va a git (pesa); OneDrive la sincroniza.
