using System.Text.Json.Serialization;

namespace AkaiHoshiLauncher;

public sealed class GitHubRelease
{
    [JsonPropertyName("tag_name")]
    public string TagName { get; set; } = "";

    [JsonPropertyName("draft")]
    public bool Draft { get; set; }

    [JsonPropertyName("prerelease")]
    public bool Prerelease { get; set; }

    [JsonPropertyName("assets")]
    public List<GitHubAsset> Assets { get; set; } = [];
}

public sealed class GitHubAsset
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("browser_download_url")]
    public string BrowserDownloadUrl { get; set; } = "";

    [JsonPropertyName("size")]
    public long Size { get; set; }
}

public sealed class ClientReleaseManifest
{
    [JsonPropertyName("schemaVersion")]
    public int SchemaVersion { get; set; }

    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("archiveName")]
    public string ArchiveName { get; set; } = "";

    [JsonPropertyName("archiveSha256")]
    public string ArchiveSha256 { get; set; } = "";

    [JsonPropertyName("archiveSize")]
    public long ArchiveSize { get; set; }

    [JsonPropertyName("expandedSize")]
    public long ExpandedSize { get; set; }

    [JsonPropertyName("loaderVersion")]
    public string LoaderVersion { get; set; } = "";

    [JsonPropertyName("loaderArchiveName")]
    public string LoaderArchiveName { get; set; } = "";

    [JsonPropertyName("loaderSha256")]
    public string LoaderSha256 { get; set; } = "";
}

public sealed class PackageManifest
{
    [JsonPropertyName("schemaVersion")]
    public int SchemaVersion { get; set; }

    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("files")]
    public List<ManagedFile> Files { get; set; } = [];
}

public sealed class ManagedFile
{
    [JsonPropertyName("path")]
    public string Path { get; set; } = "";

    [JsonPropertyName("sha256")]
    public string Sha256 { get; set; } = "";

    [JsonPropertyName("size")]
    public long Size { get; set; }
}

public sealed class LauncherState
{
    [JsonPropertyName("gamePath")]
    public string GamePath { get; set; } = "";

    [JsonPropertyName("installedVersion")]
    public string InstalledVersion { get; set; } = "";

    [JsonPropertyName("files")]
    public List<ManagedFile> Files { get; set; } = [];
}

public sealed record InstallProgress(string Message, double Percent);

public sealed record InstallReport(
    string Version,
    int InstalledFiles,
    int RemovedFiles,
    int PreservedModifiedFiles,
    bool InstalledLoader);
