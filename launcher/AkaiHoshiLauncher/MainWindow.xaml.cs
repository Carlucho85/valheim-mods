using Microsoft.Win32;
using System.ComponentModel;
using System.Diagnostics;
using System.Security.Principal;
using System.Windows;

namespace AkaiHoshiLauncher;

public partial class MainWindow : Window
{
    private readonly GitHubReleaseClient _releaseClient = new();
    private readonly InstallService _installService;
    private GitHubRelease? _release;
    private ClientReleaseManifest? _manifest;
    private LauncherState _state;
    private bool _busy;

    public MainWindow()
    {
        InitializeComponent();
        _installService = new InstallService(_releaseClient);
        _state = SettingsStore.Load();
#if TEST_CHANNEL
        Title = "AKH TestClient | Akai Hoshi (pruebas)";
        TestVersionPanel.Visibility = Visibility.Visible;
        TestVersionBox.Text = _state.InstalledVersion.TrimStart('v');
#endif
    }

    private async void TestVersionBox_KeyDown(object sender, System.Windows.Input.KeyEventArgs e)
    {
        if (e.Key == System.Windows.Input.Key.Enter)
            await RefreshReleaseAsync();
    }

    private async void Window_Loaded(object sender, RoutedEventArgs e)
    {
        string[] arguments = Environment.GetCommandLineArgs();
        int installArgument = Array.IndexOf(arguments, "--install");
#if TEST_CHANNEL
        int versionArgument = Array.IndexOf(arguments, "--version");
        if (versionArgument >= 0 && versionArgument + 1 < arguments.Length)
            TestVersionBox.Text = arguments[versionArgument + 1];
#endif
        string? gamePath = _state.GamePath;
        if (installArgument >= 0 && installArgument + 1 < arguments.Length)
            gamePath = arguments[installArgument + 1];
        if (!SteamLocator.IsValheimDirectory(gamePath))
            gamePath = SteamLocator.FindValheim();
        if (SteamLocator.IsValheimDirectory(gamePath))
            SetGamePath(gamePath!);
        else
            InstallPathText.Text = "No encontramos Valheim. Elige la carpeta del juego.";

        await RefreshReleaseAsync();
        if (installArgument >= 0 && SteamLocator.IsValheimDirectory(_state.GamePath) && _release is not null)
            InstallButton_Click(InstallButton, new RoutedEventArgs());
    }

    private async void RefreshButton_Click(object sender, RoutedEventArgs e)
    {
        await RefreshReleaseAsync();
    }

