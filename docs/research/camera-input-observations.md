<a id="caméra-en-pause-et-défilement-au-bord"></a>

# Paused camera and edge scrolling

Since 0.7.1, controlled scenarios temporarily disable `OptionsHolder::edgeScrolling` in memory and restore it at the next accepted load. The `settings.cfg` file remains unchanged. The native Heng inventory under 0.7.0 observed `edge_scrolling=false`, active control ownership, `mPos=[0.5,0.5]`, `mPosAbs=[640,360]`, and false direction/Ctrl states; reloading observed `edge_scrolling=true` and inactive ownership. These fields describe the input seen by the engine at those instants, without proving the physical pointer position during earlier drift. Evidence: `runtime/scenarios/battle-candidates.json` and restoration of `battle-20261028T012023Z.json`.

The user suggests that the camera drifts when the mouse leaves the screen or game window. The initial local setting is Edge scrolling=1 (Re_Kenshi/settings.cfg, line 7). The SDK also exposes OptionsHolder::edgeScrolling in OptionsHolder.h and the options global in Globals.h; InputHandler.h exposes mPos/mPosAbs and key states through the key global. These fields have been read since 0.7.0; a point observation does not establish the cause of earlier drift.

Drift was observed while paused and after some restorations, while game hours remained frozen. Controlled benchmark windows are verified separately. One invalid measurement window with a moving camera was excluded and the checks strengthened; a paused game does not necessarily mean a stationary camera.

A temporary test changed only Edge scrolling=1 to 0, after stopping only the project's processes and saving the exact file. After restarting and restoring the copy, the camera did not change for 10,020 seconds: runtime/scenarios/edge-disabled-observation.json. The physical pointer was not controlled throughout the interval.

The original bytes were then restored and verified against SHA-256 5c221a0b0bca397a377ce4bd683b252d1f5599b027d63205da736f976c4db98a. After this second restart with Edge scrolling=1, the view also remained stationary for 10,012 seconds: runtime/scenarios/edge-enabled-restored.json. **These two intervals therefore do not show that the setting alone explains the earlier drift.** Restarts and the lack of control over pointer position are confounding factors.

The user's usual setting remains enabled; no permanent change was retained. runtime/edge-test-state.json has restore_required=false and the exact backup is in runtime/settings-before-edge-test.cfg. The copy is paused again. An optional manual observation with the pointer outside the window was requested; tools/research/live_idle_camera.py records only the camera for one minute, sends no input, and stops observing if the world is unpaused.

The one-minute recording completed with 60 samples, zero maximum displacement, and pause maintained: runtime/scenarios/manual-pointer-observation.json. No user response had yet confirmed the pointer position during that interval. It therefore does not confirm the outside→drift link. If the user responds “Fait” later, start a new observation at the time of that response; do not associate it retroactively with this recording.

A causal conclusion requires comparing pointer positions that are actually controlled while keeping other inputs unchanged, or adding read-only telemetry for public SDK input fields after verifying the symbols. Do not attribute all drift to the mouse without this evidence, or permanently change preferences to stabilize a measurement without preserving the original state.
