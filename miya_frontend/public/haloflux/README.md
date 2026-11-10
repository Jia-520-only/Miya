# Miya soul resonance field

Modified from **HALOFLUX by Ryder191 (RYDER CODE / Ms MAIKEBAIs CAT)**.
The original copyright notice remains in `lab.html`; the upstream license is in `LICENSE`.
The app's visual-source credit is available in the observatory's status details.

The Miya app loads `lab.html?ambient=1&miya=1` through `MiyaFluxScene.vue`.
`miya.js` adds the circular Miya portrait, six memory sectors, two compositions,
porcelain-blue emotion colors and three visual modes. Opening `lab.html` without `miya=1` retains the
original console. No external runtime or additional audio is loaded by Miya mode.

The parent sends `miya:presence` messages from the same origin and is the only
source of live readings. `useMiyaPresence` shares `/api/observatory/events` (SSE,
three-second snapshots) and `/api/observatory/snapshot` (15-second REST fallback).
It accepts camelCase REST and native SSE keys, checks snapshot freshness, follows
dynamic API ports, and releases connections when hidden or no consumers remain.
The backend samples live persona/emotion, the spine heartbeat, MemoryBus's six
indexed layers, and the runtime platform registry. Missing sources stay unknown.

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
- Lifecycle sets the artistic tempo, rotation, beam intensity and runner population;
  emotion intensity is a separate, explicitly scaled reading, not an activity score.
- A rising memory count triggers a porcelain-white echo; initial load and reconnection do not.
- A rising spine message count triggers a smaller echo.
- The enlarged main band preserves the original dense micro panels and outward
  data streams. Selected panels show actual recent log excerpts; the remaining
  abstract patterns and light movement are artistic representations.
- Three lightweight satellite rings carry memory, execution, and perception/link
  records from the existing management SSE log stream. Six upright readings are
  integrated into the memory ring; its total and platform counts come from the
  independent observatory snapshot rather than being inferred from log volume.
- Ring ribbons, module/time micro panels and recent-event traces use actual log
  records. Hover or keyboard focus holds the ribbons and their preview; selecting
  a ring opens category history and full plain-text records. Category history is
  bounded to 160 entries per category; the execution counter describes retained
  live logs within 60 seconds, with a saturation marker rather than a task count.
- Module names determine categories, with limited message fallback for generic
  console output. Routine HTTP polling and connection chatter are filtered;
  warnings and errors remain visible in warm accent colors. Terminal escapes are
  removed; full records are rendered as text. Log display does not invoke a model.
- Initial/reset/resumed batches are history, never fresh activity. Live events
  create bounded traces and a short connecting light toward the main ring. Hidden
  pages release the SSE stream; reconnect uses the cursor, including after backend
  restarts. Dynamic management ports are followed. The backend log buffer assigns
  sequences under its lock to keep concurrent producers ordered.
- The observatory offers a complete ring with an edge note, or a cropped closeup
  with smooth camera push-in, travel along the rim and pullback. Composition is
  persisted independently of the resonance, surge and quiet visual modes. The home
  ambient layer keeps its own composition. The portrait and foreground follow
  the same camera transform. Satellite rings remain stable for reading.
- Offline readings display `—`; the visual settles to an idle rhythm.
- Modes and pause preference persist across the observatory and home ambient layer.
- Pausing stops the main animation, satellite rotation and closeup camera; hidden documents suspend it. The initial pause
  preference follows `prefers-reduced-motion` until explicitly changed by the user.

Verification: `node --test tests/miya-presence.test.mjs tests/miya-runtime-logs.test.mjs` from `miya_frontend`.

Observatory notes are composed by `MiyaObservatoryOrgan` with the current persona
and a dedicated model client, independently of Earth Online. `observatory` in
`config/qq_config.yaml` controls the switch, minimum interval (120 minutes by
default), and quiet hours. Failed or silent attempts wait at least 15 minutes;
the previous note survives. Notes and scheduling state are atomically stored in
`data/observatory/`. Opening/refreshing a page never calls the model.

Backend checks: `.venv/Scripts/python -m pytest tests/test_observatory.py -q`.
Browser checks after building: `.venv/Scripts/python tests/browser/observatory_smoke.py`.
The browser script runs an isolated changing fixture, verifies SSE, reconnection,
composition/mode/pause/immersion persistence, note persistence, home consistency,
camera movement and pause, classified runtime logs, history versus live activity,
hidden-page resume, and both compositions at ten viewport sizes.
It checks that the complete ring, its six labels and action buttons remain
reachable, including with a desktop title bar, long notes and large counters.
The ring occupies the main stage with a subtle note at its edge; narrow/short
windows place the satellites and note below the main ring and scroll as a single
document. Laptop windows keep all three satellites next to the main ring in the
first view; their size follows the workspace height. Compact workspaces provide
a note dialog instead of reserving space above the satellites. Browser checks
assert satellite bounds before any scroll, including desktop title-bar spacing. Reading
details and the portrait editor are teleported to the viewport so scroll
containers cannot clip them.
The script saves desktop/mobile/disconnected screenshots without touching live data.
