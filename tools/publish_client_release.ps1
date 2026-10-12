param(
    [Parameter(Mandatory = $true)]
    [string] $ServerPlugins,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$')]
    [string] $Version,

    [string] $OutputDirectory = ".artifacts\$Version"
)

$ErrorActionPreference = "Stop"
$Repository = "Carlucho85/valheim-mods"

if (-not (Test-Path -LiteralPath $ServerPlugins)) {
    throw "No se encontró el ZIP o la carpeta de plugins del servidor: $ServerPlugins"
}

$Branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo comprobar la rama actual de Git."
}
$DefaultBranch = (& gh api "repos/$Repository" --jq ".default_branch").Trim()
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo consultar la rama principal de GitHub."
}
if ($Branch -ne $DefaultBranch) {
    throw "Publica desde la rama principal '$DefaultBranch' después de integrar los cambios del launcher."
}

$Status = & git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo comprobar el estado de Git."
}
if ($Status) {
    throw "El árbol de trabajo debe estar limpio antes de publicar una versión."
}

$LocalCommit = (& git rev-parse HEAD).Trim()
$RemoteCommit = (& gh api "repos/$Repository/commits/$DefaultBranch" --jq ".sha").Trim()
if ($LASTEXITCODE -ne 0 -or $LocalCommit -ne $RemoteCommit) {
    throw "Actualiza la rama '$DefaultBranch' con GitHub antes de publicar."
}

& gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "Autentícate con GitHub CLI (`gh auth login`) antes de publicar."
}

$ExistingRelease = & gh release view $Version --repo $Repository 2>$null
if ($LASTEXITCODE -eq 0) {
    throw "Ya existe una GitHub Release para $Version."
}

$OutputPath = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

& python ".\tools\build_client_pack.py" `
    --server-plugins $ServerPlugins `
    --version $Version `
    --output-dir $OutputPath
if ($LASTEXITCODE -ne 0) {
    throw "Falló la creación o validación del paquete cliente."
}

$PublishPath = Join-Path $OutputPath "launcher"
& dotnet publish ".\launcher\AkaiHoshiLauncher\AkaiHoshiLauncher.csproj" `
    --configuration Release `
    --runtime win-x64 `
    --self-contained true `
    --output $PublishPath `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:EnableCompressionInSingleFile=true
if ($LASTEXITCODE -ne 0) {
    throw "Falló la compilación del launcher para Windows."
}

$Launcher = Join-Path $PublishPath "AkaiHoshiLauncher.exe"
if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) {
    throw "No se generó AkaiHoshiLauncher.exe."
}

$Manifest = Get-Content -LiteralPath (Join-Path $OutputPath "client-manifest.json") -Raw | ConvertFrom-Json
$Assets = @(
    (Join-Path $OutputPath "valheim-mods-cliente.zip"),
    (Join-Path $OutputPath "valheim-mods-cliente.zip.sha256"),
    (Join-Path $OutputPath "client-manifest.json"),
    (Join-Path $OutputPath $Manifest.loaderArchiveName),
    (Join-Path $OutputPath "$($Manifest.loaderArchiveName).sha256"),
    $Launcher
)
foreach ($Asset in $Assets) {
    if (-not (Test-Path -LiteralPath $Asset -PathType Leaf)) {
        throw "Falta el asset requerido para la release: $Asset"
    }
}

$Notes = @"
Modpack cliente $Version para Akai Hoshi: Changarök.

Los jugadores descargan únicamente AkaiHoshiLauncher.exe. El launcher detecta Valheim en Steam, instala BepInEx cuando falta y descarga/verifica el modpack de esta release.

Actualizado desde el ZIP de plugins del servidor. Assets preparados por tools/build_client_pack.py.
"@
$CreateArguments = @(
    "release", "create", $Version,
    "--repo", $Repository,
    "--target", $DefaultBranch,
    "--draft",
    "--title", "Akai Hoshi $Version",
    "--notes", $Notes
) + $Assets
& gh @CreateArguments
if ($LASTEXITCODE -ne 0) {
    throw "GitHub rechazó la creación de la release."
}

& gh release edit $Version --repo $Repository --draft=false
if ($LASTEXITCODE -ne 0) {
    throw "Los assets se subieron, pero no se pudo publicar la release. Publícala en GitHub Releases."
}

Write-Host "Release publicada: https://github.com/$Repository/releases/tag/$Version"
Write-Host "Los jugadores podrán descargar: https://github.com/$Repository/releases/latest/download/AkaiHoshiLauncher.exe"
