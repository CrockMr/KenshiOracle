<a id="préparation-des-scénarios-lourds--api-repérées"></a>

# Preparing heavy scenarios: identified APIs

Status: **a populated scene near Heng was obtained in 0.6.0**, without an additional system hook. Camera movement alone (0.5.x) was insufficient; moving the player group on the copy loaded residents. No battle was created.

<a id="ville-peuplée"></a>

## Populated town

- Globals.h exports shou (SharedKing*); SharedKing.h declares townList (TownList*).
- Town.h declares TownList::getAllTowns(), getActiveTowns(), getTownBySID() and getNearestInOrder(). The list_towns inventory uses getAllTowns and inherited getPosition/getName/getFaction methods. There were 304 observed town definitions and one active town at the starting point. The first hundred are archived in runtime/scenarios/town-inventory.json.
- PlayerInterface.h provides getCamera() (CameraClass*). CameraClass.h provides the reads and mutations used by get_scene_state, focus_town and set_camera_free. Import symbols were checked, then v100 linking succeeded. These commands run on the GameWorld thread; mutations require pause.
- Native attempt on October 27 at 23:37 UTC: runtime/scenarios/city-20261027T233742Z.json. Heng's position comes from the inventory: [48029.58984375,1503.591430664063,-41953.01171875]. The immediate response puts the camera at the expected x/z, but after five seconds it returned to [50333.62109375,1046.910522460938,-16135.9296875]. Free mode=true, one active town; 178 then 176 update entries after fifteen seconds at x1. **No populated-town scene was validated.** The cause of the restriction was not demonstrated; CameraClass::restrictPosition is declared but not called by the plugin.
- Reloading retains free mode. Fix 0.5.1 exposes set_camera_free to restore this boolean **before** reloading; changing it afterward moves the view. Attempt 0.5.1, runtime/scenarios/city-20261027T234107Z.json, confirmed the same Heng limitation. Corrected final restoration is in runtime/scenarios/restored-camera.json: center=[50759.15625,997.8407592773438,-14012.9853515625], position=[49933.14453125,1655.223999023438,-15577.66015625], free_camera=false, paused=true. Positions equal the initial observation. tests/live_restore.py applies this order; live_city.py reuses that helper. The first 0.5.0 attempt did not restore the boolean; do not present it as complete restoration.
- Preparation in 0.6.0: PlayerInterface::getAllPlayerCharacters(), Character::getMovement()/isPlayerCharacter() and CharMovement::halt()/_setPositionDirectionAndTeleport are declared in the local SDK. Using this controller for an absolute position is corroborated by [KenshiCoop, EngineEntity::park](https://github.com/nhoral/KenshiCoop/blob/main/src/plugin/game/EngineEntity.cpp), consulted on October 28. Our implementation uses public methods and no RVA. OgreMain_x64.lib is added as in the official CharacterHighlight example, for vectors/quaternions; the first link without this library failed and was corrected.
- prepare_town_scene requires pause and the last probe-requested load to equal KenshiProbe_test. All characters and positions are checked before mutation; only a local group of 1..32 characters is accepted. It retains x/z offsets and uses town altitude and identity orientation. This guard does not detect a later UI load. Do not mix the scenario with manual loading.
- First native call: runtime/scenarios/populated-20261027T235525Z.json. Immediately returned positions were still the originals; a subsequent world_ready=false transition interrupted the first collection and its immediate restoration. The process did not exit. Scripts now wait for the ready world to return before observing and restoring; do not repeat the mutation during the transition.
- Observation resumed without another move: runtime/scenarios/populated-20261027T235611Z.json. Ryers/Okada reached the requested x/z, with ground y approximately 1507. Two active towns; 447..453 characters in the update list and 160..167 within an x/z radius of 2000 units around Heng, across six observations five seconds apart. Even excluding the two players, this is an observed population. The camera is stable at [48234.80078125,1243.616943359375,-39723.90234375], approximately 2240 units from the center: do not describe it as centered on the town square.
- Restoration confirmed: one active town, 106 update entries, identical initial camera positions, free mode false, pause true, unchanged source SHA-256 and the same PID 9772. The scene is reconstructed by loading and preparing the copy; it is not saved, and its evolution may vary with streaming and caches.

<a id="bataille"></a>

## Battle

The current save of two player characters in Gut is not a prepared battle. Two approaches remain to investigate: create a repeatable scene on the copy through public spawning/order APIs, or use an existing battle save if available. Exact spawning functions and their invariants still need checking against examples and headers; entity creation must not be improvised.

Retain the reference state, participants, factions, initial orders, positions, camera, speed and warm-up. Do not overwrite KenshiProbe_validation. Scenarios must reload from a known copy, and game files must remain outside Git.
