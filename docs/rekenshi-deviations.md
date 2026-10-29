<a id="re_kenshi-035--modifications-et-profil-de-loracle"></a>

# RE_Kenshi 0.3.5: changes and oracle profile

<a id="périmètre-et-preuves"></a>

## Scope and evidence

Inventory dated 29 October 2026 against public tag `v0.3.5`, commit
`210a7adbf1b95b1ade0c33417ca87de1b8f6335e`: the **28 keys** in
`GenerateDefaultSettings`, initialization and hooks in that tag.
No game code or decompiled code reproduced.

- **Verified in source**: mechanism or value read in the tag; this establishes
  neither an installed DLL's effective state nor parity in every scene.
- **Observed in-game**: identified, bounded trial. [Phase 1](oracle-phase1-delivery.md)
  observes Kenshi 1.0.65 Steam, RE_Kenshi 0.3.5 and KenshiLib 0.5.0; it did not
  neutralize/measure all these functions.
- **Unknown**: effect not established, particularly geometric equivalence,
  timing influence and other threads' state. No new performance measurement
  is needed for this inventory.

The [wiki][wiki] explicitly describes **0.2.18**: useful for usage, but no
replacement for tag 0.3.5. [0.3.5 notes][release035] announce a KenshiLib update,
faster initialization, plugin-error diagnostics and installation fixes.
[0.3.2][release032] adds free camera and dependency-loading fixes;
[0.3.3][release033] fixes exit, menu emergency saves and crash-report prompt frequency.

<a id="simulation-et-chemins-dont-léquivalence-reste-inconnue"></a>

## Simulation and paths whose equivalence remains unknown

Each mechanism below is **Verified in source**; its simulation consequence
has the distinct status in the second column.

| Change, exact keys and code defaults | Simulation effect | Disabling | Evidence and limitation |
| --- | --- | --- | --- |
| RNG fix: `FixRNG=true` | **Yes**, draws including recruits and generated items. | **Yes before startup**: false in a fresh process prevents conditional hook installation. | A hot toggle does not remove these hooks; `DisableFixRNG` changes a TLS flag on the calling thread. Other threads' state and old sequence **Unknown**. [MiscHooks][misc]. |
| Custom speeds: `UseCustomGameSpeeds=false`, `GameSpeeds=[1,2,5,10,20]` | **Yes** when enabled. | **Yes**: custom mode false; record the array too. | Callbacks below persist. [SetSpeed1/2/3 and ForceWriteSpeed][speed]. |
| x2/x5 callbacks and keyboard handling | **Yes** for speed commands; their own effect on probe-driven scenarios **Unknown**. | **No**, no global switch identified. | `ReHookTimeButtons` replaces x2/x5 delegates; `KeyboardHook` runs after the game's listener, even in non-custom mode. [Callbacks][callbacks]. |
| Startup `srand(...)` initialization | **Yes** for initial randomness; magnitude **Unknown**. | **No**, unconditional call. | False RNG/speed options do not provide a strict vanilla reference. [MiscHooks::Init][misc]. |
| Attack slots: `AttackSlots=-1`, `AttackSlotsOverride=false` | **Yes** when enabled. | **Yes**: override false at startup; otherwise restore/check `MAX_NUM_ATTACK_SLOTS`. | Changing JSON/boolean alone does not prove restoration of an already applied constant. [Callbacks][limits], [GUI initialization][limitsinit]. |
| Faction size: `MaxFactionSize=-1`, `MaxFactionSizeOverride=false` | **Yes** when enabled. | **Yes**: override false; restore/check `MAX_FACTION_SIZE` if already changed. | Baseline comes from data/mods, not an assumed universal value. [Limits][limits]. |
| Squad size: `MaxSquadSize=-1`, `MaxSquadSizeOverride=false` | **Yes** when enabled. | **Yes**: same method for `MAX_SQUAD_SIZE`. | Persistent values are not effective constants. [Limits][limits]. |
| Squad count: `MaxSquads=-1`, `MaxSquadsOverride=false` | **Yes** when enabled. | **Yes**: same method for `MAX_SQUADS`. | Negative configuration values are not world population counts. [Limits][limits]. |
| Heightmap reader: `HeightmapMode=-1` (AUTO) | **Unknown**, replaces height reads; geometric equivalence not demonstrated here. | **Yes**: mode 0 and cache refresh, or fresh startup. | Modes -1 auto, 0 original, 1 compressed, 2 fast uncompressed. AUTO persists a concrete mode; failures may fall back to 0. Mode 0 hooks call originals. [Heightmap][heightmap], [enumeration][heightmapenum]. |
| Heightmap preload: `PreloadHeightmap=false` | **Unknown**, memory strategy. | **Yes**: false before opening the image. | Changing this key does not unload an already opened image. [Heightmap][heightmap]. |
| Collider cache: `CachePhysXColliders=true` | **Unknown**, physical-collection clones; result identity not checked. | **Yes**: false calls original loader. Prefer a fresh process. | Cache excludes XML files. [PhysicsHooks][physics]. |
| File rebinding: `RE_Kenshi.json/FileRebinds`, including `HIDE` | **Yes if content changes simulation data**, otherwise file-dependent. | **Through the source mod's configuration**, no global switch. | Inventory mappings/manifests; do not silently change the save's mod set. I/O hook remains. [Mod settings][modsettings], [FSHook][fs]. |
| DLL loading: `PreloadPlugins` / `Plugins` | **Unknown**, depends on each DLL. | **Per plugin/manifest and restart**; globally stopping loading is incompatible with the probe. | Preloading scans available mods; postloading scans active mods: the active list alone does not prove absence of a preloaded DLL. [Plugins][plugins]. |

