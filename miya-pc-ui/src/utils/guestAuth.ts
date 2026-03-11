/**
 * 访客模式 - 临时测试使用
 * 允许无需登录直接访问所有页面
 */

import { useAuthStore } from '../store/webStore';

interface GuestUser {
  id: string;
  username: string;
  email: string;
  level: number;
}

export function enableGuestMode() {
  const { login } = useAuthStore.getState();

  const guestUser: GuestUser = {
    id: 'guest-user',
    username: '访客',
    email: 'guest@miya.local',
    level: 1,
  };

  const guestToken = 'guest-token-' + Date.now();

  login(guestUser as any, guestToken);
  console.log('✅ 访客模式已启用');
}

// 在控制台中调用 enableGuestMode() 即可启用访客模式
// 或者直接在浏览器控制台执行:
// window.enableGuestMode = () => { ... }
