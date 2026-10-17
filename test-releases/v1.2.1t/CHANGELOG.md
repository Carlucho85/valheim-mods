# Akai Hoshi 1.2.1t (PRUEBAS)

Base: cliente estable 1.2.0. Esta versión de prueba no cambia los plugins del
cliente; conserva el paquete 1.2.0, incluido BepInEx 5.4.2351 y los cuatro
plugins RtD usados por el servidor.

## Cambio del servidor

- Se actualizó BepInExPack Valheim de 5.4.2333 a 5.4.2351 para satisfacer la
  dependencia declarada por RtDBiomes, RtDLegends, RtDMythics y RtDOcean.
- Se preservaron `BepInEx.cfg`, los plugins, las configuraciones y el mundo
  Changarok V2. El backup previo al cambio se verificó y los datos activos del
  mundo coinciden byte por byte; Valheim solo avanzó el índice de guardado
  `_main.31` a `_main.33` al iniciar.
- El arranque quedó verificado: BepInEx 5.4.2351, 49 plugins cargados, 3
  omitidos y 0 fallidos. Los cuatro plugins RtD informaron las versiones
  esperadas.

## Prueba pendiente

La hipótesis es que la discrepancia del loader impedía completar la transición
a las cuevas RtD; el arranque correcto no demuestra todavía que la entrada
funcione. Entra al servidor con el cliente 1.2.1t y prueba la tecla **E** en
una entrada de cueva. No promover esta versión a estable hasta confirmar la
transición dentro del juego.
