using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using BepInEx;
using BepInEx.Bootstrap;
using BepInEx.Configuration;
using HarmonyLib;
using UnityEngine;

namespace AKH.MasterKeybind
{
    // Panel único de teclas: refleja en su propio config (que el modpack nunca sobrescribe) las acciones
    // de Valheim y los KeyCode/KeyboardShortcut de los demás plugins, y aplica lo que el jugador elija.
    [BepInPlugin(Guid, "Master Keybind", "1.0.0")]
    public sealed class MasterKeybindPlugin : BaseUnityPlugin
    {
        public const string Guid = "akh.masterkeybind";

        private static MasterKeybindPlugin _instance = null!;
        private readonly List<Mirror> _mirrors = new List<Mirror>();
        private readonly HashSet<string> _known = new HashSet<string>();
        private float _scanUntil;
        private bool _applying;
        private bool _vanillaReady;

        private sealed class VanillaAction
        {
            public string Name = "";
            public string Category = "";
            public string Label = "";
        }

        // Acciones de Valheim re-asignables con teclado/ratón, agrupadas por categoría.
        private static readonly VanillaAction[] VanillaActions =
        {
            new VanillaAction { Category = "01 Vanilla - Combate", Name = "Attack", Label = "Atacar" },
            new VanillaAction { Category = "01 Vanilla - Combate", Name = "SecondaryAttack", Label = "Ataque secundario" },
            new VanillaAction { Category = "01 Vanilla - Combate", Name = "Block", Label = "Bloquear" },
            new VanillaAction { Category = "01 Vanilla - Combate", Name = "Hide", Label = "Guardar arma" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "Forward", Label = "Avanzar" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "Backward", Label = "Retroceder" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "Left", Label = "Izquierda" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "Right", Label = "Derecha" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "Jump", Label = "Saltar" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "Crouch", Label = "Agacharse" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "AltDodge", Label = "Esquivar (alternativa)" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "Run", Label = "Correr" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "ToggleWalk", Label = "Alternar caminar" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "AutoRun", Label = "Correr automático" },
            new VanillaAction { Category = "02 Vanilla - Movimiento", Name = "Sit", Label = "Sentarse" },
            new VanillaAction { Category = "03 Vanilla - Interacción", Name = "Use", Label = "Usar / interactuar" },
            new VanillaAction { Category = "03 Vanilla - Interacción", Name = "GP", Label = "Poder de guardián" },
            new VanillaAction { Category = "03 Vanilla - Interacción", Name = "AutoPickup", Label = "Recogida automática" },
            new VanillaAction { Category = "03 Vanilla - Interacción", Name = "OpenRadial", Label = "Menú radial" },
            new VanillaAction { Category = "03 Vanilla - Interacción", Name = "OpenEmote", Label = "Menú de emotes" },
            new VanillaAction { Category = "04 Vanilla - Construcción", Name = "BuildMenu", Label = "Menú de construcción" },
            new VanillaAction { Category = "04 Vanilla - Construcción", Name = "AltPlace", Label = "Colocación alternativa" },
            new VanillaAction { Category = "04 Vanilla - Construcción", Name = "Remove", Label = "Desmontar pieza" },
            new VanillaAction { Category = "05 Vanilla - Interfaz y mapa", Name = "Inventory", Label = "Inventario" },
            new VanillaAction { Category = "05 Vanilla - Interfaz y mapa", Name = "Map", Label = "Mapa" },
            new VanillaAction { Category = "05 Vanilla - Interfaz y mapa", Name = "MapZoomOut", Label = "Alejar mapa" },
            new VanillaAction { Category = "05 Vanilla - Interfaz y mapa", Name = "MapZoomIn", Label = "Acercar mapa" },
            new VanillaAction { Category = "05 Vanilla - Interfaz y mapa", Name = "TabLeft", Label = "Pestaña anterior" },
            new VanillaAction { Category = "05 Vanilla - Interfaz y mapa", Name = "TabRight", Label = "Pestaña siguiente" },
            new VanillaAction { Category = "06 Vanilla - Sistema", Name = "Console", Label = "Consola" },
        };

        private abstract class Mirror
        {
            public bool Applied;
            public abstract void Apply();
            public abstract void Pull();
        }

        private sealed class ModMirror : Mirror
        {
            public ConfigEntryBase Target = null!;
            public ConfigEntryBase Master = null!;

            public override void Apply()
            {
                if (!Equals(Target.BoxedValue, Master.BoxedValue))
                    Target.BoxedValue = Master.BoxedValue;
            }

