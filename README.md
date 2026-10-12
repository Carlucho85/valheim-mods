# Akai Hoshi — Valheim mods

Modpack oficial del servidor **Akai Hoshi: Changarök** y launcher para que los
jugadores instalen y actualicen los mods con un clic.

## Jugadores

1. Descarga **[AkaiHoshiLauncher.exe](https://github.com/Carlucho85/valheim-mods/releases/latest/download/AkaiHoshiLauncher.exe)** desde Windows.
2. Ejecútalo, selecciona la carpeta de Valheim si no se detecta automáticamente y pulsa **Instalar / actualizar mods**.
3. Pulsa **Jugar a Valheim**.

El launcher instala BepInEx si hace falta, obtiene la última versión estable del
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

La carpeta `BepInEx/plugins` del servidor (o un ZIP de esa carpeta) es la fuente
de verdad. Después de actualizar el servidor, genera y publica el paquete
cliente en un solo paso desde un Windows con Python 3, .NET 8 SDK, GitHub CLI
autenticado y el cambio del launcher integrado en `main`:

```powershell
.\tools\publish_client_release.ps1 `
  -ServerPlugins "C:\ruta\BepInEx\plugins" `
  -ServerConfigFolder "C:\ruta\BepInEx\config" `
  -Version "v1.0.4"
```

Para no publicar por accidente claves o configuraciones privadas, solo se
incluyen los archivos del servidor enumerados en
`client-pack/server-config-allowlist.txt`. Revisa cada archivo antes de añadir
su ruta. Se conservan los plugins recibidos del servidor excepto QuickConnect,
que permanece en el servidor y se omite solo en el paquete cliente. Las
configuraciones de BepInEx/config se distribuyen solo tras revisión y mediante
la lista de permitidos. Esta versión no distribuye ajustes del servidor,
aunque el ZIP completo incluya `BepInEx/config`.

El proceso acepta un ZIP de `plugins` o de la carpeta completa `BepInEx`,
conserva los plugins del servidor, resuelve copias duplicadas según la versión
activa reportada por el servidor (incluidos los desfases detectados en
Adventure Backpacks, PlantEasily, Ammo Count, ConfigDrawers, DoorOpenerBruh,
Minimal Status Effects y Shield Me Bruh), y omite QuickConnect y
metadatos/documentación. Después
aplica localizaciones y la configuración del menú, descarga y verifica el
paquete oficial de BepInEx, construye
`valheim-mods-cliente.zip`, genera manifiestos y hashes, compila el launcher y
publica una GitHub Release. Los
jugadores no tienen que descargar ni ejecutar scripts: solo usan el `.exe`.
Para corregir o reemplazar plugins concretos sin editar la fuente, pasa
`-PluginOverrides "C:\ruta\plugins-actualizados"`; la carpeta debe replicar
las rutas relativas dentro de `BepInEx\plugins`.

Los assets grandes se alojan en Releases y no se guardan en el historial Git.
Cada release contiene el ZIP para el launcher, los manifiestos/checksums y el
paquete de BepInEx requerido para instalaciones nuevas.

## Desarrollo

```powershell
python -m unittest discover -s tests -v
dotnet build .\launcher\AkaiHoshiLauncher\AkaiHoshiLauncher.csproj -c Release
```

La GitHub Action valida el generador y compila el launcher para Windows en cada
pull request y cambio en `main`.
