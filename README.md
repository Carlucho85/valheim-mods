# Akai Hoshi — Valheim mods 1.1

Modpack estable **1.1.0** de **Akai Hoshi: Changarök** y launcher para instalar
y actualizar los mods de cliente.

## Jugadores

1. Descarga **[AkaiHoshiLauncher.exe](https://github.com/Carlucho85/valheim-mods/releases/latest/download/AkaiHoshiLauncher.exe)** desde Windows.
2. Ejecútalo, selecciona la carpeta de Valheim si no se detecta automáticamente y pulsa **Instalar / actualizar mods**.
3. Pulsa **Jugar a Valheim**.

El launcher conserva el diseño y el flujo de actualización de la versión
estable anterior. Instala BepInEx si hace falta, obtiene la versión estable del
modpack desde GitHub Releases y comprueba SHA-256 antes de instalar. Detecta
instalaciones de Steam y copia cualquier archivo que vaya a reemplazar por
primera vez a `%LOCALAPPDATA%\AkaiHoshi\backups`, incluidas las modificaciones
locales en archivos del pack que van a actualizarse. También conserva los
archivos modificados que ya no forman parte de la nueva versión.

La descarga del modpack supera los 700 MiB. La primera instalación necesita
espacio libre adicional para descargar, verificar y preparar los archivos.
Actualmente el launcher está dirigido a **Windows de 64 bits con Valheim en
Steam**. Al instalar o actualizar en una carpeta protegida de Steam, Windows
pedirá permiso de administrador (UAC). Si el ejecutable no está firmado,
Windows SmartScreen puede mostrar una advertencia; descarga el launcher
únicamente desde este repositorio.

## Administrador del servidor

Los snapshots saneados de las carpetas BepInEx 1.1 están en `sources/` y se
siguen mediante Git LFS. Se retiraron `BepInEx/config`, cachés y logs para no
publicar ajustes privados del servidor o del cliente. No son copias byte a byte
de los adjuntos originales.

Para regenerar el paquete desde Windows con Python 3, .NET 8 SDK y GitHub CLI
autenticado:

```powershell
.\tools\publish_client_release.ps1 `
  -ServerPlugins ".\sources\BepInEx-server-1.1-sanitized.zip" `
  -Version "v1.1.0"
```

El inventario del cliente 1.1 contiene 44 DLL únicas; el servidor tiene las
mismas más `MaxPlayerCount.dll`, que se excluye del paquete cliente.
`QuickConnect` se omite también. Para las DLL compartidas, el servidor es la
fuente canónica. En la validación de 1.1 se comparó el resultado contra el
inventario del cliente. Las localizaciones y el menú personalizado se mantienen
mediante `client-pack/overrides/`; no se copian configuraciones generales del
servidor.

No se detectaron nombres de DLL nuevos respecto al paquete estable 1.0.4.
Cuatro DLL tenían hashes distintos entre los adjuntos de cliente y servidor
1.1 (`BepInEx.ConfigDrawers`, `DoorOpenerBruh`, `ShieldMeBruh` y
`ValheimBuildCamera`); para esas se usan los bytes de la copia del servidor.
AdventureBackpacks, Advize_PlantEasily, AmmoCount, BepInEx.ConfigDrawers,
DoorOpenerBruh, MinimalStatusEffects y ShieldMeBruh aparecen en carpetas de
plugins instalados en 1.1, pero ya estaban en `thunderstore/` del paquete
estable anterior.

Las copias fuente grandes se guardan con Git LFS. Los assets descargables del
launcher y del modpack se publican en GitHub Releases.

## Desarrollo

```powershell
python -m unittest discover -s tests -v
dotnet build .\launcher\AkaiHoshiLauncher\AkaiHoshiLauncher.csproj -c Release
```

La GitHub Action valida el generador y compila el launcher para Windows al
publicar una release.
