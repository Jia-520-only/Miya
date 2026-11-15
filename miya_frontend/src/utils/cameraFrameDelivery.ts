const NORMAL_INTERVAL_MS = 15_000
const RETRY_BASE_MS = 3_000
const RETRY_MAX_MS = 30_000

/** Per-source delivery cadence; one failing camera must not delay the others. */
export class CameraFrameDeliverySchedule {
  private readonly nextAt = new Map<string, number>()
  private readonly failures = new Map<string, number>()

  isDue(sourceId: string, now = Date.now()) {
    return now >= (this.nextAt.get(sourceId) || 0)
  }

  delivered(sourceId: string, now = Date.now()) {
    this.failures.delete(sourceId)
    this.nextAt.set(sourceId, now + NORMAL_INTERVAL_MS)
  }

  failed(sourceId: string, now = Date.now()) {
    const failures = (this.failures.get(sourceId) || 0) + 1
    this.failures.set(sourceId, failures)
    this.nextAt.set(sourceId, now + Math.min(RETRY_MAX_MS, RETRY_BASE_MS * 2 ** (failures - 1)))
  }

  reset() {
    this.failures.clear()
    this.nextAt.clear()
  }
}
