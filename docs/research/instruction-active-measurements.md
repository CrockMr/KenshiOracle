<a id="observations-rip-actives-sans-élévation--28-octobre-2026"></a>

# Active RIP observations without elevation — 28 October 2026

Lightweight PSS also works during simulation at Heng: a pilot of 12 captures, a series of 60, then a cadence check of 60, all completed with restoration. **No administrator, memory clone, attached debugger, or new hook.** The plugin remains 0.8.9, v100 x64, 17 tools/three probes. These observations identify user addresses and modules; they provide neither stacks nor per-function CPU percentages.

<a id="acquisition-et-reproductibilité"></a>

## Acquisition and reproducibility

`tools/research/live_instruction_active.py` selects the four highest-consuming identities from the completed CPU 0.8.9 recording, checks the same PID/path/command/creation time, and prepares Heng from KenshiProbe_test. Native process identity is read with GetProcessTimes, independently of floating-point rounding. Each capture must find exactly the requested TIDs and creation FILETIMEs. PSS uses flags0x180/contexts 0x100003, without VA clone or stack reads. Registers are copied before releasing the snapshot; modules are checked before/after and between captures.

The controller limits the series to 120 captures and each complete call to 250 ms. The completed tests request random delays of 0,8..1,2 s, with the seed retained. The first series read the MCP scene immediately before capture; the second places the delay **after** that read to reduce possible synchronization with the main thread. The actual retained delays between scene and capture are 0,813308..1,220051 s in the second series. This change does not prove that all PSS or scheduling bias is eliminated.

| Test, directory under runtime/instruction-active | Captures | Helper total | Max helper | Mean process CPU |
|---|---:|---:|---:|---:|
| 20261028T130858520293Z, pilot |12|108,557 ms|10,437 ms|2,389649 logical processors|
| 20261028T131248766820Z, scene then capture |60|541,348 ms|12,790 ms|2,283443|
| 20261028T131640088252Z, scene then delay then capture |60|550,530 ms|12,619 ms|2,160076|

These helper times include opening, module inventories, capture, copying, and cleanup. They are **not** the target's exact suspension duration. The PssCaptureSnapshot call alone totals 106,044 ms in the last series; this does not measure a global game pause either. The controller and its requests have their own cost, which is not causally isolated. No tests or compilation during acquisitions.

Each directory contains controller.json. Respective SHA-256 values:

- Pilot: **099ad389c675f3a230de7f651a3dad528e392667a06dd732c22e19336c2e313e**.
- Initial series: **7c85baacd133854568c3d8fece4a7a1b69f9f396c64b73f99aa945c5307a5881**.
- Series with separation: **3d8cab8cf198d92ef47033ad7f56ab79f60c12d1a66fd196608a12c90657875d**.

`tools/research/analyze_instruction_active.py INPUT --expected-sha256 SHA --output NOUVEAU_FICHIER` replays identities/contexts/modules, counts, durations, scene order, camera/speed, progression, native CPU counters, and attested restoration outside the game. It rejects an existing output file. Reports: `runtime/instruction-pilot-active-analysis.json`, `runtime/instruction-series-active-analysis.json`, and `runtime/instruction-series-separated-analysis.json`. Their basic counts remain reproducible; additional cadence metadata exist only in the last report. File preservation is a controller attestation retained in these raw files; the final audit separately recalculates their actual manifests.

**505 tests pass in 21,18 s**, including corrupted counts/CPU cache, reused identity, contradictory module, missing creation time, capture order, camera, speed, restoration clock, and false separation delay. Network tests require local access outside the sandbox; this grants no Windows administrator privileges.

<a id="ce-que-montrent-les60-observations-séparées"></a>

## What the 60 separated observations show

Process **39204/creation FILETIME134376639120505830**, executable verified. Process window 64,610 s, 139,562500 s CPU, mean 2,160076 logical processors. Signed residual **+0,093750 s**, no omitted thread identity; residual retained without assignment to a module. The scene advances by 0,592155457 h over 64,601911 s; complete boundary inventories399→440. Population and streaming evolve.

| TID/creation FILETIME identity | Whole-thread CPU | Addresses observed by module, out of 60 |
|---|---:|---|
|35744/134376639120505844, main/render|52,203125 s,0,808173 logical processor|Ogre22, ntdll13, D3D119, RenderSystem7, MyGUI5; CRT, engine, terrain, and graphics driver1 each|
|32156/134376639240826668, unattributed function|8,015625 s,0,124092|ntdll56, Plugin_Terrain3, Ogre1|
|13132/134376639240828501, previously verified SDK non-render role|19,265625 s,0,298257|ntdll48, engine12, each of the 12 engine RVAs observed once|
|12820/134376639144112817|10,890625 s,0,168601|ntdll54, graphics driver4, win32u2|

Thread normalizations use their own 64,594 s bounds, distinct from the process bounds. Module observations are not CPU shares. A user context in ntdll proves neither permanent inactivity, the calling function, nor the kernel-mode execution location. In the previous series, 32156 had 60 ntdll contexts while consuming 14,046875 s CPU; inferring zero work would be incorrect. RPC/capture separation changes observations, and the scene also evolves: no CPU difference between these series is causally attributed to that change alone.

The controller also retains addresses not associated with a module: one such main-thread observation in the first series remains unknown, without arbitrary association to the neighboring module. Historical SDK/BirdManager names are not transferred to 32156 from its TID or a module name.

<a id="restitution-et-prochaine-mesure"></a>

## Restoration and next measurement

All three tests return to **404,3333339691162 h**, copy paused and camera control released. All PSS cleanups are verified, saves and settings preserved. The independent audit `runtime/instruction-active-final.json` rechecks the 702/702/738 source/copy/snapshot files, DLL, roles, watchdog, and deadline. No persistent capture helper; watchdog/bootstrap remain bounded to 28 October22 h15 UTC.

The series expands the observed execution locations without isolating a new bottleneck or justifying a fourth hook. The next priority is a heavy x5 condition with effective speed/clock, windows adapted to the actual number of frames, complete inventories, and restoration. Any address annotation must retain the exact build, verified SDK binding, and ambiguous regions; do not substitute the nearest symbol for this evidence. No engine algorithm changed or performance gain demonstrated.
