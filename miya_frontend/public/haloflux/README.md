# Miya soul resonance field

Modified from **HALOFLUX by Ryder191 (RYDER CODE / Ms MAIKEBAIs CAT)**.
The original copyright notice remains in `lab.html`; the upstream license is in `LICENSE`.

The Miya app loads `lab.html?ambient=1&miya=1` through `MiyaFluxScene.vue`.
`miya.js` adds the complete halo, circular Miya portrait, six memory anchors,
porcelain-blue emotion colors and three visual modes. Opening `lab.html` without `miya=1` retains the
original console. No external runtime or additional audio is loaded by Miya mode.

The parent sends `miya:presence` messages from the same origin and is the only
source of live readings. `useMiyaPresence` shares a 15-second poll of `/api/status`
and `/api/persona/current`, supports both normalized camelCase and native backend
keys, cancels requests on unmount and retries on visibility restoration.

- The default portrait is the user-selected `696c945479c7dc7be250e671ceeab7a1.png`,
  copied without modification to `miya-avatar.png` so it works after packaging.
- The portrait editor accepts PNG/JPEG/WebP up to 15 MB, resizes custom images
  locally to at most 1024 pixels, and saves the image, crop and flow strength in
  `miya-flux-portrait`. Upload failures leave the previous portrait intact.
- Crop controls set zoom and horizontal/vertical position. Foreground data streams
  are clipped to the circular portrait and can be adjusted from 0 to 75 percent.
- The portrait stays upright while the surrounding halo turns. The portrait
  renderer uses a separate same-origin `miya:portrait` message so large image data
  is only sent when portrait settings change or a scene loads.
- Emotion changes the glaze within a blue-and-white porcelain palette; selected
  runners, comets and foreground data use the same color.
- Activity sets the tempo, rotation, beam intensity and runner population.
- A rising memory count triggers a porcelain-white echo; initial load and reconnection do not.
- The six memory anchors and micro data blocks are artistic representations,
  not per-layer counts or task execution telemetry.
- Offline readings display `—`; the visual settles to an idle rhythm.
- Modes and pause preference persist across the observatory and home ambient layer.
- Pausing stops the animation loop; hidden documents suspend it. The initial pause
  preference follows `prefers-reduced-motion` until explicitly changed by the user.

Verification: `node --test tests/miya-presence.test.mjs` from `miya_frontend`.