<a id="autres-réglages-et-fonctions"></a>

## Other settings and functions

“No” means no simulation rule is changed by the examined path. This does
not establish absence of indirect timing effects on a nondeterministic engine.

| Setting or function and code default | Simulation effect | Disabling | Evidence and limitation |
| --- | --- | --- | --- |
| `CacheShaders=true` | **No**, graphics compilation. | **Yes**: false calls original `D3DCompile`. | Hook and initialization-time cache opening remain. [ShaderCache][shader]. |
| `SkipUnusedMipReads=true` | **No**, DDS/mipmap reads and rendering. | **Yes**: false forwards to original listener. | Codecs remain registered. [OgreHooks][ogre], [DDS][dds]. |
| `IncreaseMaxCameraDistance=false` | **Unknown** through observed/loaded region. | **Yes**: false restores intended limit to 2000 instead of 4000; check controls. | Does not restore pose/following. [GUI command][camera]. |
| Free camera, binding, focus and cursor | **Unknown** through region activation/observation; no combat rule identified. | Disable the **mode** and restore controls; **no global shutdown** of hooks. | Loss of focus may leave free mode; binding and cursor remain. [MiscHooks][misc], [KeyboardHook][speed]. |
| `FixModListScroll=true` | **No**, launcher list. | **Yes**: false calls original. | [TabMods_updateModsList_hook][misc]. |
| `SkipSplashScreens=true` | **No**, screens before menu. | **Yes**: false. | Other hook actions persist. [SplashScreen_update_hook][misc]. |
| `OpenSettingOnStart=true` | **No**, settings display. | **Yes**: false at next UI startup. | Exact singular JSON spelling differs from C++ functions. [Settings][settings]. |
| `CheckUpdates=true`, `SkippedVersion=""` | **No**, version notification. | **Yes**: `CheckUpdates=false` before startup avoids this thread. | Skipped version alone does not disable the mechanism. [Version][version]. |
| `IgnoreHash=false` | **Unknown** if enabled: allows an unrecognized binary/table combination. | **Yes**: keep false, verify versions/hashes. | Not universal compatibility. [Initialization][startup]. |
| `LogFileIO=false` | **No**, logging. | **Yes**: false. | File and hooks may be initialized despite false. [FSHook][fs]. |
| `LogAudio=false` | **No**, audio logging. | **Yes** for conditional writes. | Hooks, audio queue and possible internal forced logging remain. [Sound][sound]. |
| `ProfileLoads=false` | **No**, load logging. | **Yes**: false. | Not a simulation clock. [GUIUpdate][guiupdate]. |
| `EnableEmergencySaves=true` | **No** during normal execution; changes crash handling. | **Yes**: false removes the emergency-save prompt. | Does not remove the entire handler; a crashed run is invalid. [Bugs][bugs]. |
| `AlwaysReportCrashes=false` | **No**, post-crash prompt. | False reduces prompts on non-prerelease builds; **no global shutdown** identified. | Prerelease status and a random draw also intervene: false does not guarantee no dialog. Oracle sends no external report. [Bugs][bugs], [Version][version]. |
| SIC/DDS codecs and manifest schema | **No** for graphics codecs; rebindings handled separately. | **No global switch**. | Registered at startup. [SIC][sic], [DDS][dds], [Init][startup]. |
| Mod audio banks and deferred loading | **No** for examined rules; different sound possible. | Removing the test mod's `SoundBanks` entries disables their contribution, **not** the internal queue. | Same content set required/recorded. [Sound][sound], [mod settings][modsettings]. |
| DLL search, COM/WMI, locale, integrated UI and log | **No** for rules; indirect timing **Unknown**. | **No global switch**; debug tab can be closed. | Infrastructure, not evidence of vanilla parity. [Init][startup], [Plugins][plugins], [IO][io]. |
| 1.0.65 compatibility baseline for a 1.0.68 installation | **Unknown** for all build differences. | `--norekenshi` also disables probe loading: **unusable as an oracle profile**. | Record version/hash of the executable actually loaded. [Notes][release035], [entry][entry]. |

