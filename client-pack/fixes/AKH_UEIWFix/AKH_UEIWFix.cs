using BepInEx;
using HarmonyLib;

// Sustituye el parche IsSwimming de UseEquipmentInWater 0.2.4, que creaba un
// StackTrace en cada llamada y dejaba el juego a 1 FPS al nadar con BetterDiving.
// Misma logica, pero con un contador de profundidad en lugar de inspeccionar la pila.
[BepInPlugin("akh.ueiwfix", "AKH UseEquipmentInWater Fix", "1.0.0")]
[BepInDependency("com.lvh-it.valheim.useequipmentinwater", BepInDependency.DependencyFlags.HardDependency)]
public class AkhUeiwFix : BaseUnityPlugin
{
    private const string OriginalOwner = "UseEquipmentInWater";
    internal static int EquipDepth;

    private void Awake()
    {
        var harmony = new Harmony("akh.ueiwfix");
        var isSwimming = AccessTools.Method(typeof(Character), "IsSwimming");
        var info = Harmony.GetPatchInfo(isSwimming);
        if (info != null)
        {
            foreach (var prefix in info.Prefixes)
            {
                if (prefix.PatchMethod.DeclaringType != null && prefix.PatchMethod.DeclaringType.Name == OriginalOwner)
                {
                    harmony.Unpatch(isSwimming, prefix.PatchMethod);
                    Logger.LogInfo("Parche IsSwimming original (con StackTrace) retirado.");
                }
            }
        }
        harmony.PatchAll(typeof(Patches));
    }

    private static class Patches
    {
        [HarmonyPatch(typeof(Character), "IsSwimming")]
        [HarmonyPrefix]
        private static bool IsSwimmingPrefix(ref bool __result, Character __instance, float ___m_swimTimer)
        {
            if (EquipDepth > 0 && ___m_swimTimer < 0.5f && __instance.IsPlayer())
            {
                __result = false;
                return false;
            }
            return true;
        }

        [HarmonyPatch(typeof(Humanoid), "EquipItem")]
        [HarmonyPatch(typeof(Humanoid), "UpdateEquipment")]
        [HarmonyPrefix]
        private static void EnterEquip() { EquipDepth++; }

        [HarmonyPatch(typeof(Humanoid), "EquipItem")]
        [HarmonyPatch(typeof(Humanoid), "UpdateEquipment")]
        [HarmonyFinalizer]
        private static void ExitEquip() { if (EquipDepth > 0) EquipDepth--; }
    }
}