    private async Task RefreshReleaseAsync()
    {
        if (_busy)
            return;
        SetBusy(true);
#if TEST_CHANNEL
        _release = null;
        _manifest = null;
        if (string.IsNullOrWhiteSpace(TestVersionBox.Text))
        {
            ReleaseStatusText.Text = "Escribe la versión de pruebas (por ejemplo 1.1.1t)";
            StatusText.Text = "Indica la versión que te pasó el equipo y pulsa Buscar.";
            SetBusy(false);
            return;
        }
        StatusText.Text = $"Buscando la versión de pruebas {TestVersionBox.Text.Trim()}…";
#else
        StatusText.Text = "Comprobando la última versión publicada…";
#endif
        try
        {
#if TEST_CHANNEL
            (_release, _manifest) = await _releaseClient.GetByTagAsync(TestVersionBox.Text, CancellationToken.None);
#else
            (_release, _manifest) = await _releaseClient.GetLatestAsync(CancellationToken.None);
#endif
            string installed = _state.InstalledVersion;
            bool current = string.Equals(installed, _manifest.Version, StringComparison.OrdinalIgnoreCase);
#if TEST_CHANNEL
            ReleaseStatusText.Text = current
                ? $"Ya tienes la versión de pruebas {_manifest.Version}"
                : $"Se instalará la versión de pruebas {_manifest.Version}";
            StatusText.Text = "Al instalar se purgará cualquier instalación de mods anterior (se guarda una copia en AKH-purged).";
#else
            ReleaseStatusText.Text = current
                ? $"Ya tienes la versión {_manifest.Version}"
                : $"Versión disponible: {_manifest.Version}";
            StatusText.Text = current
                ? "El modpack está actualizado."
                : "La actualización se descargará desde GitHub y se verificará antes de instalar.";
#endif
        }
        catch (Exception ex) when (ex is HttpRequestException or IOException or InvalidDataException or TaskCanceledException)
        {
            ReleaseStatusText.Text = "No se pudo comprobar la versión de GitHub";
            StatusText.Text = ex.Message;
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void InstallButton_Click(object sender, RoutedEventArgs e)
    {
        if (_busy)
            return;
        if (!SteamLocator.IsValheimDirectory(_state.GamePath))
        {
            BrowseForValheim();
            if (!SteamLocator.IsValheimDirectory(_state.GamePath))
                return;
        }
#if TEST_CHANNEL
        await RefreshReleaseAsync();
        if (_release is null || _manifest is null)
            return;
#else
        if (_release is null || _manifest is null)
        {
            await RefreshReleaseAsync();
            if (_release is null || _manifest is null)
                return;
        }
#endif

        if (!IsAdministrator())
        {
            try
            {
                string executable = Environment.ProcessPath
                    ?? throw new InvalidOperationException("No se pudo localizar el launcher.");
                using Process? elevated = Process.Start(new ProcessStartInfo(executable)
                {
#if TEST_CHANNEL
                    Arguments = $"--install \"{_state.GamePath}\" --version {_manifest.Version.TrimStart('v')}",
#else
                    Arguments = $"--install \"{_state.GamePath}\"",
#endif
                    UseShellExecute = true,
                    Verb = "runas"
                });
                if (elevated is null)
                    throw new InvalidOperationException("Windows no inició el proceso elevado.");
                Close();
            }
            catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
            {
                StatusText.Text = "La instalación necesita permisos de administrador; se canceló la solicitud de UAC.";
            }
            catch (Exception ex) when (ex is Win32Exception or InvalidOperationException)
            {
                StatusText.Text = $"No se pudo iniciar el instalador con permisos elevados: {ex.Message}";
            }
            return;
        }

        SetBusy(true);
        InstallProgressBar.Value = 0;
        var progress = new Progress<InstallProgress>(update =>
        {
            StatusText.Text = update.Message;
            InstallProgressBar.Value = Math.Clamp(update.Percent, 0, 100);
        });

        try
        {
            InstallReport result = await _installService.InstallAsync(
                _state.GamePath,
                _release,
                _manifest,
                progress,
                CancellationToken.None);
            _state = SettingsStore.Load();
            ReleaseStatusText.Text = $"Versión instalada: {result.Version}";
            string details = result.InstalledLoader
                ? "BepInEx y los mods quedaron instalados."
                : "Los mods quedaron instalados.";
            if (result.PreservedModifiedFiles > 0)
                details += $" Se conservaron {result.PreservedModifiedFiles} archivo(s) obsoleto(s) que habías modificado.";
            StatusText.Text = details;
            InstallProgressBar.Value = 100;
            PlayButton.IsEnabled = SteamLocator.IsValheimDirectory(_state.GamePath);
            if (result.PreservedModifiedFiles > 0)
                MessageBox.Show(
                    this,
                    $"{details}\n\nRevisa la carpeta de mods si conservaste plugins modificados.",
                    "Instalación completada",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
        }
        catch (OperationCanceledException)
        {
            StatusText.Text = "Operación cancelada.";
        }
        catch (Exception ex)
        {
            StatusText.Text = "No se pudo completar la instalación.";
            MessageBox.Show(this, ex.Message, "Error al instalar mods", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void BrowseButton_Click(object sender, RoutedEventArgs e)
    {
        BrowseForValheim();
    }

    private void BrowseForValheim()
    {
        var dialog = new OpenFolderDialog
        {
            Title = "Selecciona la carpeta principal de Valheim",
            InitialDirectory = SteamLocator.IsValheimDirectory(_state.GamePath)
                ? _state.GamePath
                : Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86)
        };
        if (dialog.ShowDialog(this) != true)
            return;
        if (!SteamLocator.IsValheimDirectory(dialog.FolderName))
        {
            MessageBox.Show(
                this,
                "La carpeta seleccionada no contiene valheim.exe.",
                "Carpeta no válida",
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
            return;
        }
        SetGamePath(dialog.FolderName);
    }

    private void SetGamePath(string path)
    {
        _state.GamePath = Path.GetFullPath(path);
        InstallPathText.Text = _state.GamePath;
        PlayButton.IsEnabled = SteamLocator.IsValheimDirectory(path)
            && !string.IsNullOrWhiteSpace(_state.InstalledVersion);
        try
        {
            SettingsStore.Save(_state);
        }
        catch (IOException ex)
        {
            StatusText.Text = $"No se pudo guardar la ruta del juego: {ex.Message}";
        }
    }

    private void PlayButton_Click(object sender, RoutedEventArgs e)
    {
        if (!SteamLocator.IsValheimDirectory(_state.GamePath))
        {
            StatusText.Text = "Selecciona primero la carpeta de Valheim.";
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo("steam://run/892970") { UseShellExecute = true });
        }
        catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            try
            {
                Process.Start(new ProcessStartInfo(Path.Combine(_state.GamePath, "valheim.exe"))
                {
                    WorkingDirectory = _state.GamePath,
                    UseShellExecute = true
                });
            }
            catch (Exception launchError)
            {
                StatusText.Text = $"No se pudo iniciar Valheim: {launchError.Message}";
            }
        }
    }

    private void SetBusy(bool busy)
    {
        _busy = busy;
        InstallButton.IsEnabled = !busy;
        BrowseButton.IsEnabled = !busy;
        RefreshButton.IsEnabled = !busy;
    }

    private static bool IsAdministrator()
    {
        using WindowsIdentity identity = WindowsIdentity.GetCurrent();
        return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
    }
}