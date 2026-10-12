using Microsoft.Win32;
using System.Text.RegularExpressions;

namespace AkaiHoshiLauncher;

public static partial class SteamLocator
{
    private static readonly Regex LibraryPathRegex = new(
        "\"path\"\\s*\"(?<path>[^\"]+)\"",
        RegexOptions.Compiled | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    public static string? FindValheim()
    {
        foreach (string library in GetSteamLibraries())
        {
            string candidate = Path.Combine(library, "steamapps", "common", "Valheim");
            if (File.Exists(Path.Combine(candidate, "valheim.exe")))
                return candidate;
        }

        return null;
    }

    public static bool IsValheimDirectory(string? path) =>
        !string.IsNullOrWhiteSpace(path) && File.Exists(Path.Combine(path, "valheim.exe"));

    private static IEnumerable<string> GetSteamLibraries()
    {
        var roots = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        AddRegistryPath(roots, Registry.CurrentUser, @"Software\Valve\Steam", "SteamPath");
        AddRegistryPath(roots, Registry.LocalMachine, @"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath");
        AddRegistryPath(roots, Registry.LocalMachine, @"SOFTWARE\Valve\Steam", "InstallPath");

        string? programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        if (!string.IsNullOrWhiteSpace(programFiles))
            roots.Add(Path.Combine(programFiles, "Steam"));

        foreach (string root in roots)
        {
            yield return root;
            string librariesFile = Path.Combine(root, "steamapps", "libraryfolders.vdf");
            if (!File.Exists(librariesFile))
                continue;

            string contents;
            try
            {
                contents = File.ReadAllText(librariesFile);
            }
            catch (IOException)
            {
                continue;
            }

            foreach (Match match in LibraryPathRegex.Matches(contents))
            {
                string library = match.Groups["path"].Value.Replace(@"\\", @"\");
                if (!string.IsNullOrWhiteSpace(library))
                    yield return library;
            }
        }
    }

    private static void AddRegistryPath(
        HashSet<string> paths,
        RegistryKey hive,
        string keyPath,
        string valueName)
    {
        try
        {
            using RegistryKey? key = hive.OpenSubKey(keyPath);
            if (key?.GetValue(valueName) is string value && !string.IsNullOrWhiteSpace(value))
                paths.Add(value.Replace('/', '\\'));
        }
        catch (System.Security.SecurityException)
        {
        }
        catch (IOException)
        {
        }
    }
}
