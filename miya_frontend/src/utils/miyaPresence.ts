export interface MiyaPresence {
  persona: string | null
  emotion: string | null
  activity: number | null
  memoryCount: number | null
  platformCount: number | null
}

function record(value: unknown): Record<string, any> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function count(...values: unknown[]): number | null {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value) && value >= 0)
      return Math.round(value)
  }
  return null
}

// ApiClient converts response keys to camelCase; also accept native backend payloads.
export function normalizeMiyaPresence(statusValue: unknown, personaValue?: unknown): MiyaPresence {
  const status = record(statusValue)
  const persona = record(personaValue)
  const emotion = record(status.emotion)
  const memory = record(status.memoryStats ?? status.memory_stats)
  const platforms = record(status.platformInfo ?? status.platform_info)
  const emotions = Array.isArray(emotion.emotions) ? emotion.emotions.map(record) : []
  const dominant = [...emotions].sort((a, b) => (count(b.intensity) ?? 0) - (count(a.intensity) ?? 0))[0]
  const activity = count(record(persona.soul).activity, emotion.intensity, dominant?.intensity)
  const tide = count(memory.tideCount, memory.tide_count)
  const longterm = count(memory.longtermCount, memory.longterm_count)
  return {
    persona: text(record(persona.persona).name) ?? text(record(persona.persona).id),
    emotion: text(emotion.emotionName ?? emotion.emotion_name) ?? text(emotion.dominant) ?? text(dominant?.name),
    activity: activity === null ? null : Math.min(100, activity),
    memoryCount: count(memory.total, memory.nodeCount, memory.totalNodes, memory.total_nodes)
      ?? (tide !== null || longterm !== null ? (tide ?? 0) + (longterm ?? 0) : null),
    platformCount: count(platforms.enabledCount, platforms.enabled_count),
  }
}
