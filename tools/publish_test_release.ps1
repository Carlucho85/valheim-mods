param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v\d+\.\d+\.\d+t\d*$')]
    [string] $Version,

    [switch] $SkipLauncher
)

# Publica una PRERELEASE de pruebas (nunca aparece como "latest", asi que los
# clientes estables no la ven) y mantiene la release fija "test-launcher".
$ErrorActionPreference = "Stop"
$Repository = "Carlucho85/valheim-mods"
$Out = Join-Path (Get-Location) ".artifacts\test-$Version"
$Release = Join-Path $Out "release"
$Mods = Get-Content -LiteralPath "test-releases\$Version\mods.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$ChangelogPath = "test-releases\$Version\CHANGELOG.md"

if (-not (Test-Path (Join-Path $Release "client-manifest.json"))) {
    throw "Ejecuta primero: python tools\prepare_test_release.py $Version"
}
& gh auth status
if ($LASTEXITCODE -ne 0) { throw "Autenticate con gh." }

$Manifest = Get-Content -LiteralPath (Join-Path $Release "client-manifest.json") -Raw | ConvertFrom-Json
$Assets = @(
    (Join-Path $Release "valheim-mods-cliente.zip"),
    (Join-Path $Release "valheim-mods-cliente.zip.sha256"),
    (Join-Path $Release "client-manifest.json"),
    (Join-Path $Release $Manifest.loaderArchiveName),
    (Join-Path $Release "$($Manifest.loaderArchiveName).sha256")
)
foreach ($Asset in $Assets) {
    if (-not (Test-Path -LiteralPath $Asset -PathType Leaf)) { throw "Falta $Asset" }
}

$Branch = (& git branch --show-current).Trim()
$Notes = (Get-Content -LiteralPath $ChangelogPath -Raw -Encoding UTF8)
$Notes = "**VERSION DE PRUEBAS - pendiente de OK.** No es para jugadores: usa AKH-TestClient.`n`n$Notes"
$NotesFile = Join-Path $Out "release-notes.md"
[System.IO.File]::WriteAllText($NotesFile, $Notes, (New-Object System.Text.UTF8Encoding($false)))

cmd /c "gh release view $Version --repo $Repository >nul 2>nul"
if ($LASTEXITCODE -eq 0) {
    & gh release upload $Version @Assets --repo $Repository --clobber
    & gh release edit $Version --repo $Repository --notes-file $NotesFile --prerelease
} else {
    & gh release create $Version @Assets --repo $Repository --target $Branch --prerelease `
        --title "Akai Hoshi $Version (PRUEBAS)" --notes-file $NotesFile
}
if ($LASTEXITCODE -ne 0) { throw "Fallo la publicacion de $Version." }

if (-not $SkipLauncher) {
    $Publish = Join-Path $Out "testclient"
    & dotnet publish ".\launcher\AkaiHoshiLauncher\AkaiHoshiLauncher.csproj" -c Release -r win-x64 `
        --self-contained true -o $Publish -p:Channel=Test -p:PublishSingleFile=true `
        -p:IncludeNativeLibrariesForSelfExtract=true -p:EnableCompressionInSingleFile=true
    if ($LASTEXITCODE -ne 0) { throw "Fallo la compilacion de AKH-TestClient." }
    $Exe = Join-Path $Publish "AKH-TestClient.exe"
    cmd /c "gh release view test-launcher --repo $Repository >nul 2>nul"
    if ($LASTEXITCODE -eq 0) {
        & gh release upload test-launcher $Exe --repo $Repository --clobber
    } else {
        & gh release create test-launcher $Exe --repo $Repository --target $Branch --prerelease `
            --title "AKH-TestClient (launcher de pruebas)" `
            --notes "Launcher de pruebas. Escribe la version (por ejemplo 1.1.1t) e instala. No es para jugadores."
    }
    if ($LASTEXITCODE -ne 0) { throw "Fallo la subida de AKH-TestClient." }
}
Write-Host "Prerelease: https://github.com/$Repository/releases/tag/$Version"
Write-Host "Launcher:   https://github.com/$Repository/releases/download/test-launcher/AKH-TestClient.exe"
