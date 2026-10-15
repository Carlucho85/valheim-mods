using System.Security.Cryptography;
using AkaiHoshiLauncher;

string temporary = Path.Combine(Path.GetTempPath(), "akh-launcher-policy-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(temporary);
try
{
    string matchingFile = Path.Combine(temporary, "matching.dll");
    byte[] original = [1, 2, 3, 4];
    await File.WriteAllBytesAsync(matchingFile, original);
    string hash = Convert.ToHexString(SHA256.HashData(original));
    Assert(await InstallFilePolicy.MatchesFileAsync(matchingFile, original.Length, hash, CancellationToken.None));
    Assert(!await InstallFilePolicy.MatchesFileAsync(matchingFile, original.Length + 1, hash, CancellationToken.None));
    Assert(!await InstallFilePolicy.MatchesFileAsync(matchingFile, original.Length, new string('0', 64), CancellationToken.None));
    Assert(!await InstallFilePolicy.MatchesFileAsync(Path.Combine(temporary, "missing.dll"), 0, hash, CancellationToken.None));

    Assert(InstallFilePolicy.IsPreservedUserFile(@"BepInEx\config\AKH.MasterKeybind.cfg"));
    Assert(InstallFilePolicy.IsPreservedUserFile("BepInEx/config/randyknapp.mods.equipmentandquickslots.cfg"));
    Assert(InstallFilePolicy.IsPreservedUserFile("BepInEx/config/ishid4.mods.betterarchery.cfg"));
    Assert(!InstallFilePolicy.IsPreservedUserFile("BepInEx/config/other.cfg"));

    string plugins = Path.Combine(temporary, "BepInEx", "plugins");
    Directory.CreateDirectory(Path.Combine(plugins, "current"));
    await File.WriteAllTextAsync(Path.Combine(plugins, "current", "Current.dll"), "current");
    await File.WriteAllTextAsync(Path.Combine(plugins, "Old.dll"), "old");
    await File.WriteAllTextAsync(Path.Combine(plugins, "Old.exe"), "old");
    await File.WriteAllTextAsync(Path.Combine(plugins, "readme.txt"), "keep");
    var expected = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
    {
        "BepInEx/plugins/current/Current.dll"
    };
    List<string> obsolete = InstallFilePolicy.FindObsoletePluginFiles(temporary, expected);
    Assert(obsolete.Count == 3 && obsolete.Contains("BepInEx/plugins/Old.dll")
        && obsolete.Contains("BepInEx/plugins/Old.exe")
        && obsolete.Contains("BepInEx/plugins/readme.txt"));

    Console.WriteLine("Launcher file policy tests passed.");
}
finally
{
    Directory.Delete(temporary, recursive: true);
}

static void Assert(bool condition)
{
    if (!condition)
        throw new InvalidOperationException("Launcher file policy assertion failed.");
}
