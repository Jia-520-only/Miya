export interface PlatformInfo {
  platform_id: string
  platform_name: string
  status: string
  last_online: string | null
  last_offline: string | null
  latency_ms: number
  message_count: number
  message_in_count: number
  message_out_count: number
  uptime_seconds: number
  last_heartbeat: string | null
  heartbeat_interval: number
  consecutive_health_failures: number
  last_message_received: string | null
}

export const PLATFORM_COLORS: Record<string, string> = {
  qqofficial: '#12B7F5',
  aiocqhttp: '#12B7F5',
  telegram: '#26A5E4',
  discord: '#5865F2',
  slack: '#4A154B',
  line: '#06C755',
  lark: '#3370FF',
  dingtalk: '#0089FF',
  wecom: '#07C160',
  weixin_oc: '#07C160',
  weixin_official_account: '#07C160',
  weixin_ilink: '#07C160',
  kook: '#F8D64E',
  mattermost: '#0058CC',
  misskey: '#86B300',
  satori: '#FF6B9D',
  mobile: '#FF6B35',
  desktop: '#00ADB5',
  terminal: '#7C8B9E',
  wecom_ai_bot: '#07C160',
  qqofficial_webhook: '#12B7F5',
}

export function getPlatformColor(platformId: string): string {
  return PLATFORM_COLORS[platformId] || '#6B7280'
}

export function getPlatformLabel(platformId: string, platformName?: string): string {
  if (platformName) return platformName
  const labels: Record<string, string> = {
    qqofficial: 'QQ',
    aiocqhttp: 'QQ',
    qqofficial_webhook: 'QQ',
    telegram: 'TG',
    discord: 'DC',
    slack: 'Slack',
    line: 'LINE',
    lark: '飞书',
    dingtalk: '钉钉',
    wecom: '企微',
    wecom_ai_bot: '企微AI',
    weixin_oc: '微信',
    weixin_official_account: '公众号',
    weixin_ilink: '微信',
    kook: 'KOOK',
    mattermost: 'MM',
    misskey: 'Misskey',
    satori: 'Satori',
    mobile: '手机端',
    desktop: '桌面端',
    terminal: '终端',
    generic: '通用',
  }
  return labels[platformId] || platformId
}
