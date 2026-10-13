# Auditoría de traducciones — v1.1.1t

Resultado de revisar el texto visible en el juego de los mods nuevos. Los nombres
propios y términos de Valheim se mantienen.

| Mod | Texto visible | Estado |
|---|---|---|
| HipLantern 1.1.13 | Objeto, descripción, avisos de luz/calor, slot | Español incluido en la DLL («Linterna de cadera»). Sin cambios. |
| StaminaExtended 1.0.11 | Tooltips de comida y panel de efectos | Usa tokens de Valheim (`$se_staminaregen`, `$item_current`), ya en español. Sin cambios. |
| SkilledCarryWeight 1.4.3 | «Quick Cart», «Cart Mass», «Found cart {0} away», «[tecla] Quick Attach/Detach» | **Pendiente.** Los textos están codificados en la DLL y no se pueden sustituir con un archivo de traducción. Requiere un componente de código en AKH Plugins (`runtime/`). |
| FloorsAreRoofs 2.0.2 | Solo registros en el log | Nada que traducir. |
| InstantMonsterDrop 1.0.2 | Solo configuración | Nada que traducir. |
| NoStamCosts 0.1.2 | Solo configuración | Nada que traducir. |
| NoTreeStump 1.0.3 | Ninguno | Nada que traducir. |
| UseEquipmentInWater 0.2.4 | Ninguno | Nada que traducir. |

Las descripciones de las opciones de configuración (`.cfg`) se mantienen en
inglés: solo las ve quien edita los ajustes, no los jugadores en partida.

## Traducciones de ValheimRAFT
Incluidas en AKH Plugins (Translations/<Idioma>/valheimraft.json, con el espanol). Antes de la 1.1.2 los paquetes solo llevaban DLL y esta carpeta no se instalaba en instalaciones limpias.

## v1.1.3t (prueba)

- AKH Plugins 1.1.4: configs `vapok.mods.{adventurebackpacks,dooropenerbruh,shieldmebruh}.cfg` con `Show Splash on Startup = false` y `Enable Anonymous Telemetry = false` (quita el popup de Vapok en todos los clientes).

| Mod | Texto visible | Estado |
|---|---|---|
| DarwinAwards 1.0.6 | Mensajes de muerte | **Descartado de la prueba:** su ServerSync interno falla con el Valheim actual (`MissingFieldException: ZRoutedRpc.Everybody`) y el mod no arranca. La traduccion ya hecha esta guardada en `test-releases/v1.1.3t/descartados/AwardCategories.es.yml`. |
| OdinBanners 1.1.12 | Nombres y descripciones de los estandartes | **Traducido** (`plugins/OdinBanners/Translations/OdinBanners.Spanish.yml`). Los nombres de casas y clanes se mantienen. |
| BetterDiving 1.1.2 | Mensajes «You prepare to dive», «You remain on the surface», «You have surfaced», «You can breath now.» | **Pendiente.** Estan codificados en la DLL; requiere un componente de codigo en AKH Plugins, igual que SkilledCarryWeight. |
| Slope Combat Assistance 2.0.30 | Ninguno | Nada que traducir. |
| Pinnacle 1.17.0 | Comandos de consola y configuracion | Nada visible para el jugador en partida. |
| ComfySigns 1.12.0 | Solo configuracion | Nada que traducir. |

