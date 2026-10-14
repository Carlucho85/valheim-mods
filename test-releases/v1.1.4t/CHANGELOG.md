# v1.1.4t — prueba de BetrValheim y nuevos mods

Base: version estable v1.1.3, mas las pruebas anteriores v1.1.1t y v1.1.3t.

## Mods nuevos incluidos

| Mod | Version | Instalacion | Pagina |
|---|---:|---|---|
| balrond_constructions | 1.5.1 | Cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/Balrond/balrond_constructions/) |
| BetrValheim | 5.1.4 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/DezzyCode/BetrValheim/) |
| Enigmas Realistic Smoke Rework | 0.3.0 | Cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/Enigma_Prime/Enigmas_Realistic_Smoke_Rework/) |
| Plateautem | 0.4.3 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/Erkle64/Plateautem/) |
| CoreWoodExtras | 2.3.5 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/MagicMike/CoreWoodExtras/) |
| PlanBuild | 0.20.0 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/MathiasDecrock/PlanBuild/) |
| PlantEasily (actualización de dependencia) | 2.3.0 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/Advize/PlantEasily/) |
| SkilledCarryWeight (actualización de dependencia) | 1.5.0 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/Searica/SkilledCarryWeight/) |
| AmmoCount (actualización de dependencia) | 0.5.1 | Servidor y cliente | [Nexus Mods](https://www.nexusmods.com/valheim/mods/2273) |
| ValheimRAFT (reinstalación en el servidor) | 5.0.9 | Servidor; ya incluido en cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/zolantris/ValheimRAFT/) |
| StarLevelSystem | 1.25.1 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/MidnightMods/StarLevelSystem/) |
| RtDBiomes | 3.2.0 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/Soloredis/RtDBiomes/) |
| RtDLegends | 1.4.0 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/Soloredis/RtDLegends/) |
| RtDMythics | 1.4.0 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/Soloredis/RtDMythics/) |
| RtDOcean | 2.3.1 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/Soloredis/RtDOcean/) |
| EpicLoot ProgressionFix | 0.1.276 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/Tenemo/EpicLoot_ProgressionFix/) |
| Shack Better Paths | 1.1.0 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/TheShackDev/Shack_Better_Paths/) |
| LivingFactions | 0.6.5 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/under2ker/LivingFactions/) |
| OOD_LIB | 1.2.0 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/ValMedia/OOD_LIB/) |
| OdinOnDemand | 1.3.0 | Servidor y cliente | [Thunderstore](https://thunderstore.io/c/valheim/p/ValMedia/OdinOnDemand/) |

## Cambios de compatibilidad

- BetrValheim reemplaza las funciones redundantes de Equipment and Quick Slots, itemdrawers, CraftFromContainers, QuickStackStore, ClockMod y XPortal.
- PortalStations se omite; BetrValheim proporciona la red de portales.
- Se conserva Better Archery. Sus ajustes locales y los de Equipment and Quick Slots se deben mantener durante la actualizacion del cliente.
- Se mantiene la configuracion personal de AKH MasterKeybind.
- El launcher de pruebas reutiliza archivos locales con hash coincidente, elimina archivos obsoletos sin crear `AKH-purged` y conserva las configuraciones personales de MasterKeybind, Equipment and Quick Slots y Better Archery.
- Se conservan los idiomas distribuidos originalmente por los autores; las cadenas sin localización española publicada permanecen en su idioma original.
- Las teclas propias de BetrValheim se configuran en su panel F11; MasterKeybind gestiona las teclas de Valheim y las entradas compatibles de BepInEx.

## Dependencias comprobadas

- Jotunn 2.30.2 ya esta instalado en la base.
- YamlDotNet 16.3.1 y JsonDotNET 13.0.4 coinciden byte a byte por SHA-256 con las bibliotecas de la base estable.
- EpicLoot ProgressionFix requiere EpicLoot 0.14.13 en ambos lados.
- StarLevelSystem se fija en 1.25.1 porque EpicLoot ProgressionFix 0.1.276 rechaza la versión 1.26.0.
- PlantEasily se actualiza a 2.3.0, requerido por la integración de cosecha de EpicLoot ProgressionFix.
- SkilledCarryWeight se actualiza a 1.5.0, requerido por EpicLoot ProgressionFix. AmmoCount se actualiza a 0.5.1 desde la DLL de aedenthorn incluida en la instantánea estable; el paquete de Thunderstore con ese nombre pertenece a otro proyecto y no se sustituye.
- ValheimRAFT 5.0.9 estaba solo en la caché de Thunderstore de la instantánea y no se instaló en la carpeta activa del servidor; se reutiliza el DLL ya disponible y se instala en `BepInEx/plugins/ValheimRAFT/`. Sus dependencias obligatorias ZdoWatcher 1.2.0 y DynamicLocations 1.2.0, junto con Zolantris.Shared.dll, también se reutilizan desde el snapshot local.
- Adventure Backpacks debe mantenerse en 2.2.11 para coincidir con el servidor; se empaqueta el DLL instalado, no la copia obsoleta de Thunderstore 2.3.4.

## Mundo y prueba

RtDLegends y RtDMythics requieren un mundo nuevo. Esta publicacion no cambia ni crea el mundo del servidor; el cambio se hara cuando el administrador lo autorice.

La prueba de carga automatica se revisa en los logs del servidor. El usuario debe validar la compatibilidad dentro del juego con AKH-TestClient antes de aprobar la version.
