## Akai Hoshi v1.1.3t (PRUEBAS - pendiente de OK)

Base: v1.1.2 estable (52 plugins) + 5 mods nuevos - UseEquipmentInWater = 56 plugins. AKH Plugins 1.1.4.

### Mods nuevos (5)

| Mod | Version | Donde |
|---|---|---|
| [BetterDiving](https://thunderstore.io/c/valheim/p/MainStreetGaming/BetterDiving/) (MainStreetGaming) | 1.1.2 | Servidor y cliente |
| [Digitalroot's Slope Combat Assistance](https://thunderstore.io/c/valheim/p/Digitalroot/Digitalroots_Slope_Combat_Assistance/) (Digitalroot) | 2.0.30 | Servidor y cliente |
| [OdinBanners](https://thunderstore.io/c/valheim/p/OdinPlus/OdinBanners/) (OdinPlus) | 1.1.12 | Servidor y cliente |
| [Pinnacle](https://thunderstore.io/c/valheim/p/ComfyMods/Pinnacle/) (ComfyMods) | 1.17.0 | Solo cliente |
| [ComfySigns](https://thunderstore.io/c/valheim/p/ComfyMods/ComfySigns/) (ComfyMods) | 1.12.0 | Solo cliente |

### Descartado
- **UseEquipmentInWater 0.2.4**: retirado del cliente. Crea un `StackTrace` en cada llamada a `Character.IsSwimming` dentro del agua y BetterDiving la llama muchas veces por frame, lo que dejaba el juego a ~1 FPS al entrar al agua.
- **Popup de Vapok** (Adventure Backpacks, DoorOpenerBruh, Shield Me Bruh!): desactivado junto con su telemetria mediante configs en AKH Plugins 1.1.4.
- **DarwinAwards 1.0.6** (Smoothbrain): incompatible con el Valheim actual (su ServerSync interno falla con `MissingFieldException: ZRoutedRpc.Everybody` y el mod no arranca). Queda fuera; la traduccion de sus mensajes de muerte esta guardada para cuando haya una version compatible.

### Traducciones (AKH Plugins)
- OdinBanners: nombres y descripciones de los estandartes traducidos al espanol (`OdinBanners.Spanish.yml`); los nombres de casas y clanes se mantienen.
- BetterDiving: 4 mensajes («You prepare to dive», «You remain on the surface», «You have surfaced», «You can breath now.») siguen en ingles porque estan codificados en la DLL.
- Slope Combat Assistance, Pinnacle y ComfySigns: sin texto visible que traducir.

### Servidor
Backup previo de la 1.1.2 en `akh-backups\20261013-222923-stable-1.1.2`. Servidor reiniciado con los 3 mods nuevos de servidor (BetterDiving, Slope Combat Assistance, OdinBanners) y estable, sin errores.

### Como probar
Descarga AKH-TestClient, escribe `1.1.3t` y pulsa Instalar. Comprueba: entrar al servidor, banners en el menu de construccion (en espanol), nadar/bucear, combate en pendientes, carteles con color y pines rapidos en el mapa.
