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

Character discovery is enabled, but mutation commands still return
`scene_action_not_configured` until each action is wired to a reviewed,
restricted VaM API. This prevents an unreviewed network command from mutating
arbitrary VaM storables. Keep the endpoint on loopback and add a shared token
in both VaM and Miya (`MIYA_VAM_TOKEN`) before enabling control actions.

The wire contract is documented in [`docs/VAM_BRIDGE.md`](../../docs/VAM_BRIDGE.md).
