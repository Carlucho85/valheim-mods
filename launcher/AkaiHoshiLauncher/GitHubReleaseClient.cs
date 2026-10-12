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

    public async Task<(GitHubRelease Release, ClientReleaseManifest Manifest)> GetLatestAsync(
        CancellationToken cancellationToken)
    {
        using HttpResponseMessage response = await Http.GetAsync(
            LatestReleaseUrl,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        response.EnsureSuccessStatusCode();
        await using Stream stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        GitHubRelease? release = await JsonSerializer.DeserializeAsync<GitHubRelease>(
            stream,
            cancellationToken: cancellationToken);
        if (release is null || release.Draft || release.Prerelease || string.IsNullOrWhiteSpace(release.TagName))
            throw new InvalidDataException("GitHub no devolvió una versión estable válida del modpack.");

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

    private static HttpClient CreateClient()
    {
        var client = new HttpClient { Timeout = TimeSpan.FromMinutes(15) };
        client.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("AkaiHoshiLauncher", "1.0"));
        client.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        client.DefaultRequestHeaders.Add("X-GitHub-Api-Version", "2022-11-28");
        return client;
    }
}
