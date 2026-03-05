/**
 * 弥娅 PC端统一管理面板 - JavaScript应用
 * 
 * 功能：
 * - 系统状态监控
 * - 交互端管理
 * - Agent管理
 * - 记忆系统查询
 * - 队列统计
 * - 配置管理
 */

// API配置
const API_CONFIG = {
    baseURL: 'http://localhost:8000',
    endpoints: {
        probe: '/api/probe',
        status: '/api/status',
        health: '/health',
        endpoints: '/api/endpoints',
        endpointStart: (id) => `/api/endpoints/${id}/start`,
        endpointStop: (id) => `/api/endpoints/${id}/stop`,
        agents: '/api/agents',
        agentsStats: '/api/agents/stats',
        cognitiveEvents: '/api/cognitive/events',
        cognitiveProfiles: '/api/cognitive/profiles',
        queueStats: '/api/queue/stats',
    },
    refreshInterval: 5000, // 5秒
};

// 应用状态
const appState = {
    connected: false,
    endpoints: [],
    agents: [],
    stats: {},
    lastUpdate: null,
    startTime: null,
};

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

/**
 * 初始化应用
 */
function initApp() {
    console.log('弥娅管理面板初始化...');
    
    // 初始化导航
    initNavigation();
    
    // 开始刷新循环
    startRefreshLoop();
    
    // 首次加载数据
    refreshAll();
    
    console.log('弥娅管理面板初始化完成');
}

/**
 * 初始化导航
 */
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.section');
    
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const sectionId = item.dataset.section;
            
            // 更新导航状态
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            // 显示对应section
            sections.forEach(section => {
                section.classList.remove('active');
                if (section.id === `section-${sectionId}`) {
                    section.classList.add('active');
                }
            });
        });
    });
    
    // 初始化记忆标签切换
    initMemoryTabs();
}

/**
 * 初始化记忆标签
 */
function initMemoryTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const memoryContent = document.getElementById('memoryContent');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const tab = btn.dataset.tab;
            if (tab === 'events') {
                loadMemoryEvents();
            } else if (tab === 'profiles') {
                loadMemoryProfiles();
            }
        });
    });
}

/**
 * 开始刷新循环
 */
function startRefreshLoop() {
    setInterval(() => {
        refreshAll();
    }, API_CONFIG.refreshInterval);
}

/**
 * 刷新所有数据
 */
async function refreshAll() {
    try {
        // 并发请求所有数据
        await Promise.all([
            checkConnection(),
            loadSystemStatus(),
            loadEndpoints(),
            loadAgents(),
            loadQueueStats(),
        ]);
        
        updateLastUpdateTime();
    } catch (error) {
        console.error('刷新数据失败:', error);
        showToast('刷新数据失败', 'error');
    }
}

/**
 * 检查连接
 */
async function checkConnection() {
    try {
        const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.probe}`);
        const data = await response.json();
        
        appState.connected = true;
        updateConnectionStatus(true);
        return true;
    } catch (error) {
        appState.connected = false;
        updateConnectionStatus(false);
        return false;
    }
}

/**
 * 更新连接状态
 */
function updateConnectionStatus(connected) {
    const statusIndicator = document.getElementById('systemStatus');
    const statusDot = statusIndicator.querySelector('.status-dot');
    const statusText = statusIndicator.querySelector('.status-text');
    
    if (connected) {
        statusDot.classList.remove('offline');
        statusDot.classList.add('online');
        statusText.textContent = '已连接';
    } else {
        statusDot.classList.remove('online');
        statusDot.classList.add('offline');
        statusText.textContent = '离线';
    }
}

/**
 * 加载系统状态
 */
async function loadSystemStatus() {
    try {
        const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.status}`);
        const data = await response.json();
        
        appState.stats = data;
        
        // 更新统计卡片
        document.getElementById('statEndpoints').textContent = data.endpoints_count || 0;
        document.getElementById('statAgents').textContent = data.agents_count || 0;
        document.getElementById('statTasks').textContent = data.queue_size || 0;
        
        // 更新系统信息
        document.getElementById('infoStatus').textContent = data.status || '--';
        document.getElementById('infoStartTime').textContent = data.start_time || '--';
        
        // 更新运行时间
        if (data.start_time) {
            const uptime = calculateUptime(data.start_time);
            document.getElementById('statUptime').textContent = uptime;
        }
        
    } catch (error) {
        console.error('加载系统状态失败:', error);
    }
}

/**
 * 计算运行时间
 */
function calculateUptime(startTime) {
    const start = new Date(startTime);
    const now = new Date();
    const diff = now - start;
    
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    if (days > 0) {
        return `${days}d ${hours}h`;
    } else if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else {
        return `${minutes}m`;
    }
}

/**
 * 加载交互端
 */
