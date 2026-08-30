/**
 * 测试页面 - 用于调试
 */

export default function TestPage() {
  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: '#667eea' }}>🧪 测试页面</h1>
      <p>如果你能看到这个页面，说明 React 路由正常工作</p>
      <div style={{ marginTop: '20px', padding: '15px', background: '#f0f0f0', borderRadius: '8px' }}>
        <h3>状态：</h3>
        <ul>
          <li>✅ TestPage 组件渲染正常</li>
          <li>✅ 路由配置正确</li>
        </ul>
      </div>
    </div>
  );
}
