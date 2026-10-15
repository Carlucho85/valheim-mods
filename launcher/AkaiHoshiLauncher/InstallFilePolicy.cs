using System.Security.Cryptography;

namespace AkaiHoshiLauncher;

internal static class InstallFilePolicy
{
    internal static readonly string[] CodeRoots = ["BepInEx/plugins", "BepInEx/patchers", "BepInEx/monomod"];
    internal static readonly string[] CodeExtensions = [".dll", ".exe"];

    private static readonly HashSet<string> PreservedUserFiles = new(StringComparer.OrdinalIgnoreCase)
    {
        "BepInEx/config/akh.masterkeybind.cfg",
        "BepInEx/config/randyknapp.mods.equipmentandquickslots.cfg",
        "BepInEx/config/ishid4.mods.betterarchery.cfg"
    };

    internal static bool IsPreservedUserFile(string path) =>
        PreservedUserFiles.Contains(path.Replace('\\', '/'));

    internal static async Task<bool> MatchesFileAsync(
        string path,
        long expectedSize,
        string expectedSha256,
        CancellationToken cancellationToken)
    {
        if (!File.Exists(path) || new FileInfo(path).Length != expectedSize)
            return false;

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

        string actual = Convert.ToHexString(hash.GetHashAndReset());
        return string.Equals(actual, expectedSha256, StringComparison.OrdinalIgnoreCase);
    }

    internal static List<string> FindObsoletePluginFiles(
        string gamePath,
        IReadOnlySet<string> expectedPaths)
    {
        var obsolete = new List<string>();
        foreach (string root in CodeRoots)
        {
            string directory = Path.Combine(gamePath, root.Replace('/', Path.DirectorySeparatorChar));
            if (!Directory.Exists(directory))
                continue;

            foreach (string path in Directory.EnumerateFiles(directory, "*", SearchOption.AllDirectories))
            {
                string relative = Path.GetRelativePath(gamePath, path).Replace('\\', '/');
                if (!expectedPaths.Contains(relative))
                    obsolete.Add(relative);
            }
        }

        return obsolete;
    }
}
