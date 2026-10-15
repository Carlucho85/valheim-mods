# Akai Hoshi: Changarök 1.2.0 — estable

La prueba **1.1.4t terminó satisfactoriamente** y se promueve a estable. El
paquete de cliente se preparó desde el BepInEx proporcionado para esta
versión. No se modificó ni sincronizó el servidor.

## Mods nuevos en 1.2.0

| Mod | Versión | Lado | Descripción |
|---|---:|---|---|
| [Plateautem](https://thunderstore.io/c/valheim/p/Erkle64/Plateautem/) | 0.4.3 | Servidor y cliente | Permite aplanar terreno para construir. |
| [RtDOcean](https://thunderstore.io/c/valheim/p/Soloredis/RtDOcean/) | 2.2.54 | Servidor y cliente | Añade contenido del océano y cocina; incluye español. |
| [RtDLegends](https://thunderstore.io/c/valheim/p/Soloredis/RtDLegends/) | 1.3.78 | Servidor y cliente | Añade leyendas y jefes; incluye español. |
| **AKH Plugins** | 1.2.0 | Cliente | Plugin propio privado con Master Keybind, traducciones y ajustes de interfaz. Sin página externa. |

Se fijan las posiciones elegidas para los HUD de Equipment and Quick Slots y
Better Archery. Los valores de la configuración local de cada jugador se
respetan al actualizar; en una instalación nueva se aplican los ajustes
compartidos aprobados.

## Actualización integrada en la estable 1.2.0

Se incorpora aquí, sin crear ni distribuir una versión 1.2.1, el hotfix de
cliente que se había preparado con ese número:

- **BetrValheim 5.1.7** se empaqueta desde los 45 archivos de la instalación
  local del cliente, incluidos su DLL, recursos gráficos y traducciones. El
  DLL tiene SHA-256
  `7aa9799cb0594360bcaf9aafc059d1b1d17cda3aaed1b0d01ff53c9ddc461cea`.
- El paquete de AKH Plugins desactiva `[Features] HudWidget` de Living Factions
  para ocultar el panel de actividad de facciones. La configuración se
  administra desde `client-pack/AKHPlugins/customizations/`.
- El paquete estable sigue usando la versión más reciente de AKH Plugins
  incluida en el repositorio y el formato compacto de 1.1.3.

Este cambio es solo de cliente. La compatibilidad de BetrValheim con la
versión instalada en el servidor no se ha verificado en esta actualización;
no se ha modificado ni sincronizado el servidor.

## Mods retirados

No se incluyen **Distant Dynasties**, **RenegadeVikings**, **PortalStations** ni
**VALKEA**; fueron retirados y no forman parte del cliente 1.2. Tampoco se
incluye UseEquipmentInWater, ya descartado anteriormente.

## Anexo — inventario de mods del servidor respaldado por el repositorio

El repositorio no contiene un snapshot BepInEx del servidor 1.2: el ZIP
disponible es el snapshot saneado 1.1 (`sources/BepInEx-server-1.1-sanitized.zip`).
La lista siguiente consolida sus DLL de plugins únicas con las incorporaciones
marcadas como `both` en los manifiestos de las pruebas 1.1.1t, 1.1.3t y 1.1.4t,
omitiendo los cuatro mods retirados. Las versiones del snapshot 1.1 no están
registradas. Por tanto, es el inventario exhaustivo sustentado por esos
archivos y manifiestos, no una comprobación byte a byte del servidor 1.2.

### Snapshot saneado del servidor 1.1

AchievementEnabler, AdventureBackpacks, Advize_PlantEasily,
Advize_PlantEverything, AmmoCount, AugaLite, AzuAutoStore,
BepInEx.ConfigDrawers, BetterArchery, ClockMod, ConditionalConfigSync,
ConditionalConfigSync.Plugin, CraftFromContainers, DiscardInventoryItem,
DoorOpenerBruh, DynamicLocations, EpicLoot, EquipmentAndQuickSlots,
HoeRadius, itemdrawers, Jotunn, MaxPlayerCount, MinimalStatusEffects,
ModConfigs, Newtonsoft.Json, NewtonsoftJsonDetector, Pathfinder,
ProcreationPlus, ProperPortals, QuickStackStore, RecycleItemsIntoParts,
ServerSync, ShieldMeBruh, SpeedyPaths, TripleBronzeJVL, ValheimBuildCamera,
ValheimMenu, ValheimRAFT, ValheimVehicles, VentureValheim.AsocialCartography,
XPortal, YamlDotNet, YamlDotNetDetector, ZdoWatcher y Zolantris.Shared.

`MaxPlayerCount` es exclusivo del servidor. Las DLL de bibliotecas compartidas
incluidas en el snapshot también aparecen en este inventario por nombre de
archivo.

### Incorporaciones compartidas registradas en las pruebas

- **1.1.1t:** HipLantern 1.1.13, StaminaExtended 1.0.11,
  SkilledCarryWeight 1.4.3, FloorsAreRoofs 2.0.2 e
  InstantMonsterDrop 1.0.2.
- **1.1.3t:** BetterDiving 1.1.2, Digitalroot's Slope Combat Assistance 2.0.30
  y OdinBanners 1.1.12.
- **1.1.4t, retenidos en 1.2:** Plateautem 0.4.3, RtDOcean 2.2.54 y
  RtDLegends 1.3.78.

Pinnacle y ComfySigns de la prueba 1.1.3t están clasificados como cliente; no
se cuentan como mods del servidor.

### Elementos sin evidencia suficiente para atribuirlos al servidor

El BepInEx de cliente entregado también contiene OdinOnDemand, RtDBiomes y
RtDMythics. Se incluyen en el paquete porque forman parte de los archivos de
cliente solicitados, pero no aparecen como incorporaciones en los manifiestos
citados ni en el snapshot del servidor 1.1. No se les atribuye presencia,
versión o lado de servidor en este anexo.

## Preparación de la release

El launcher conserva el ZIP completo y compacto de 1.1.3 con sus manifiestos
SHA-256. Al actualizar, reutiliza archivos locales con el mismo tamaño y hash,
elimina archivos de mods obsoletos sin crear `AKH-purged` y respeta las
configuraciones locales de AKH MasterKeybind, Equipment and Quick Slots y
Better Archery. Esta release estable se publica para permitir la prueba del
launcher; no implica ningún cambio ni despliegue en el servidor.
