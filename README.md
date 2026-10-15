# Akai Hoshi — Valheim mods 1.2

Cliente estable **1.2.0** de **Akai Hoshi: Changarök**, con launcher para
instalar y actualizar el modpack.

## Jugadores

1. Descarga **[AkaiHoshiLauncher.exe](https://github.com/Carlucho85/valheim-mods/releases/latest/download/AkaiHoshiLauncher.exe)** desde Windows.
2. Ejecútalo, selecciona la carpeta de Valheim si no se detecta automáticamente y pulsa **Instalar / actualizar mods**.
3. Pulsa **Jugar a Valheim**.

El launcher verifica SHA-256, conserva los archivos idénticos que ya están
instalados y elimina los mods obsoletos sin crear `AKH-purged`. Mantiene los
ajustes personales de AKH MasterKeybind, Equipment and Quick Slots y Better
Archery. La descarga continúa siendo un único ZIP completo, igual que en 1.1.3;
la reutilización evita volver a copiar en disco los archivos coincidentes.
Funciona en Windows de 64 bits con Valheim en Steam. En carpetas protegidas,
Windows puede pedir permisos de administrador (UAC).

## Cliente 1.2

La prueba 1.1.4t se dio por satisfactoria. La lista de mods nuevos y el anexo
del inventario conocido del servidor están en
[`releases/v1.2.0/CHANGELOG.md`](releases/v1.2.0/CHANGELOG.md). Se usa el
contenido de plugins del cliente aportado para 1.2; no se incluyen sus
configuraciones generales, cachés ni logs. Cuatro mods retirados durante la
prueba no se distribuyen.

**AKH Plugins** es nuestro plugin privado: reúne las traducciones al español,
el artwork del menú y los ajustes cliente revisados. No tiene página externa.
Su fuente, personalizaciones y DLL están en `client-pack/AKHPlugins/`.

## Fuentes y desarrollo

Los snapshots saneados del servidor 1.1 están en `sources/`; no son copias
byte a byte ni una sincronización con el servidor 1.2. El launcher genera
paquetes ZIP compactos con manifiestos y SHA-256, siguiendo el flujo de 1.1.3.
No se publican credenciales ni configuraciones privadas.

```powershell
python -m unittest discover -s tests -v
dotnet run --project .\tests\LauncherPolicyTests\LauncherPolicyTests.csproj
dotnet build .\launcher\AkaiHoshiLauncher\AkaiHoshiLauncher.csproj -c Release
```