            public override void Pull()
            {
                if (!Equals(Master.BoxedValue, Target.BoxedValue))
                    Master.BoxedValue = Target.BoxedValue;
            }
        }

        private sealed class VanillaMirror : Mirror
        {
            public string Name = "";
            public ConfigEntry<KeyCode> Master = null!;

            public override void Apply()
            {
                KeyCode current = ReadVanilla(Name);
                if (current == Master.Value)
                    return;
                WriteVanilla(Name, Master.Value);
            }

            public override void Pull()
            {
                KeyCode current = ReadVanilla(Name);
                if (current != Master.Value)
                    Master.Value = current;
            }
        }

        private void Awake()
        {
            _instance = this;
            Config.SaveOnConfigSet = true;
            _scanUntil = Time.realtimeSinceStartup + 180f;
            new Harmony(Guid).PatchAll(typeof(ZInputPatches));
        }

        private void Start() => Scan();

        private float _nextScan;

        private void Update()
        {
            if (Time.realtimeSinceStartup < _nextScan)
                return;
            _nextScan = Time.realtimeSinceStartup + (Time.realtimeSinceStartup < _scanUntil ? 3f : 30f);
            Scan();
        }

        internal static void OnVanillaChangedInGame()
        {
            if (_instance == null || _instance._applying)
                return;
            foreach (VanillaMirror mirror in _instance._mirrors.OfType<VanillaMirror>())
                mirror.Pull();
        }

        internal static void OnVanillaLoaded()
        {
            if (_instance != null)
                _instance.Scan();
        }

        private void Scan()
        {
            _applying = true;
            try
            {
                ScanVanilla();
                ScanMods();
            }
            catch (Exception exception)
            {
                Logger.LogWarning("Escaneo de teclas: " + exception.Message);
            }
            finally
            {
                _applying = false;
            }
        }

        private void ScanVanilla()
        {
            if (ZInputReady() == false)
                return;
            foreach (VanillaAction action in VanillaActions)
            {
                string id = "vanilla:" + action.Name;
                if (_known.Contains(id) || !HasVanilla(action.Name))
                    continue;
                _known.Add(id);

                KeyCode defaultKey = ReadVanilla(action.Name, defaultBinding: true);
                var definition = new ConfigDefinition(action.Category, action.Label);
                bool saved = IsSaved(definition);
                ConfigEntry<KeyCode> entry = Config.Bind(definition, defaultKey,
                    new ConfigDescription("Acción de Valheim: " + action.Name + ". Sobrescribe el menú de controles del juego."));
                if (!saved)
                    entry.Value = ReadVanilla(action.Name);

                var mirror = new VanillaMirror { Name = action.Name, Master = entry };
                mirror.Apply();
                entry.SettingChanged += (_, __) =>
                {
                    if (!_applying)
                        mirror.Apply();
                };
                _mirrors.Add(mirror);
            }
            _vanillaReady = true;
        }

        private void ScanMods()
        {
            foreach (var info in Chainloader.PluginInfos.Values.ToList())
            {
                BaseUnityPlugin? plugin = info.Instance;
                if (plugin == null || plugin == this || plugin.Config == null)
                    continue;

                foreach (ConfigDefinition definition in plugin.Config.Keys.ToList())
                {
                    ConfigEntryBase target = plugin.Config[definition];
                    Type type = target.SettingType;
                    if (type != typeof(KeyCode) && type != typeof(KeyboardShortcut))
                        continue;

                    string id = "mod:" + info.Metadata.GUID + ":" + definition.Section + ":" + definition.Key;
                    if (!_known.Add(id))
                        continue;

                    string section = "10 Mod - " + info.Metadata.Name;
                    string key = definition.Section + " / " + definition.Key;
                    var masterDefinition = new ConfigDefinition(section, key);
                    bool saved = IsSaved(masterDefinition);

                    ConfigEntryBase master = BindBoxed(masterDefinition, type, target.DefaultValue,
                        new ConfigDescription("Tecla del mod " + info.Metadata.Name + " (" + definition.Section + " / " + definition.Key + ")."));
                    if (!saved)
                        master.BoxedValue = target.BoxedValue;

                    var mirror = new ModMirror { Target = target, Master = master };
                    mirror.Apply();
                    master.ConfigFile.SettingChanged += (_, args) =>
                    {
                        if (!_applying && args.ChangedSetting == master)
                            mirror.Apply();
                    };
                    plugin.Config.SettingChanged += (_, args) =>
                    {
                        if (!_applying && args.ChangedSetting == target)
                            mirror.Pull();
                    };
                    _mirrors.Add(mirror);
                }
            }
        }

