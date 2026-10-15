AKAI HOSHI: CHANGAROK — MODPACK ESTABLE 1.2.0

Instala o actualiza el paquete con AkaiHoshiLauncher.exe.

El paquete conserva el formato ZIP compacto y los manifiestos SHA-256 de la
versión 1.1.3. Incluye los plugins del cliente aprobados para 1.2 y el bundle
AKH Plugins, con sus traducciones, artwork y ajustes cliente. Se omiten
configuraciones generales de BepInEx/config, cachés y logs.

La prueba 1.1.4t terminó satisfactoriamente. Distant Dynasties,
RenegadeVikings, PortalStations y VALKEA fueron retirados y no se distribuyen
en 1.2. El inventario conocido del servidor y las notas de esta versión están
en releases/v1.2.0/CHANGELOG.md.

La distribución estable contiene BetrValheim 5.1.7 desde la carpeta local del
cliente, para corregir la lectura del inventario extra e incluir sus imágenes.
AKH Plugins desactiva el widget HUD de Living Factions. El servidor no se
modifica.

Diagnostico: si no aparece la consola de BepInEx, comprueba
BepInEx/config/BepInEx.cfg, en [Logging.Console], Enabled. Con Enabled = false
el juego y los mods pueden iniciar sin mostrar esa ventana; los logs siguen
guardandose en BepInEx/LogOutput.log. Para una prueba, puedes activar la
consola temporalmente y volver a desactivarla al terminar.

Si el log contiene "BetrValheim 5.1.7 loaded", el mod alcanzo la fase de carga.
Un error "VAT: expected one station cheat flag lookup, found 0" indica un
conflicto de parche de ValheimAdminTools con la version actual del juego; puede
desactivar funciones afectadas de varios mods, pero por si solo no demuestra
que Steam haya impedido arrancar Valheim.