async function loadEndpoints() {
    try {
        const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.endpoints}`);
        const data = await response.json();
        
        appState.endpoints = data.endpoints || [];
        renderEndpoints();
    } catch (error) {
        console.error('加载交互端失败:', error);
    }
}

/**
 * 渲染交互端列表
 */
function renderEndpoints() {
    const container = document.getElementById('endpointsList');
    const searchTerm = document.getElementById('endpointSearch').value.toLowerCase();
    
    const filtered = appState.endpoints.filter(ep => 
        ep.name.toLowerCase().includes(searchTerm) ||
        ep.type.toLowerCase().includes(searchTerm)
    );
    
    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无交互端</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = filtered.map(endpoint => `
        <div class="endpoint-card" data-id="${endpoint.id}">
            <div class="endpoint-header">
                <div class="endpoint-name">
                    <span>${getEndpointIcon(endpoint.type)}</span>
                    <span>${endpoint.name}</span>
                </div>
                <span class="endpoint-type">${endpoint.type}</span>
            </div>
            <div class="endpoint-status">
                <span class="status-badge ${endpoint.status}">${getStatusText(endpoint.status)}</span>
            </div>
            <div class="endpoint-actions">
                <button class="btn btn-success" onclick="startEndpoint('${endpoint.id}')" 
                    ${endpoint.status === 'running' ? 'disabled' : ''}>
                    <span>▶</span> 启动
                </button>
                <button class="btn btn-danger" onclick="stopEndpoint('${endpoint.id}')" 
                    ${endpoint.status !== 'running' ? 'disabled' : ''}>
                    <span>⏹</span> 停止
                </button>
            </div>
            <div class="endpoint-info">
                <p>ID: ${endpoint.id}</p>
                ${endpoint.pid ? `<p>PID: ${endpoint.pid}</p>` : ''}
                ${endpoint.last_heartbeat ? `<p>心跳: ${formatTime(endpoint.last_heartbeat)}</p>` : ''}
            </div>
        </div>
    `).join('');
}

/**
 * 获取交互端图标
 */
function getEndpointIcon(type) {
    const icons = {
        'qq': '💬',
        'pc': '🖥️',
        'web': '🌐',
        'default': '🎮',
    };
    return icons[type] || icons['default'];
}

/**
 * 获取状态文本
 */
function getStatusText(status) {
    const texts = {
        'running': '运行中',
        'stopped': '已停止',
        'error': '错误',
    };
    return texts[status] || status;
}

/**
 * 启动交互端
 */
async function startEndpoint(id) {
    try {
        showToast('正在启动交互端...', 'info');
        
        const response = await fetch(
            `${API_CONFIG.baseURL}${API_CONFIG.endpoints.endpointStart(id)}`,
            { method: 'POST' }
        );
        
        if (response.ok) {
            showToast('交互端启动成功', 'success');
            await loadEndpoints();
        } else {
            showToast('交互端启动失败', 'error');
        }
    } catch (error) {
        console.error('启动交互端失败:', error);
        showToast('启动失败', 'error');
    }
}

/**
 * 停止交互端
 */
async function stopEndpoint(id) {
    try {
        showToast('正在停止交互端...', 'info');
        
        const response = await fetch(
            `${API_CONFIG.baseURL}${API_CONFIG.endpoints.endpointStop(id)}`,
            { method: 'POST' }
        );
        
        if (response.ok) {
            showToast('交互端停止成功', 'success');
            await loadEndpoints();
        } else {
            showToast('交互端停止失败', 'error');
        }
    } catch (error) {
        console.error('停止交互端失败:', error);
        showToast('停止失败', 'error');
    }
}

/**
 * 刷新交互端
 */
function refreshEndpoints() {
    loadEndpoints();
    showToast('交互端列表已刷新', 'success');
}

/**
 * 加载Agent列表
 */
async function loadAgents() {
    try {
        const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.agents}`);
        const data = await response.json();
        
        appState.agents = data.agents || [];
        renderAgents();
    } catch (error) {
        console.error('加载Agent失败:', error);
    }
}

/**
 * 渲染Agent列表
 */
function renderAgents() {
    const container = document.getElementById('agentsList');
    
    if (appState.agents.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无Agent</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = appState.agents.map(agent => `
        <div class="agent-card" data-id="${agent.id}">
            <div class="agent-header">
                <div class="agent-name">
                    <span>🤖</span>
                    <span>${agent.name}</span>
                </div>
                <span class="agent-type">${agent.type}</span>
            </div>
            <div class="agent-description">${agent.description || '暂无描述'}</div>
            <div class="agent-stats">
                <div class="agent-stat">
                    <span>状态</span>
                    <span class="status-badge ${agent.status}">${getStatusText(agent.status)}</span>
                </div>
                ${agent.stats ? Object.entries(agent.stats).map(([key, value]) => `
                    <div class="agent-stat">
                        <span>${key}</span>
                        <span>${value}</span>
                    </div>
                `).join('') : ''}
            </div>
        </div>
    `).join('');
}

/**
 * 刷新Agent
 */
function refreshAgents() {
    loadAgents();
    showToast('Agent列表已刷新', 'success');
}

/**
 * 显示Agent统计
 */
async function showAgentStats() {
    try {
        const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.agentsStats}`);
        const data = await response.json();
        
        const statsContainer = document.getElementById('agentsStats');
        statsContainer.innerHTML = Object.entries(data.stats || {}).map(([name, stats]) => `
            <div class="stat-card">
                <div class="stat-icon">📊</div>
                <div class="stat-content">
                    <div class="stat-value">${stats.count || 0}</div>
                    <div class="stat-label">${name}</div>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('加载Agent统计失败:', error);
        showToast('加载统计失败', 'error');
    }
}

