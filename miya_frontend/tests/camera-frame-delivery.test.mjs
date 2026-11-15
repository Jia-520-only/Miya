/* eslint-disable test/no-import-node-test -- Uses the project's Node test runner. */
import assert from 'node:assert/strict'
import test from 'node:test'
import { CameraFrameDeliverySchedule } from '../src/utils/cameraFrameDelivery.ts'

test('delivery cadence is tracked independently for each camera', () => {
  const cadence = new CameraFrameDeliverySchedule()
  cadence.delivered('camera-a', 1_000)

  assert.equal(cadence.isDue('camera-a', 15_999), false)
  assert.equal(cadence.isDue('camera-a', 16_000), true)
  assert.equal(cadence.isDue('camera-b', 1_000), true)
})

test('failed delivery backs off per camera and success resets the retry state', () => {
  const cadence = new CameraFrameDeliverySchedule()
  cadence.failed('camera-a', 1_000)
  cadence.failed('camera-a', 4_000)

  assert.equal(cadence.isDue('camera-a', 9_999), false)
  assert.equal(cadence.isDue('camera-a', 10_000), true)
  assert.equal(cadence.isDue('camera-b', 1_000), true)

  cadence.delivered('camera-a', 10_000)
  cadence.failed('camera-a', 25_000)
  assert.equal(cadence.isDue('camera-a', 27_999), false)
  assert.equal(cadence.isDue('camera-a', 28_000), true)
})

test('reset makes every camera immediately eligible again', () => {
  const cadence = new CameraFrameDeliverySchedule()
  cadence.delivered('camera-a', 1_000)
  cadence.reset()

  assert.equal(cadence.isDue('camera-a', 1_001), true)
})
