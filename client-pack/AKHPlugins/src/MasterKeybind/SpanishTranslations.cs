using System;
using System.Reflection;
using BepInEx;
using HarmonyLib;

namespace AKH.MasterKeybind
{
    [BepInPlugin(Guid, "AKH Spanish Translations", "1.0.0")]
    public sealed class SpanishTranslationsPlugin : BaseUnityPlugin
    {
        private const string Guid = "akh.spanishtranslations";
        private static PropertyInfo _localizationInstance = null!;
        private static MethodInfo _getSelectedLanguage = null!;

        private void Awake()
        {
            Type localizationType = AccessTools.TypeByName("Localization")
                ?? throw new InvalidOperationException("Valheim Localization type was not found.");
            MethodInfo localize = AccessTools.Method(localizationType, "Localize", new[] { typeof(string) })
                ?? throw new InvalidOperationException("Localization.Localize(string) was not found.");
            _localizationInstance = AccessTools.Property(localizationType, "instance");
            _getSelectedLanguage = AccessTools.Method(localizationType, "GetSelectedLanguage", Type.EmptyTypes);
            if (_localizationInstance?.GetGetMethod(true)?.IsStatic != true || _getSelectedLanguage == null)
                throw new InvalidOperationException("Valheim's selected language API was not found.");

            MethodInfo postfix = AccessTools.Method(typeof(SpanishTranslationsPlugin), nameof(TranslateResult))
                ?? throw new InvalidOperationException("Spanish translation postfix was not found.");
            new Harmony(Guid).Patch(localize, postfix: new HarmonyMethod(postfix));
        }

        private static void TranslateResult(ref string __result)
        {
            if (!string.IsNullOrEmpty(__result) && IsSpanish())
                __result = __result.Replace("Quick Attach/Detach", "Acoplar/desacoplar rápidamente");
        }

        private static bool IsSpanish()
        {
            object localization = _localizationInstance.GetValue(null)!;
            string language = localization == null
                ? ""
                : _getSelectedLanguage.Invoke(localization, null) as string ?? "";
            return string.Equals(language, "Spanish", StringComparison.OrdinalIgnoreCase);
        }
    }
}
