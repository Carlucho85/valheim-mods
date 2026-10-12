using System.Diagnostics;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;

namespace AkaiHoshiLauncher;

public sealed class InstallService
{
    private const string EmbeddedManifestName = "client-pack-manifest.json";
    private const string PackageName = "valheim-mods-cliente.zip";
    private readonly GitHubReleaseClient _releaseClient;

    public InstallService(GitHubReleaseClient releaseClient)
    {
        _releaseClient = releaseClient;
    }

    public async Task<InstallReport> InstallAsync(
        string gamePath,
        GitHubRelease release,
        ClientReleaseManifest releaseManifest,
        IProgress<InstallProgress> progress,
        CancellationToken cancellationToken)
    {
        if (!SteamLocator.IsValheimDirectory(gamePath))
            throw new DirectoryNotFoundException("Selecciona la carpeta que contiene valheim.exe.");

        if (Process.GetProcessesByName("valheim").Any(IsRunning))
            throw new InvalidOperationException("Cierra Valheim antes de instalar o actualizar los mods.");

        GitHubAsset packageAsset = GitHubReleaseClient.FindAsset(release, releaseManifest.ArchiveName);
        GitHubAsset loaderAsset = GitHubReleaseClient.FindAsset(release, releaseManifest.LoaderArchiveName);
        if (packageAsset.Size > releaseManifest.ArchiveSize || releaseManifest.ExpandedSize <= 0)
            throw new InvalidDataException("El tamaño publicado del modpack no es válido.");

        string appData = SettingsStore.DataDirectory;
        string workDirectory = Path.Combine(appData, "work", Guid.NewGuid().ToString("N"));
        string downloadDirectory = Path.Combine(workDirectory, "downloads");
        string packageStage = Path.Combine(workDirectory, "package");
        string loaderStage = Path.Combine(workDirectory, "loader");
        string rollbackDirectory = Path.Combine(workDirectory, "rollback");
        string backupDirectory = Path.Combine(
            appData,
            "backups",
            DateTimeOffset.Now.ToString("yyyyMMdd-HHmmss"));
        Directory.CreateDirectory(downloadDirectory);

        bool succeeded = false;
        var applied = new List<(string Destination, string? RollbackPath)>();
        int installed = 0;
        int removed = 0;
        int preserved = 0;
        bool installedLoader = false;
        string? persistentBackup = null;

        try
        {
            progress.Report(new InstallProgress("Descargando el modpack desde GitHub…", 3));
            string packageArchive = Path.Combine(downloadDirectory, PackageName);
            await _releaseClient.DownloadVerifiedAsync(
                packageAsset,
                releaseManifest.ArchiveSha256,
                packageArchive,
                new Progress<long>(bytes => progress.Report(new InstallProgress(
                    $"Descargando mods… {FormatBytes(bytes)} / {FormatBytes(releaseManifest.ArchiveSize)}",
                    3 + Math.Min(53, bytes * 53d / Math.Max(1, releaseManifest.ArchiveSize))))),
                cancellationToken);

            PackageManifest packageManifest = await Task.Run(
                () => ExtractAndVerifyPackage(packageArchive, packageStage, releaseManifest.Version),
                cancellationToken);

            var loaderFiles = new List<StagedFile>();
            if (!HasBepInEx(gamePath))
            {
                progress.Report(new InstallProgress("Preparando BepInEx para Valheim…", 60));
                string loaderArchive = Path.Combine(downloadDirectory, releaseManifest.LoaderArchiveName);
                await _releaseClient.DownloadVerifiedAsync(
                    loaderAsset,
                    releaseManifest.LoaderSha256,
                    loaderArchive,
                    null,
                    cancellationToken);
                loaderFiles = await Task.Run(
                    () => ExtractBepInEx(loaderArchive, loaderStage),
                    cancellationToken);
                if (loaderFiles.Count == 0)
                    throw new InvalidDataException("El paquete oficial no contiene los archivos de BepInEx para Windows.");
                installedLoader = true;
            }

            var previousState = SettingsStore.Load();
            if (!string.Equals(
                    Path.GetFullPath(previousState.GamePath),
                    Path.GetFullPath(gamePath),
                    StringComparison.OrdinalIgnoreCase))
                previousState = new LauncherState();
            Dictionary<string, string> previousFiles = previousState.Files
                .Where(file => IsManagedPackagePath(file.Path))
                .GroupBy(file => file.Path, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(group => group.Key, group => group.Last().Sha256, StringComparer.OrdinalIgnoreCase);
            HashSet<string> nextPaths = packageManifest.Files
                .Select(file => file.Path)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
            Dictionary<string, string> destinationToRollback = new(StringComparer.OrdinalIgnoreCase);

            long requiredGameSpace = packageManifest.Files.Sum(file => file.Size)
                + loaderFiles.Sum(file => file.Size);
            DriveInfo gameDrive = new(Path.GetPathRoot(Path.GetFullPath(gamePath))!);
            if (gameDrive.AvailableFreeSpace < requiredGameSpace)
                throw new IOException(
                    $"No hay espacio suficiente en el disco del juego. Se necesitan aproximadamente {FormatBytes(requiredGameSpace)}.");

            progress.Report(new InstallProgress(
                installedLoader ? "Instalando BepInEx y preparando los mods…" : "Preparando los mods…",
                63));

            if (installedLoader)
            {
                foreach (StagedFile file in loaderFiles)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    await ApplyFileAsync(
                        gamePath,
                        file,
                        previousFiles,
                        destinationToRollback,
                        applied,
                        rollbackDirectory,
                        backupDirectory,
                        setPersistentBackup: value => persistentBackup ??= value,
                        cancellationToken);
                }
            }

            int index = 0;
            foreach (ManagedFile file in packageManifest.Files)
            {
                cancellationToken.ThrowIfCancellationRequested();
                string source = SafeCombine(packageStage, file.Path);
                await ApplyFileAsync(
                    gamePath,
                    new StagedFile(file.Path, source, file.Size),
                    previousFiles,
                    destinationToRollback,
                    applied,
                    rollbackDirectory,
                    backupDirectory,
                    setPersistentBackup: value => persistentBackup ??= value,
                    cancellationToken);
                installed++;
                index++;
                progress.Report(new InstallProgress(
                    $"Instalando mods… {index} / {packageManifest.Files.Count}",
                    65 + (packageManifest.Files.Count == 0 ? 30 : index * 30d / packageManifest.Files.Count)));
            }

            foreach ((string stalePath, string expectedHash) in previousFiles)
            {
                if (nextPaths.Contains(stalePath))
                    continue;
                cancellationToken.ThrowIfCancellationRequested();
                string destination = SafeCombine(gamePath, stalePath);
                if (!File.Exists(destination))
                    continue;

                string currentHash = await HashFileAsync(destination, cancellationToken);
                if (!string.Equals(currentHash, expectedHash, StringComparison.OrdinalIgnoreCase))
                {
                    preserved++;
                    continue;
                }

                string rollbackPath = SafeCombine(rollbackDirectory, stalePath);
                Directory.CreateDirectory(Path.GetDirectoryName(rollbackPath)!);
                File.Copy(destination, rollbackPath, overwrite: true);
                applied.Add((destination, rollbackPath));
                File.Delete(destination);
                removed++;
            }

            progress.Report(new InstallProgress("Guardando la versión instalada…", 98));
            SettingsStore.Save(new LauncherState
            {
                GamePath = Path.GetFullPath(gamePath),
                InstalledVersion = releaseManifest.Version,
                Files = packageManifest.Files
            });

            succeeded = true;
            progress.Report(new InstallProgress("Mods instalados y verificados.", 100));
            return new InstallReport(releaseManifest.Version, installed, removed, preserved, installedLoader);
        }
        catch (Exception installError)
        {
            try
            {
                Rollback(applied);
            }
            catch (Exception rollbackError)
            {
                throw new AggregateException(
                    "La instalación falló y Windows no pudo restaurar todos los archivos anteriores.",
                    installError,
                    rollbackError);
            }
            throw;
        }
        finally
        {
            if (Directory.Exists(workDirectory))
                Directory.Delete(workDirectory, recursive: true);
            if (!succeeded && persistentBackup is not null && Directory.Exists(persistentBackup)
                && !Directory.EnumerateFileSystemEntries(persistentBackup).Any())
                Directory.Delete(persistentBackup);
        }
    }

