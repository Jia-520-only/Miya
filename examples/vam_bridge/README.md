# Miya VAM Bridge reference plugin

`MiyaVAMBridgeTcp.cs` is the recommended reference implementation for this VaM
installation. It uses `TcpListener` and VaM's bundled `SimpleJSON`, so it does
not need `WebSocketSharp.dll`.

For VaM package installation, use `Miya.MiyaVAMBridge.1.var`. The package
contains the script, its `.cslist` manifest and metadata, and should be copied
under `AddonPackages` before starting VaM.

1. Copy `MiyaVAMBridgeTcp.cs` to `VaM/Custom/Scripts/Miya/`.
2. In the current VaM scene, select any Atom (use the main Person Atom), open
   its Plugins panel, choose **Add Plugin -> C# -> Custom Scripts -> Miya ->
   MiyaVAMBridgeTcp.cs**, and confirm the script compilation dialog.
3. Confirm the VaM log contains `ws://127.0.0.1:8765/miya-vam`, or check that
   local TCP port `8765` is listening.
4. Start Miya and call `vam_status`.
5. Call `vam_list_atoms`. The bridge automatically allowlists every live
   `Person` Atom in the current scene. Characters that only exist as packages
   or presets under `AddonPackages` appear after they are loaded into a scene.

Set the plugin's `sharedToken` field and Miya's `MIYA_VAM_TOKEN` to the same
random value before enabling control actions. The reference plugin rejects all
commands without that token when the field is non-empty.

The bridge deliberately disables `vam_inspect_person`: broad storable and
parameter enumeration can exhaust the VaM/Mono heap in complex scenes. Use the
fixed expression, gaze, and bounded `vam_move_person` controls instead; typed
plugin controls require a known storable and parameter supplied by the scene.
Call `vam_get_person_state` when a decision needs the current public values of
one controller or plugin. It is read-only and requires an explicit storable ID;
the autonomy loop does not scan all plugin state automatically.
For fluid interaction, `vam_run_sequence` accepts up to 32 timed steps and can
loop until stopped. The VaM main thread advances one step at a time, interpolates
facial morphs and root movement, and emits state updates when a sequence starts,
advances, completes, fails, or stops. Movement is limited to 0.25m per axis and
5 seconds per transition; stop restores the original root position.
Use `vam_autonomy_start` to let Miya periodically observe the bridge state and
submit a context-aware sequence only while the scene is idle. The bridge reports
the player's distance and gaze angle to each live Person; Miya uses these values
to choose a close, near, away, far, or unknown interaction strategy. The first
decision runs during startup, then the background loop waits for the configured
interval. `vam_autonomy_stop` pauses that loop; any manual `vam_run_sequence`
also pauses it.
The bridge rejects non-Person atoms, unknown storables/actions, invalid values,
and parameter batches larger than 32 entries. It never evaluates code sent over
the socket. Some third-party actions continue asynchronously; use that plugin's
own stop action when `vam_stop_all` cannot cancel it.

Keep the endpoint on loopback and set a shared token in both VaM and Miya
(`MIYA_VAM_TOKEN`) before enabling control actions.

The wire contract is documented in [`docs/VAM_BRIDGE.md`](../../docs/VAM_BRIDGE.md).
