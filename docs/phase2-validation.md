<a id="phase-2--validation-fonctionnelle-et-comparaison-réelle"></a>

# Phase 2: functional validation and real comparison

Local validation on October 29, 2026. The original reference profile, the
opt-in Meitou adapter enabled by `--oracle`, additive state 0.2 and the
comparator produced a **quiet-town comparison with N = 5 against N = 5**.
The results describe these observations; five repetitions do not establish
generalization.

**Saves with mod definitions.** These campaigns used saves that reference
Workshop mod definitions (**Verified** by save inspection). The original
registered mod resource locations (**Observed**); the effective load order is
**Unknown**. See
[earlier figures obtained with mods](mod-free-campaigns.md#earlier-figures-obtained-with-mods).

Publication rebuild: [KenshiProbe 0.10.0](../release/v0.10.0-notes.md) packages
the current native source separately from the campaign binaries identified
below. After the research-directory reorganization, the complete Python suite
passed again from the clean public checkout: **1,975 passed, 25 skipped** in
**106.70 seconds**. Six portable native scripts passed from another working
directory, with 344 counted assertions plus the JSON parser checks. These
build, unit and packaging checks add no new real-game loading claim.
The current probe release is [0.11.0](../release/v0.11.0-notes.md); it adds
scene setup, whose live validation is pending, and changes none of the
results below.

**Time note.** The "two minutes" and "ten minutes" checkpoints below
(scenario `at` 120 and 600) are game **calendar** time, not simulated or real
time. Per MeitouClient's constant of `1200/11` simulated seconds per in-game
hour (**Verified** in its code), they correspond to about **3.6** and
**18.2 simulated seconds**. On MeitouClient that ratio is **Verified** in code
(`Simulation.TickSeconds` 1/30) and its 1.1-calendar-second checkpoint steps
are **Observed** and consistent with it; on the original the engine reports the
same 109.09-second hour (**Verified**) and the calendar advances about 33
calendar seconds per real second at x1 (**Observed**), but no simulated-time
counter is read (**Unknown**); see [time units](protocol.md#time-units).

The evidence links below refer to **local artifacts ignored by Git and not
distributed**. No dump, save, private configuration, game image or decompiled
code is copied into this report.

<a id="campagnes-et-restitution"></a>

## Campaigns and restoration

| Target and scenario | Repetitions | State-0.2 snapshots | Verified scope |
| --- | ---: | ---: | --- |
| Original, quiet town | 5 | 15 | Effective cold-start profile, canonical captures, controls restored, then player profile restored and verified. |
| Meitou, quiet town | 5 | 15 | Seeds 0..4 applied before loading; C# captures identical to Python canonicalization; controls and initial seed 1729 restored. |
| Meitou, small battle | 1 | 3 | Orders using two saved HANDs, observed health changes, verified captures and restoration. |
| Meitou, squad travel | 1 | 3 | Move order, verified captures and restoration; no statistical evidence at N = 1. |

The [original acceptance evidence](../../phase2-live-original-five/acceptance.json)
and N = 5 report (local evidence, not published)
record six RE_Kenshi options set to false during the experiment, GUI and CRT
export observations, then restoration of the player profile after a cold
restart. The INI, `settings.cfg`, previous DLL and four protected saves were
restored or unchanged. The [first cold-start milestone](phase2-step0-validation.md)
retains its historical state-0.1 scope.

The [three-scenario Meitou acceptance evidence](../../phase2-meitou-scenarios/20261029T200649Z/acceptance.json)
records **21 snapshots**, seed 1729 after each restoration, the owned process
stopped, and preferences and four saves unchanged. Reports:
quiet town (local evidence, not published),
battle (local evidence, not published),
travel (local evidence, not published).
Initial preparation loads the population without an unclocked simulation or
combat tick; `startup_boundary` identifies that boundary in provenance.

The [Meitou supervisor smoke test](../../phase2-meitou-watchdog-smoke/20261029T202354Z/acceptance.json)
validates the production launch path: seed 2718, matching PID/instance, a ready
paused world, a fresh heartbeat, cancellation followed by owned-process
shutdown, and `state.running=false`. Preferences were copied into its private
directory; input configuration, four saves and player settings were unchanged.
This test did not induce a real crash or freeze to validate a Meitou restart.

<a id="builds-et-tests"></a>

## Builds and tests

Campaign binaries are identified by SHA-256:

| Component | Identification |
| --- | --- |
| Phase 2 KenshiProbe, Kenshi 1.0.65/RE_Kenshi 0.3.5/KenshiLib 0.5.0 | `a42ac22176204e2a9cfea9e938adc87ba15fa1baa17d9914c9564698040ed512` |
| MeitouClient, local `oracle-adapter` branch, base `1df44934efd32c49998e7f3aa75d877fb499459a` | `a378c8c55371e6dc8c48f5f84d877aaa4162fbf845848c395568160b3cabb947` |

The [Meitou source/build manifest](../../phase2-meitou-build/oracle-source-provenance.json)
links changed files to the tested binary. It supplements the save fingerprint,
which covers neither assets, mods/load order nor builds.

| Check | Result and limitation |
| --- | --- |
| Shared canonicalization | 62 C#/Python/native vectors, including 59 historical cases; identical expected bytes. |
| Complete Python suite, phase 2 English sources before publication reorganization | **1,975 passed, 25 skipped, zero failures**, 101.57 s; log (local evidence, not published) and JUnit (local evidence, not published). |
| Targeted Meitou Oracle/camera tests | [115 passed, zero failures](../../phase2-meitou-build/oracle-loading-boundary-tests.txt). |
| Fast Meitou subset before the preparation fix | [577 passed, 2 skipped](../../phase2-meitou-build/meitou-quick-tests.txt); historical evidence, not a substitute for the current complete run. |
| Complete Meitou suite excluding `Bench` | **716 passed, 11 failed, 24 skipped**; this suite is not green. |

The [11 failing cases](../../phase2-meitou-build/upstream-baseline-comparison.json)
were rerun on the upstream commit without the adapter: the same cases failed
with identical messages. This bounds attribution in the installed environment;
it neither resolves their causes nor turns the run into a success. Skipped
cases include a Vulkan device not declared available by those tests and
platform-specific cases for other operating systems.
No assertion was weakened and no performance campaign was added.

The **25 Python skips** are explicit: 24 optional local-capture references
ignored by Git, whose synthetic checks remain portable, and one symbolic-link
test requiring Windows Developer Mode or an unavailable privilege.

The [phase 2 source audit before publication reorganization](../../phase2-final-source-audit.json) examines 393
KenshiOracle files, 26 fork changes and 99 documents/examples: no game file or
binary is published, and no personal path is included. Fictitious absolute-path
counterexamples in seven test files are listed separately. The native DLL's
CodeView reference is exactly `KenshiProbe.pdb`, without the Windows username
in ASCII/UTF-16. The **210,231 checked local report links** contain neither
broken links nor absolute paths.

All public documentation is in English, including historical research notes,
tool descriptions and generated comparison reports. The [documentation
policy](../AGENTS.md) applies to future additions. Measurements, hashes and
literal recorded output are preserved; legacy heading anchors keep existing
section links working. The independent review covered 75 public Markdown
files. Links to ignored local evidence remain unavailable in a fresh public
clone, as stated above.

<a id="résultat-de-ville-calme"></a>

## Quiet-town results

The readable report (local evidence, not published),
detailed JSON (local evidence, not published) and
English drafts (local evidence, not published) use the
two certified campaigns, the same scenario/save and Meitou seeds 0..4.
Absolute tolerances: positions/distances **1e-6** world unit, other numbers
**0**; X/Z arrival radius **5** world units.

The main report is a **25,579-byte** index, with a preview of 20 strong
discrepancies and **203 detail pages**, at most 100 metrics per page. The
complete JSON retains **173,346,900 bytes** of observations and statistics.
The [rendering proof](../../phase2-comparison-render-proof.json) confirms the
same 90,102 findings and 291 drafts before and after pagination; no class was
changed to reduce Markdown size.

| Class | Fields or metrics |
| --- | ---: |
| Stable divergent | 291 |
| Stable identical | 69,991 |
| Variable outside range | 648 |
| Attributed known deviation | 0 |
| Variable compatible | 316 |
| Not comparable | 18,856 |
| **Total** | **90,102** |

**291 metrics do not mean 291 bugs.** Axes, checkpoints, counts, states and
groups overlap; one population or movement difference can produce several
rows and issue drafts.

| Family among the 291 stable divergences | Count |
| --- | ---: |
| Saved-character coordinates | 77 |
| Faction/template groups: squads and members | 69 |
| Total/per-faction population, states and unpaired entities | 67 |
| Initial-cohort size/survivors | 30 |
| Character combat mode | 28 |
| Final squad positions and distances | 8 |
| Current health/stun | 5 |
| Directional relations and changes | 4 |
| Clock | 2 |
| Observed engagement of one faction | 1 |

Three examples bounded to this run, with N = 5 on each side:

1. **Loaded population at two minutes**: the original has **103** in all five
   repetitions; Meitou has **139, 137, 151, 159, 139**, median **139**, all five
   observations outside the reference. The scope is loaded entities, not world
   population; this motivates an audit of loading and generation rules.
2. **Height of a saved character at two minutes**, HAND
   `hand:1:10:801513664:1:1702636672`, field `position/1`: the original is
   constantly **1591.878906**; Meitou spans **1581.197632..1581.245728**, median
   **1581.221191**. All five values differ from the reference by more than the
   **1e-6** tolerance. This does
   not identify the cause: geometry, navigation, state and the semantics of
   position projection still need examination.
3. **Directional relation at ten minutes**, `1088-gamedata.base` to
   `1305-gamedata.base`: the original is constantly **-10**; Meitou is **-10**
   in four repetitions and **-10.000625** in one. At tolerance **0**, this
   small difference is classified as stable divergent; confidence in the
   observation and gameplay severity are separate questions.

The **648** variable-outside-range metrics are a weaker signal: the observed
range of five original repetitions is not its entire distribution. The **316**
compatible metrics do not establish general parity. Of the **69,991** identical
metrics, **63,032** are relation values/deltas: these correlated counts are not
an overall engine-fidelity score.

The **18,856** not-comparable metrics represent gaps in coverage, including
**14,256** relation metrics and **1,932** health maxima. RE_Kenshi residuals
are recorded as context; no applicable documented cause reclassified a
divergence as a known deviation. The 291 `issues/` files are **drafts to group
and review**; no issue has been published.

<a id="limites-et-travaux-restants"></a>

## Limitations and remaining work

- Prove equivalence between town-placement keys
  `Town::instanceID.uid`/`TownSite.InstanceId`; current assignment and origin
  remain null. Do not match by name, `TOWN` definition, index or current HAND.
- Complete Meitou `health[].maximum` and `order` after proving their semantics;
  unknown values remain null, never zero.
- Observed polylines are lower bounds. Net displacement, exact arrival, full
  trajectory and cumulative combat duration are not interchangeable. Arrival
  requires every member within the X/Z radius; its interval remains
  `[0, first observation]`. An engagement span does not prove continuous combat.
- Meitou battle and travel each have only one repetition: functional
  validation does not replace comparative campaigns with N ≥ 5.
- Do not generalize this run to every save, installation/mod set or future
  commit. A known seed and canonical bytes do not eliminate differences caused
  by asynchronous services.
- Maintain the [small local-fork integration](meitou-oracle-design.md), update
  explicitly from upstream and revalidate. The modding API remains a concept:
  loading, seed control, lifecycle and service while paused must exist before
  migration. No fictitious plugin framework is implemented.

The [comparison guide](comparator.md), [state coverage](state-coverage.md) and
[Meitou guide](meitou-target.md) define contracts and procedures.