<a id="profil-provenance-et-restitution"></a>

## Profile, provenance and restoration

Validated decision: Kenshi 1.0.65, `FixRNG=false` **before startup** and
`UseCustomGameSpeeds=false`. Residual x2/x5/keyboard callbacks are accepted
as a known deviation; strict restoration of native callbacks is not required.
The reported personal opinion of a MeitouClient developer is not an official
decision by their team.

Also neutralize the four gameplay overrides. For the two geometric paths
whose equivalence remains unknown, the conservative profile uses
`HeightmapMode=0`, `PreloadHeightmap=false`, `CachePhysXColliders=false`.
This selects original paths; it does not prove other modes caused a divergence.
Purely graphical options may be retained if recorded.

Contract to verify in the implementation:

1. Capture the player's persistent bytes, fingerprint and effective options;
   arm a recovery journal before mutation.
2. Prepare the profile before startup, loading and NPC generation.
   Do not equate hot RNG disabling with startup without hooks.
   Do not modify RE_Kenshi itself.
3. Verify versions, instance/epoch, options and effective constants before
   each repetition/snapshot. `RE_Kenshi.ini` is **JSON** loaded into a DOM:
   disk reads alone do not attest process state. AUTO may change.
4. Record **outside common state**: previous/requested/effective settings,
   read method/limitations, known/unknown RNG initialization state,
   component/manifest hashes, mod order, inventoried mappings/plugins,
   residuals and compliance. An unknown/lost control invalidates the reference.
5. Restore bytes and effective options, plus camera/time, then verify.
   If a fresh process is required, do so explicitly. Restoring a boolean
   does not reconstruct the RNG sequence. Failure retains the journal.

**Evidence status:** this inventory verifies public code. A subsequent
[real step 0 cycle](phase2-step0-validation.md) verified the six booleans below,
loaded CRT exports and restoration of the player's profile after a cold restart.
It does not verify every option or equivalence to the game without RE_Kenshi.
The API used must be verified in the loaded binary/SDK; no assumed private
symbol or offset.

The [cold reference controller](original-reference.md) documents commands
and scope. Its initial profile covers six RNG/speed/override booleans;
the conservative profile's geometric options are not implicitly declared
verified by this surface. The first successful cycle covers one `ville-calme`
repetition at schema 0.1; it does not replace validation of contract 0.2,
the adapter or the comparator.

<a id="écarts-connus-et-classement"></a>

## Known deviations and classification

Residuals without switches include speed callbacks, `srand` initialization,
camera/focus/cursor, infrastructure, codecs, deferred audio and error handling.
Their provenance specifies activation/scope; the 1.0.65 baseline difference
against the MeitouClient studied on 1.0.68 also remains tracked.

The comparator does **not classify every difference** as a “known deviation”
merely because RE_Kenshi is present. Attribution requires mechanism,
field/indicator, effective condition and applicable evidence. Without attribution,
retain the statistical class or “not comparable”. For example, x2/x5 callbacks
alone cannot explain a different population without keyboard input in the scenario.

<a id="références-versionnées"></a>

## Versioned references

[settings]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/Settings.cpp#L35-L76
[misc]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/MiscHooks.cpp
[speed]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/dllmain.cpp#L131-L313
[callbacks]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/dllmain.cpp#L1525-L1577
[limits]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/dllmain.cpp#L751-L918
[limitsinit]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/dllmain.cpp#L1266-L1365
[heightmap]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/HeightmapHook.cpp#L215-L405
[heightmapenum]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/HeightmapHook.h#L10-L18
[physics]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/PhysicsHooks.cpp
[modsettings]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/Settings.cpp#L174-L300
[fs]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/FSHook.cpp
[plugins]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/Plugins.cpp
[shader]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/ShaderCache.cpp#L651-L703
[ogre]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/OgreHooks.cpp
[camera]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/dllmain.cpp#L965-L973
[guiupdate]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/dllmain.cpp#L1594-L1667
[sound]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/Sound.cpp
[bugs]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/Bugs.cpp
[sic]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/OgreSICCodec.cpp
[dds]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/OgreDDSCodec2.cpp
[io]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/io.cpp
[version]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/Version.cpp
[startup]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/dllmain.cpp#L1744-L1915
[entry]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/blob/v0.3.5/dllmain.cpp#L1929-L2007
[wiki]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/wiki/RE_Kenshi-Features
[release035]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/releases/tag/v0.3.5
[release032]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/releases/tag/v0.3.2
[release033]: https://github.com/BFrizzleFoShizzle/RE_Kenshi/releases/tag/v0.3.3
