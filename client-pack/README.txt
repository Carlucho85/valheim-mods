AKAI HOSHI: CHANGAROK — MODPACK ESTABLE 1.1.0

Instala o actualiza el paquete con AkaiHoshiLauncher.exe.

El inventario cliente 1.1 coincide con los plugins compartidos del servidor
1.1. MaxPlayerCount.dll se queda solo en el servidor. El paquete se construye
con los binarios compartidos del servidor y no incluye QuickConnect ni
configuraciones de BepInEx/config.

No hay nombres de DLL nuevos respecto al paquete estable 1.0.4. Se detectaron
hashes distintos entre los adjuntos de cliente y servidor para
BepInEx.ConfigDrawers, DoorOpenerBruh, ShieldMeBruh y ValheimBuildCamera; el
paquete usa la copia del servidor para que los clientes coincidan con él.

Los archivos fuente saneados están en sources/. Se quitaron configuraciones,
cachés y logs antes de publicarlos; no son copias byte a byte de los adjuntos.
Al preparar esta versión se compararon ambos inventarios 1.1 para detectar DLL
faltantes y versiones distintas antes de publicarla.
