<a id="attribution-du-cpu-aux-threads--28-octobre-2026"></a>

# CPU attribution to threads — October 28, 2026

The native ten-NPC Mongrel campaign consumes **2,304 logical processors on average** over 45,094 seconds. The thread shared by GameWorld and Renderer service accounts for 34,33 % of process CPU; a worker observed in navigation calls, 7,34 %; other threads, 58,35 %. This record identifies where to continue diagnosis. It measures no optimization gain and cannot yet name the other threads' dominant functions.

The plugin remains **0.7.5, v100 x64**, with the three existing system hooks. No additional hook, game stop or deployment for this campaign. Every scenario command goes through a real stdio MCP session; OS counters are read separately by the Python controller.

<a id="preuves-et-reproduction"></a>

## Evidence and reproduction

- Local raw capture: `runtime/scenarios/battle-20261028T025346Z.json`, SHA-256 `653b2130e9504c8ab900d682bc5f3352269da6461ca26f848c1a05981ddff589`.
- Report: `runtime/thread-cpu-analysis.json`; thread descriptions: `runtime/thread-descriptions-20261028T025346Z.json`.
- Final verification: `runtime/scenarios/thread-cpu-campaign-075-final.json`.

From the project root:

```powershell
$env:PYTHONPATH="$PWD/mcp-server;$PWD"
& ./.venv/Scripts/python.exe tools/research/live_battle.py 16863-gamedata.base --faction Bloodraiders --opponent-template 1227-gamedata.base --opponent-faction 'Mercenary Guild' --town Mongrel --focus --interval .25 --seconds 45 --pairs 5 --mcp --thread-cpu
& ./.venv/Scripts/python.exe tools/research/analyze_thread_cpu.py runtime/scenarios/battle-20261028T025346Z.json --output runtime/thread-cpu-analysis.json
```

The first command repeats a trial and restores the copy paused; the second only reanalyzes the specified raw capture. Actor generation is unseeded, town reinforcements intervene and population grows from 141 to 218. This recipe reproduces the protocol without guaranteeing an identical battle. Comparison between campaigns or speeds requires a controlled initial state, notably the pose guard described in scene-snapshot-measurements.md.

<a id="résultat-de-lintervalle-englobant"></a>

## Enclosing-interval result

Total process CPU: **103,875 CPU seconds** in 45,094 real seconds. The following shares use this same denominator; they are not renormalized.

| Exclusive counting group | CPU seconds | Mean logical processors | Share of process CPU |
| --- | ---: | ---: | ---: |
| GameWorld and Renderer thread, TID 35716 | 35,656250 | 0,790709 | 34,3261 % |
| Worker observed in navigation, TID 37196 | 7,625000 | 0,169091 | 7,3406 % |
| Other identified threads | 60,609375 | 1,344067 | 58,3484 % |

The shared thread is counted once. Its CPU includes all work executed on that thread, including rendering. Navigation-worker CPU also includes all its work: **7,34 % is not findPath's exclusive share**, and other navigation workers may remain unidentified.

Among threads without an established role, TIDs 39984, 37324 and 32072 consume 10,500000, 8,328125 and 7,031250 CPU seconds respectively. A later read of Windows descriptions for the twelve dominant threads returned empty strings only. No system name, notably physics or graphics, is assigned to these threads without supporting stacks or symbols.

<a id="méthode-et-limites"></a>

## Method and limits

`WindowsThreadSampler` requests only limited-query access, verifies PID ownership and reads creation times and CPU counters through GetThreadTimes. FILETIME dates remain decimal strings to preserve their bits in JSON. A TID is joined across boundaries only if its creation time matches. Handles are closed immediately, even after an error. A live thread's exit field is not interpreted: Windows documents it as undefined. See [GetThreadTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreadtimes) and [GetProcessIdOfThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocessidofthread).

The boundaries inventory **120 matched identities**; three threads absent at the second boundary are explicitly excluded, without inventing their CPU. Sequential reads take about **94 ms then 63 ms**. Counters are quantized and process/thread boundaries are not simultaneous: the thread sum is 103,890625 s, yielding a signed process-minus-thread residual of **−0,015625 s**. This residual remains visible; it is not artificially clamped to zero. The interval includes MCP reads and waits, without exact alignment to a frame window.

Roles come from heartbeats and only retained slow calls whose ending frame falls within the observed interval. The 3600-frame diagnostic context counts 66 above-threshold calls but retains only 32: `retention_truncated=true`. It is not an exhaustive worker inventory. The final 600-frame window remains separate: 201 completed findPath calls, 200 true and one false, maximum 126,208 ms; mean frame interval 9,050 ms, p99 12,902 ms. This last sample alone does not represent the 45 seconds.

GetThreadDescription reading also verifies identity and releases returned memory; a description can change and does not prove the function executed. See [GetThreadDescription](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getthreaddescription).

<a id="prochaine-attribution--piles-cpu-windows"></a>

## Next attribution: Windows CPU stacks

A local two-second pilot on the paused copy is ready in `tools/research/live_etw_pilot.py` with `tools/research/cpu-sampling.wprp`. It uses a unique WPR instance and stops only that instance. Requested providers cover CPU, processes and modules system-wide; analysis must select the game's identity and lifetime. No disk, network or registry provider is requested. Traces remain local in runtime/etw, ignored by Git. See [WPR options](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options) and [CPU analysis](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cpu-analysis).

Attempt `runtime/etw/KenshiProbePilot_dd0f07a66fb0/controller.json` fails at startup with **0xc5585011**, « Failed to enable policy to profile system performance ». The current token is not administrator. No trace was created, no session remained active and the game stayed paused. This is a Windows permissions rejection; no system policy was changed. The user was asked to run the pilot in administrator PowerShell or continue without system capture. Until that intervention is confirmed, do not repeat the same startup.

If the pilot succeeds, verify manifest, instance shutdown and trace before a longer combat capture. Then identify dominant stacks using available symbols, without assuming a TID has an exclusive function. Choose an improvement based on those stacks; any new native target must replace an existing hook to preserve the maximum of three.

<a id="restauration-et-validation"></a>

## Restoration and validation

The **702 KenshiProbe_validation files and 702 KenshiProbe_test files** each match their control manifest after the campaign. PID 19892 and creation unchanged, plugin 0.7.5, game available paused, reference camera and normal mode, Edge scrolling=1, no active tracked combat and preference-restoration guards false. The watchdog remains healthy and bounded to October 28 at 22:15 UTC; no WPR capture is active at the final check.

**124 Python tests pass in 3,94 s**, covering reused identities, regressing counters, missing boundaries, signed residual, groups without double-counting and merged navigation contexts. Synthetic tests validate processing; native raw evidence above establishes game observations.
