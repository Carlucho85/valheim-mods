using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text.Json;

namespace AkaiHoshiLauncher;

public sealed class GitHubReleaseClient
{
    private const string LatestReleaseUrl =
        "https://api.github.com/repos/Carlucho85/valheim-mods/releases/latest";
    private static readonly HttpClient Http = CreateClient();

    public Task<(GitHubRelease Release, ClientReleaseManifest Manifest)> GetLatestAsync(
        CancellationToken cancellationToken) =>
        GetAsync(LatestReleaseUrl, allowPrerelease: false, expectedTag: null, cancellationToken);

    public Task<(GitHubRelease Release, ClientReleaseManifest Manifest)> GetByTagAsync(
        string version,
        CancellationToken cancellationToken)
    {
        string tag = version.Trim();
        if (!System.Text.RegularExpressions.Regex.IsMatch(tag, @"^v?\d+\.\d+\.\d+t\d*$"))
            throw new InvalidDataException("La versión de pruebas debe tener el formato 1.1.1t.");
        if (!tag.StartsWith('v'))
            tag = "v" + tag;
        return GetAsync(
            $"https://api.github.com/repos/Carlucho85/valheim-mods/releases/tags/{tag}",
            allowPrerelease: true,
            expectedTag: tag,
            cancellationToken);
    }

