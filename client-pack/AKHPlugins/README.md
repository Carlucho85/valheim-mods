# AKH Plugins

AKH Plugins is the private home for Akai Hoshi's own client-side modpack
changes. For every test or stable release, put our additions and changes here
instead of editing or scattering them among the upstream mod files:

- `customizations/` contains client-safe translations, artwork, and config
  files. Preserve their relative `BepInEx/` paths; the packager installs them
  both as AKH-owned source payload and at the destination expected by Valheim
  or the relevant mod. Living Factions' `HudWidget` is disabled here so the
  faction activity panel does not cover the menu artwork.
- `src/` contains the source of AKH-owned BepInEx plugins. `src/MasterKeybind`
  is **Master Keybind**: it lists every Valheim and mod keybind under
  *Mod configs* and applies the player's choices. Its config
  (`BepInEx/config/akh.masterkeybind.cfg`) is never shipped in the package and
  the launcher preserves it across updates, so keys survive.
- `runtime/` contains the built plugin assembly and any runtime dependencies.
  The packager installs these under `BepInEx/plugins/AKHPlugins/`.

Approved shared settings such as the Better Archery and Equipment and Quick
Slots HUD defaults are included for new installations. During updates the
launcher preserves existing local copies of those two configs and
`akh.masterkeybind.cfg`; other configs not managed by the package are left
untouched.

When AKH code is added, build it from `src/` into `runtime/` and test that the
resulting DLL is present in the generated client archive. Configs and
translations are content customizations; they do not execute as plugin code on
their own.

Keep `manifest.json` private and valid. The generated client manifest adopts
the release version so test and stable packages stay aligned. Never bundle
credentials, tokens, private server connection details, or server-only
settings. Only include config values reviewed as safe to distribute to every
client.