        private bool IsSaved(ConfigDefinition definition)
        {
            var orphans = typeof(ConfigFile).GetProperty("OrphanedEntries", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public)?.GetValue(Config)
                as IDictionary<ConfigDefinition, string>;
            return orphans != null && orphans.ContainsKey(definition);
        }

        private ConfigEntryBase BindBoxed(ConfigDefinition definition, Type type, object defaultValue, ConfigDescription description)
        {
            MethodInfo bind = typeof(ConfigFile).GetMethods()
                .First(m => m.Name == "Bind" && m.IsGenericMethodDefinition && m.GetParameters().Length == 3
                    && m.GetParameters()[0].ParameterType == typeof(ConfigDefinition));
            return (ConfigEntryBase)bind.MakeGenericMethod(type).Invoke(Config, new[] { definition, defaultValue, description })!;
        }

        // --- Acceso a ZInput por reflexión (sus tipos de Input System no están referenciados) ---

        private static readonly BindingFlags AnyStatic = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
        private static Dictionary<string, KeyCode>? _pathToKey;

        private static bool ZInputReady()
        {
            return ZInput.instance != null;
        }

        private static object? GetButton(string name)
        {
            return ZInput.instance?.GetButtonDef(name);
        }

        private static bool HasVanilla(string name) => GetButton(name) != null;

        private static string? ActionPath(object button, bool effective)
        {
            return (string?)button.GetType().GetMethod("GetActionPath")!.Invoke(button, new object[] { effective });
        }

        private static KeyCode ReadVanilla(string name, bool defaultBinding = false)
        {
            object? button = GetButton(name);
            if (button == null)
                return KeyCode.None;
            string? path = ActionPath(button, effective: !defaultBinding);
            if (string.IsNullOrEmpty(path))
                return KeyCode.None;
            return PathMap().TryGetValue(NormalizePath(path!), out KeyCode code) ? code : KeyCode.None;
        }

        private static void WriteVanilla(string name, KeyCode code)
        {
            object? button = GetButton(name);
            if (button == null)
                return;
            string path = KeyCodeToPath(code);
            button.GetType().GetMethod("Rebind")!.Invoke(button, new object[] { path });
            ZInput.instance.Save();
        }

        private static string NormalizePath(string path) => path.Trim().ToLowerInvariant();

        private static string KeyCodeToPath(KeyCode code)
        {
            if (code == KeyCode.None)
                return string.Empty;
            Type zinput = typeof(ZInput);
            MethodInfo tryKey = zinput.GetMethod("TryKeyCodeToKey", AnyStatic)!;
            var keyArgs = new object?[] { code, null };
            if ((bool)tryKey.Invoke(null, keyArgs)!)
                return (string)zinput.GetMethod("KeyToPath", AnyStatic)!.Invoke(null, new[] { keyArgs[1] })!;
            MethodInfo tryMouse = zinput.GetMethod("TryKeyCodeToMouseButton", AnyStatic)!;
            var mouseArgs = new object?[] { code, null };
            if ((bool)tryMouse.Invoke(null, mouseArgs)!)
                return (string)zinput.GetMethod("MouseButtonToPath", AnyStatic)!.Invoke(null, new[] { mouseArgs[1], true })!;
            return string.Empty;
        }

        private static Dictionary<string, KeyCode> PathMap()
        {
            if (_pathToKey != null)
                return _pathToKey;
            var map = new Dictionary<string, KeyCode>();
            foreach (KeyCode code in Enum.GetValues(typeof(KeyCode)))
            {
                if (code == KeyCode.None)
                    continue;
                string path;
                try { path = KeyCodeToPath(code); }
                catch { continue; }
                if (path.Length > 0)
                    map[NormalizePath(path)] = code;
            }
            _pathToKey = map;
            return map;
        }

        [HarmonyPatch]
        private static class ZInputPatches
        {
            [HarmonyPostfix, HarmonyPatch(typeof(ZInput), nameof(ZInput.Save))]
            private static void SavePostfix() => OnVanillaChangedInGame();

            [HarmonyPostfix, HarmonyPatch(typeof(ZInput), nameof(ZInput.Load))]
            private static void LoadPostfix() => OnVanillaLoaded();
        }
    }
}
