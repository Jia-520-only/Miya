/**
 * Live2D rig parameters measured from a real face.
 *
 * The conversion from geometry to parameters deliberately lives in the backend
 * (`mcpserver/screen_vision/local_camera.rig_parameters`), next to the
 * measurement and its thresholds, so there is exactly one copy of it and it is
 * covered by the Python test suite. This layer only applies what it is handed.
 *
 * Only parameters that can be justified by the five available landmarks are
 * produced. Eyebrows and eyelids are absent because there are no landmarks for
 * them - inventing them would reintroduce the fake confidence the local layer
 * exists to avoid.
 */
export interface RigCommand {
  /** Parameter id to additive offset. */
  params: Record<string, number>
  /** Face centre in normalized frame coords, for look-at follow. */
  centerX: number
  centerY: number
}

/**
 * Read a rig command out of one local-analysis result.
 *
 * Returns `null` when the frame carried no measurable face, which lets the rig
 * blend back to its own idle behaviour instead of freezing on a stale face.
 */
export function rigCommandFromAnalysis(data: unknown): RigCommand | null {
  const observation = (data as { observations?: unknown[] } | null)?.observations?.[0] as
    | { rig?: unknown, face_signals?: unknown }
    | undefined
  if (!observation) return null

  const params = observation.rig
  if (!params || typeof params !== 'object') return null

  const signals = observation.face_signals as { center?: unknown } | undefined
  const center = Array.isArray(signals?.center) ? signals?.center as number[] : null

  const clean: Record<string, number> = {}
  for (const [key, value] of Object.entries(params as Record<string, unknown>)) {
    const numeric = Number(value)
    if (Number.isFinite(numeric)) clean[key] = numeric
  }
  if (!Object.keys(clean).length) return null

  return {
    params: clean,
    centerX: Number.isFinite(center?.[0]) ? Number(center?.[0]) : 0.5,
    centerY: Number.isFinite(center?.[1]) ? Number(center?.[1]) : 0.5,
  }
}