    private async Task<(GitHubRelease Release, ClientReleaseManifest Manifest)> GetAsync(
        string url,
        bool allowPrerelease,
        string? expectedTag,
        CancellationToken cancellationToken)
    {
        using HttpResponseMessage response = await Http.GetAsync(
            url,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        if (response.StatusCode == HttpStatusCode.NotFound && expectedTag is not null)
            throw new InvalidDataException($"No existe la versión de pruebas {expectedTag}.");
        response.EnsureSuccessStatusCode();
        await using Stream stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        GitHubRelease? release = await JsonSerializer.DeserializeAsync<GitHubRelease>(
            stream,
            cancellationToken: cancellationToken);
        if (release is null || release.Draft || (release.Prerelease && !allowPrerelease)
            || string.IsNullOrWhiteSpace(release.TagName)
            || (expectedTag is not null && release.TagName != expectedTag))
            throw new InvalidDataException("GitHub no devolvió una versión válida del modpack.");

        GitHubAsset manifestAsset = FindAsset(release, "client-manifest.json");
        using HttpResponseMessage manifestResponse = await Http.GetAsync(
            manifestAsset.BrowserDownloadUrl,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        manifestResponse.EnsureSuccessStatusCode();
        await using Stream manifestStream = await manifestResponse.Content.ReadAsStreamAsync(cancellationToken);
        ClientReleaseManifest? manifest = await JsonSerializer.DeserializeAsync<ClientReleaseManifest>(
            manifestStream,
            cancellationToken: cancellationToken);
        if (manifest is null || manifest.SchemaVersion != 1 || manifest.Version != release.TagName)
            throw new InvalidDataException("El manifiesto de la versión no coincide con la Release de GitHub.");

        GitHubAsset package = FindAsset(release, manifest.ArchiveName);
        if (package.Size != manifest.ArchiveSize || !IsSha256(manifest.ArchiveSha256))
            throw new InvalidDataException("El asset del modpack no coincide con el manifiesto publicado.");

        GitHubAsset loader = FindAsset(release, manifest.LoaderArchiveName);
        if (!IsSha256(manifest.LoaderSha256) || loader.Size <= 0)
            throw new InvalidDataException("El asset de BepInEx no coincide con el manifiesto publicado.");

        if (!string.IsNullOrWhiteSpace(manifest.FilesManifestName))
        {
            if (manifest.FilesManifestName != "client-files-manifest.json"
                || !IsSha256(manifest.FilesManifestSha256)
                || manifest.FilesManifestSize <= 0
                || manifest.FilesManifestSize > 8 * 1024 * 1024)
                throw new InvalidDataException("El manifiesto de archivos de cliente no es válido.");

            GitHubAsset filesManifestAsset = FindAsset(release, manifest.FilesManifestName);
            if (filesManifestAsset.Size != manifest.FilesManifestSize)
                throw new InvalidDataException("El manifiesto de archivos no coincide con el tamaño publicado.");
            using HttpResponseMessage filesResponse = await Http.GetAsync(
                filesManifestAsset.BrowserDownloadUrl,
                HttpCompletionOption.ResponseHeadersRead,
                cancellationToken);
            filesResponse.EnsureSuccessStatusCode();
            await using Stream filesStream = await filesResponse.Content.ReadAsStreamAsync(cancellationToken);
            using var manifestBuffer = new MemoryStream((int)manifest.FilesManifestSize);
            byte[] buffer = new byte[81920];
            while (true)
            {
                int read = await filesStream.ReadAsync(buffer, cancellationToken);
                if (read == 0)
                    break;
                if (manifestBuffer.Length + read > manifest.FilesManifestSize)
                    throw new InvalidDataException("El manifiesto de archivos supera el tamaño publicado.");
                manifestBuffer.Write(buffer, 0, read);
            }
            byte[] filesBytes = manifestBuffer.ToArray();
            string actualHash = Convert.ToHexString(SHA256.HashData(filesBytes)).ToLowerInvariant();
            if (filesBytes.LongLength != manifest.FilesManifestSize
                || !CryptographicOperations.FixedTimeEquals(
                    Convert.FromHexString(actualHash),
                    Convert.FromHexString(manifest.FilesManifestSha256)))
                throw new InvalidDataException("El manifiesto de archivos no supera la verificación SHA-256.");

            PackageManifest? filesManifest = JsonSerializer.Deserialize<PackageManifest>(filesBytes);
            if (filesManifest is null
                || filesManifest.SchemaVersion != 1
                || filesManifest.Version != manifest.Version
                || filesManifest.Files.Count == 0)
                throw new InvalidDataException("El manifiesto de archivos no coincide con la versión publicada.");
            manifest.Files = filesManifest.Files;
        }

        var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (ManagedFile file in manifest.Files)
        {
            string normalizedPath = file.Path.Replace('\\', '/');
            if (!IsManagedPath(normalizedPath)
                || !paths.Add(normalizedPath)
                || file.Size < 0
                || !IsSha256(file.Sha256)
                || !string.Equals(
                    file.AssetName,
                    $"client-file-{file.Sha256.ToLowerInvariant()}.bin",
                    StringComparison.Ordinal))
                throw new InvalidDataException("El manifiesto contiene un archivo de cliente no válido.");

            file.Path = normalizedPath;
            GitHubAsset fileAsset = FindAsset(release, file.AssetName);
            if (fileAsset.Size != file.Size)
                throw new InvalidDataException($"El asset {file.AssetName} no coincide con el tamaño del manifiesto.");
        }

        return (release, manifest);
    }

    public async Task DownloadVerifiedAsync(
        GitHubAsset asset,
        string expectedSha256,
        string destination,
        IProgress<long>? progress,
        CancellationToken cancellationToken)
    {
        using HttpResponseMessage response = await Http.GetAsync(
            asset.BrowserDownloadUrl,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        response.EnsureSuccessStatusCode();
        await using Stream input = await response.Content.ReadAsStreamAsync(cancellationToken);
        await using var output = new FileStream(
            destination,
            FileMode.Create,
            FileAccess.Write,
            FileShare.None,
            1024 * 1024,
            FileOptions.Asynchronous | FileOptions.SequentialScan);
        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        byte[] buffer = new byte[1024 * 1024];
        long total = 0;
        while (true)
        {
            int read = await input.ReadAsync(buffer, cancellationToken);
            if (read == 0)
                break;
            hash.AppendData(buffer, 0, read);
            await output.WriteAsync(buffer.AsMemory(0, read), cancellationToken);
            total += read;
            progress?.Report(total);
        }

        await output.FlushAsync(cancellationToken);
        string actual = Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
        if (!CryptographicOperations.FixedTimeEquals(
                Convert.FromHexString(actual),
                Convert.FromHexString(expectedSha256)))
        {
            File.Delete(destination);
            throw new InvalidDataException($"La descarga de {asset.Name} no coincide con su SHA-256.");
        }

        if (asset.Size > 0 && total != asset.Size)
        {
            File.Delete(destination);
            throw new InvalidDataException($"El tamaño de {asset.Name} no coincide con el publicado.");
        }
    }

    public static GitHubAsset FindAsset(GitHubRelease release, string name) =>
        release.Assets.FirstOrDefault(asset => string.Equals(asset.Name, name, StringComparison.Ordinal))
        ?? throw new InvalidDataException($"La Release {release.TagName} no contiene {name}.");

    private static bool IsSha256(string value) =>
        value.Length == 64 && value.All(Uri.IsHexDigit);

    private static bool IsManagedPath(string path)
    {
        string normalized = path.Replace('\\', '/');
        return !string.IsNullOrWhiteSpace(normalized)
            && !normalized.StartsWith("/", StringComparison.Ordinal)
            && !normalized.Contains(':')
            && !normalized.Split('/').Any(part => part is "" or "." or "..")
            && (normalized.StartsWith("BepInEx/plugins/", StringComparison.OrdinalIgnoreCase)
                || normalized.StartsWith("BepInEx/config/", StringComparison.OrdinalIgnoreCase)
                || normalized.StartsWith("BepInEx/patchers/", StringComparison.OrdinalIgnoreCase));
    }

    private static HttpClient CreateClient()
    {
        var client = new HttpClient { Timeout = TimeSpan.FromMinutes(15) };
        client.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("AkaiHoshiLauncher", "1.0"));
        client.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        client.DefaultRequestHeaders.Add("X-GitHub-Api-Version", "2022-11-28");
        return client;
    }
}
