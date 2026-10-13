using System.Text.Json;

namespace AkaiHoshiLauncher;

public static class SettingsStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

#if TEST_CHANNEL
    private const string DataFolderName = "AkaiHoshiTest";
#else
    private const string DataFolderName = "AkaiHoshi";
#endif

    public static string DataDirectory =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), DataFolderName);

    public static string StatePath => Path.Combine(DataDirectory, "launcher-state.json");

    public static LauncherState Load()
    {
        try
        {
            if (!File.Exists(StatePath))
                return new LauncherState();

            return JsonSerializer.Deserialize<LauncherState>(File.ReadAllText(StatePath), JsonOptions)
                ?? new LauncherState();
        }
        catch (JsonException)
        {
            return new LauncherState();
        }
        catch (IOException)
        {
            return new LauncherState();
        }
    }

    public static void Save(LauncherState state)
    {
        Directory.CreateDirectory(DataDirectory);
        string temp = StatePath + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(state, JsonOptions));
        File.Move(temp, StatePath, overwrite: true);
    }
}