/**
 * 搜索记忆事件
 */
async function searchMemory() {
    const query = document.getElementById('memorySearchInput').value;
    
    if (!query.trim()) {
        showToast('请输入搜索内容', 'warning');
        return;
    }
    
    try {
        const response = await fetch(
            `${API_CONFIG.baseURL}${API_CONFIG.endpoints.cognitiveEvents}?query=${encodeURIComponent(query)}&limit=20`
        );
        const data = await response.json();
        
        renderMemoryEvents(data.events || []);
    } catch (error) {
        console.error('搜索记忆失败:', error);
        showToast('搜索失败', 'error');
    }
}

/**
 * 加载记忆事件
 */
async function loadMemoryEvents() {
    const container = document.getElementById('memoryContent');
    container.innerHTML = '<p>请输入搜索内容搜索记忆事件</p>';
}

/**
 * 渲染记忆事件
 */
function renderMemoryEvents(events) {
    const container = document.getElementById('memoryContent');
    
    if (events.length === 0) {
        container.innerHTML = '<p>未找到相关记忆事件</p>';
        return;
    }
    
    container.innerHTML = events.map(event => `
        <div class="memory-event" style="padding: 12px; border-bottom: 1px solid var(--border-color);">
            <div style="font-weight: 600; margin-bottom: 8px;">${event.content || '无内容'}</div>
            <div style="font-size: 12px; color: var(--text-secondary);">
                时间: ${event.timestamp || '--'} | 
                用户: ${event.user_id || '--'} | 
                群: ${event.group_id || '--'}
            </div>
        </div>
    `).join('');
}

/**
 * 加载记忆侧写
 */
async function loadMemoryProfiles() {
    try {
        const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.cognitiveProfiles}`);
        const data = await response.json();
        
        const container = document.getElementById('memoryContent');
        
        if (!data.profiles || data.profiles.length === 0) {
            container.innerHTML = '<p>暂无侧写数据</p>';
            return;
        }
        
        container.innerHTML = data.profiles.map(profile => `
            <div class="profile-card" style="padding: 12px; border-bottom: 1px solid var(--border-color);">
                <div style="font-weight: 600; margin-bottom: 8px;">用户: ${profile.user_id || '未知'}</div>
                <div style="font-size: 14px; color: var(--text-secondary);">
                    ${profile.description || '暂无描述'}
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('加载侧写失败:', error);
    }
}

/**
 * 加载队列统计
 */
async function loadQueueStats() {
    try {
        const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.queueStats}`);
        const data = await response.json();
        
        renderQueueStats(data.stats || {});
    } catch (error) {
        console.error('加载队列统计失败:', error);
    }
}

/**
 * 渲染队列统计
 */
function renderQueueStats(stats) {
    const container = document.getElementById('queueStatsGrid');
    
    if (Object.keys(stats).length === 0) {
        container.innerHTML = '<p>暂无队列数据</p>';
        return;
    }
    
    container.innerHTML = Object.entries(stats).map(([model, stat]) => `
        <div class="queue-card">
            <h4>📊 ${model}</h4>
            <div class="queue-stats">
                <div class="queue-stat">
                    <span class="queue-stat-value">${stat.total_requests || 0}</span>
                    <span class="queue-stat-label">总请求</span>
                </div>
                <div class="queue-stat">
                    <span class="queue-stat-value">${stat.processed_requests || 0}</span>
                    <span class="queue-stat-label">已处理</span>
                </div>
                <div class="queue-stat">
                    <span class="queue-stat-value">${stat.failed_requests || 0}</span>
                    <span class="queue-stat-label">失败</span>
                </div>
                <div class="queue-stat">
                    <span class="queue-stat-value">${stat.success_rate ? stat.success_rate.toFixed(1) : 0}%</span>
                    <span class="queue-stat-label">成功率</span>
                </div>
            </div>
        </div>
    `).join('');
}

/**
 * 重载配置
 */
function reloadConfig() {
    showToast('配置重载功能待实现', 'info');
}

/**
 * 查看配置
 */
function showConfig() {
    showToast('配置查看功能待实现', 'info');
}

/**
 * 更新最后更新时间
 */
function updateLastUpdateTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    document.getElementById('lastUpdate').textContent = timeStr;
}

/**
 * 格式化时间戳
 */
function formatTime(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('zh-CN');
}

/**
 * 显示Toast提示
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️',
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    // 3秒后自动消失
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