    public static bool HasBepInEx(string gamePath) =>
        File.Exists(Path.Combine(gamePath, "BepInEx", "core", "BepInEx.dll"))
        && File.Exists(Path.Combine(gamePath, "winhttp.dll"))
        && File.Exists(Path.Combine(gamePath, "doorstop_config.ini"));

    private static PackageManifest ExtractAndVerifyPackage(
        string archivePath,
        string destination,
        string expectedVersion)
    {
        Directory.CreateDirectory(destination);
        using var archive = ZipFile.OpenRead(archivePath);
        ZipArchiveEntry manifestEntry = archive.GetEntry(EmbeddedManifestName)
            ?? throw new InvalidDataException("El ZIP no contiene el manifiesto interno.");
        PackageManifest? manifest;
        using (Stream stream = manifestEntry.Open())
            manifest = JsonSerializer.Deserialize<PackageManifest>(stream);
        if (manifest is null || manifest.SchemaVersion != 1 || manifest.Version != expectedVersion)
            throw new InvalidDataException("El manifiesto interno no coincide con la versión publicada.");

        var expectedFiles = manifest.Files.ToDictionary(
            file => ValidatePackagePath(file.Path),
            file => file,
            StringComparer.OrdinalIgnoreCase);
        var extractedPaths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (ZipArchiveEntry entry in archive.Entries)
        {
            if (string.IsNullOrEmpty(entry.Name))
                continue;
            string relative = ValidateRelativePath(entry.FullName);
            if (relative.Equals(EmbeddedManifestName, StringComparison.OrdinalIgnoreCase)
                || relative.Equals("README.txt", StringComparison.OrdinalIgnoreCase))
                continue;
            if (!expectedFiles.ContainsKey(relative) || !extractedPaths.Add(relative))
                throw new InvalidDataException($"El ZIP contiene un archivo no declarado o duplicado: {relative}");
            string target = SafeCombine(destination, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            awaitCopy(entry, target);
        }

        if (extractedPaths.Count != expectedFiles.Count)
            throw new InvalidDataException("El ZIP no contiene todos los archivos declarados en el manifiesto.");
        foreach (ManagedFile file in manifest.Files)
        {
            string target = SafeCombine(destination, file.Path);
            if (!File.Exists(target) || new FileInfo(target).Length != file.Size)
                throw new InvalidDataException($"El archivo del modpack tiene un tamaño inesperado: {file.Path}");
            string actualHash = HashFile(target);
            if (!string.Equals(actualHash, file.Sha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException($"El archivo del modpack no supera SHA-256: {file.Path}");
        }

        return manifest;

        static void awaitCopy(ZipArchiveEntry entry, string target)
        {
            using Stream input = entry.Open();
            using FileStream output = new(target, FileMode.CreateNew, FileAccess.Write, FileShare.None);
            input.CopyTo(output);
        }
    }

    private static List<StagedFile> ExtractBepInEx(string archivePath, string destination)
    {
        Directory.CreateDirectory(destination);
        var files = new List<StagedFile>();
        using var archive = ZipFile.OpenRead(archivePath);
        const string packageRoot = "BepInExPack_Valheim/";
        bool loaderAssemblyFound = false;
        bool doorstopFound = false;
        bool winhttpFound = false;

        foreach (ZipArchiveEntry entry in archive.Entries)
        {
            if (string.IsNullOrEmpty(entry.Name))
                continue;
            string archivePathName = ValidateRelativePath(entry.FullName);
            if (!archivePathName.StartsWith(packageRoot, StringComparison.OrdinalIgnoreCase))
                continue;
            string relative = archivePathName[packageRoot.Length..];
            if (relative.Length == 0 || relative.EndsWith(".sh", StringComparison.OrdinalIgnoreCase))
                continue;
            bool isBepInExFile = relative.StartsWith("BepInEx/", StringComparison.OrdinalIgnoreCase);
            bool isWindowsBootstrapFile = relative.Equals("winhttp.dll", StringComparison.OrdinalIgnoreCase)
                || relative.Equals("doorstop_config.ini", StringComparison.OrdinalIgnoreCase)
                || relative.Equals(".doorstop_version", StringComparison.OrdinalIgnoreCase);
            if (!isBepInExFile && !isWindowsBootstrapFile)
                continue;

            string target = SafeCombine(destination, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            using (Stream input = entry.Open())
            using (FileStream output = new(target, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                input.CopyTo(output);
            long size = new FileInfo(target).Length;
            files.Add(new StagedFile(relative, target, size));
            loaderAssemblyFound |= relative.Equals("BepInEx/core/BepInEx.dll", StringComparison.OrdinalIgnoreCase);
            doorstopFound |= relative.Equals("doorstop_config.ini", StringComparison.OrdinalIgnoreCase);
            winhttpFound |= relative.Equals("winhttp.dll", StringComparison.OrdinalIgnoreCase);
        }

        if (!loaderAssemblyFound || !doorstopFound || !winhttpFound)
            throw new InvalidDataException("El ZIP oficial de BepInEx está incompleto para instalarlo en Windows.");
        return files;
    }

    private static async Task ApplyFileAsync(
        string gamePath,
        StagedFile file,
        Dictionary<string, string> previousFiles,
        Dictionary<string, string> destinationToRollback,
        List<(string Destination, string? RollbackPath)> applied,
        string rollbackDirectory,
        string backupDirectory,
        Action<string> setPersistentBackup,
        CancellationToken cancellationToken)
    {
        string relative = ValidateManagedPath(file.RelativePath);
        string destination = SafeCombine(gamePath, relative);
        Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
        string? rollbackPath = null;
        bool existed = File.Exists(destination);

        if (existed)
        {
            rollbackPath = SafeCombine(rollbackDirectory, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(rollbackPath)!);
            File.Copy(destination, rollbackPath, overwrite: true);
            destinationToRollback[destination] = rollbackPath;

            bool previouslyManaged = previousFiles.TryGetValue(relative, out string? previousHash);
            bool isConfiguration = relative.StartsWith("BepInEx/config/", StringComparison.OrdinalIgnoreCase);
            bool wasModified = previouslyManaged
                && !string.Equals(
                    await HashFileAsync(destination, cancellationToken),
                    previousHash,
                    StringComparison.OrdinalIgnoreCase);
            if (!previouslyManaged || isConfiguration || wasModified)
            {
                setPersistentBackup(backupDirectory);
                string userBackupPath = SafeCombine(backupDirectory, relative);
                Directory.CreateDirectory(Path.GetDirectoryName(userBackupPath)!);
                if (!File.Exists(userBackupPath))
                    File.Copy(destination, userBackupPath);
            }
        }

        cancellationToken.ThrowIfCancellationRequested();
        string temporary = destination + ".akai-" + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            await using (var input = new FileStream(
                             file.SourcePath,
                             FileMode.Open,
                             FileAccess.Read,
                             FileShare.Read,
                             1024 * 1024,
                             FileOptions.Asynchronous | FileOptions.SequentialScan))
            await using (var output = new FileStream(
                             temporary,
                             FileMode.CreateNew,
                             FileAccess.Write,
                             FileShare.None,
                             1024 * 1024,
                             FileOptions.Asynchronous | FileOptions.SequentialScan))
            {
                await input.CopyToAsync(output, cancellationToken);
                await output.FlushAsync(cancellationToken);
            }

            File.Move(temporary, destination, overwrite: true);
            applied.Add((destination, existed ? rollbackPath : null));
        }
        finally
        {
            if (File.Exists(temporary))
                File.Delete(temporary);
        }
    }

    private static void Rollback(List<(string Destination, string? RollbackPath)> applied)
    {
        var failures = new List<Exception>();
        foreach ((string destination, string? rollbackPath) in applied.AsEnumerable().Reverse())
        {
            try
            {
                if (rollbackPath is not null && File.Exists(rollbackPath))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
                    File.Copy(rollbackPath, destination, overwrite: true);
                }
                else if (File.Exists(destination))
                {
                    File.Delete(destination);
                }
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                failures.Add(new IOException($"No se pudo restaurar {destination}.", ex));
            }
        }
        if (failures.Count > 0)
            throw new AggregateException("No se pudieron restaurar todos los archivos modificados.", failures);
    }

    private static bool IsRunning(Process process)
    {
        try
        {
            return !process.HasExited;
        }
        catch (InvalidOperationException)
        {
            return false;
        }
    }

    private static bool IsManagedPackagePath(string path)
    {
        try
        {
            _ = ValidateManagedPath(path);
            return true;
        }
        catch (InvalidDataException)
        {
            return false;
        }
    }

    private static string ValidatePackagePath(string path)
    {
        string relative = ValidateRelativePath(path);
        if (!(relative.StartsWith("BepInEx/plugins/", StringComparison.OrdinalIgnoreCase)
              || relative.StartsWith("BepInEx/config/ValheimMenu/", StringComparison.OrdinalIgnoreCase)))
            throw new InvalidDataException($"El modpack declara una ruta fuera de sus carpetas permitidas: {relative}");
        return relative;
    }

    private static string ValidateManagedPath(string path)
    {
        string relative = ValidateRelativePath(path);
        if (relative.StartsWith("BepInEx/plugins/", StringComparison.OrdinalIgnoreCase)
            || relative.StartsWith("BepInEx/config/ValheimMenu/", StringComparison.OrdinalIgnoreCase)
            || relative.StartsWith("BepInEx/core/", StringComparison.OrdinalIgnoreCase)
            || relative.StartsWith("BepInEx/patchers/", StringComparison.OrdinalIgnoreCase)
            || relative.StartsWith("BepInEx/monomod/", StringComparison.OrdinalIgnoreCase)
            || relative.Equals("BepInEx/config/BepInEx.cfg", StringComparison.OrdinalIgnoreCase)
            || relative.Equals("doorstop_config.ini", StringComparison.OrdinalIgnoreCase)
            || relative.Equals("winhttp.dll", StringComparison.OrdinalIgnoreCase)
            || relative.Equals(".doorstop_version", StringComparison.OrdinalIgnoreCase))
            return relative;
        throw new InvalidDataException($"Se rechazó una ruta de instalación no permitida: {relative}");
    }

    private static string ValidateRelativePath(string path)
    {
        string normalized = path.Replace('\\', '/');
        if (Path.IsPathRooted(normalized)
            || normalized.StartsWith("/", StringComparison.Ordinal)
            || normalized.Contains(':')
            || normalized.Split('/').Any(part => part is "" or "." or ".."))
            throw new InvalidDataException($"Ruta insegura en ZIP: {path}");
        return normalized;
    }

    private static string SafeCombine(string root, string relative)
    {
        string normalized = ValidateRelativePath(relative).Replace('/', Path.DirectorySeparatorChar);
        string rootPath = Path.GetFullPath(root);
        string destination = Path.GetFullPath(Path.Combine(rootPath, normalized));
        string rootPrefix = Path.EndsInDirectorySeparator(rootPath)
            ? rootPath
            : rootPath + Path.DirectorySeparatorChar;
        if (!destination.StartsWith(rootPrefix, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException($"La ruta de instalación sale de su carpeta: {relative}");
        return destination;
    }

    private static string HashFile(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static async Task<string> HashFileAsync(string path, CancellationToken cancellationToken)
    {
        await using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            1024 * 1024,
            FileOptions.Asynchronous | FileOptions.SequentialScan);
        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        byte[] buffer = new byte[1024 * 1024];
        while (true)
        {
            int read = await stream.ReadAsync(buffer, cancellationToken);
            if (read == 0)
                break;
            hash.AppendData(buffer, 0, read);
        }
        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }

    private static string FormatBytes(long bytes)
    {
        string[] units = ["B", "KB", "MB", "GB"];
        double value = bytes;
        int unit = 0;
        while (value >= 1024 && unit < units.Length - 1)
        {
            value /= 1024;
            unit++;
        }
        return $"{value:0.#} {units[unit]}";
    }

    private sealed record StagedFile(string RelativePath, string SourcePath, long Size);
}
