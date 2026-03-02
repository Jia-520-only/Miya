// 弥娅PC端前端应用
class MiyaApp {
    constructor() {
        this.ws = null;
        this.currentSession = 'default';
        this.currentAgent = 'miya_default';
        this.messages = [];
        this.agents = [];
        this.sessions = [];
        this.groups = [];
        this.notes = [];
        
        this.init();
    }
    
    async init() {
        try {
            // 连接WebSocket
            await this.connectWebSocket();
            
            // 加载初始数据
            await this.loadInitialData();
            
            // 绑定事件
            this.bindEvents();
            
            // 渲染界面
            this.renderAgents();
            this.renderSessions();
            this.renderNotes();
            
            console.log('弥娅应用初始化完成');
        } catch (error) {
            console.error('初始化失败:', error);
            this.showError('连接弥娅服务器失败，请检查服务是否启动');
        }
    }
    
    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket连接成功');
                resolve();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket错误:', error);
                reject(error);
            };
            
            this.ws.onmessage = (event) => {
                this.handleMessage(JSON.parse(event.data));
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket连接关闭');
                // 尝试重连
                setTimeout(() => this.connectWebSocket(), 3000);
            };
        });
    }
    
    async loadInitialData() {
        // 加载状态
        const stateRes = await fetch('/api/state');
        this.agents = Object.values((await stateRes.json()).agents || {});
        this.sessions = Object.values((await stateRes.json()).sessions || {});
        
        // 如果有默认agent，设置当前agent
        if (this.agents.length > 0) {
            this.currentAgent = this.agents[0].id;
        }
    }
    
    bindEvents() {
        // 标签切换
        document.querySelectorAll('.sidebar-item').forEach(item => {
            item.addEventListener('click', () => {
                const tab = item.dataset.tab;
                this.switchTab(tab);
            });
        });
        
        // 输入框事件
        const input = document.getElementById('user-input');
        input.addEventListener('input', () => {
            this.updateSendButton();
            this.autoResizeTextarea(input);
        });
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // 发送按钮
        document.getElementById('send-btn').addEventListener('click', () => {
            this.sendMessage();
        });
        
        // 搜索笔记
        document.getElementById('note-search').addEventListener('input', (e) => {
            this.searchNotes(e.target.value);
        });
        
        // 创建笔记
        document.getElementById('create-note-btn').addEventListener('click', () => {
            this.showCreateNoteDialog();
        });
        
        // 创建群聊
        document.getElementById('create-group-btn').addEventListener('click', () => {
            this.showCreateGroupDialog();
        });
    }
    
    switchTab(tabName) {
        // 更新侧边栏
        document.querySelectorAll('.sidebar-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.tab === tabName) {
                item.classList.add('active');
            }
        });
        
        // 更新内容区
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`).classList.add('active');
    }
    
    updateSendButton() {
        const input = document.getElementById('user-input');
        const btn = document.getElementById('send-btn');
        btn.disabled = input.value.trim() === '';
    }
    
    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }
    
    async sendMessage() {
        const input = document.getElementById('user-input');
        const message = input.value.trim();
        
        if (!message) return;
        
        // 添加用户消息到界面
        this.addMessageToUI({
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        });
        
        // 清空输入框
        input.value = '';
        input.style.height = 'auto';
        this.updateSendButton();
        
        // 发送到服务器
        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    session_id: this.currentSession,
                    agent_id: this.currentAgent
                })
            });
            
            const data = await res.json();
            
            if (data.error) {
                this.showError(data.error);
            } else {
                // 添加AI回复到界面
                this.addMessageToUI({
                    role: 'assistant',
                    content: data.response,
                    timestamp: new Date().toISOString(),
                    agent_id: data.agent_id
                });
            }
        } catch (error) {
            console.error('发送消息失败:', error);
            this.showError('发送消息失败，请重试');
        }
    }
    
    addMessageToUI(message) {
        const container = document.getElementById('chat-messages');
        
        // 移除加载提示
        const loading = container.querySelector('.loading');
        if (loading) {
            loading.remove();
        }
        
        const messageEl = document.createElement('div');
        messageEl.className = `message ${message.role}`;
        
        const avatar = message.role === 'user' ? '你' : '弥娅';
        
        messageEl.innerHTML = `
            <div class="avatar">${avatar}</div>
            <div class="message-content">
                ${message.agent_id ? `<div class="message-sender">${this.getAgentName(message.agent_id)}</div>` : ''}
                <div class="message-text">${this.formatMessage(message.content)}</div>
                <div class="message-time">${this.formatTime(message.timestamp)}</div>
            </div>
        `;
        
        container.appendChild(messageEl);
        container.scrollTop = container.scrollHeight;
        
        // 滚动到底部
        container.scrollTop = container.scrollHeight;
    }
    
    formatMessage(content) {
        // 简单的markdown格式化
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }
    
    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    }
    
    getAgentName(agentId) {
        const agent = this.agents.find(a => a.id === agentId);
        return agent ? agent.name : agentId;
    }
    
    renderAgents() {
        const container = document.getElementById('agent-selector');
        container.innerHTML = '';
        
        this.agents.forEach(agent => {
            const card = document.createElement('div');
            card.className = `agent-card ${agent.id === this.currentAgent ? 'active' : ''}`;
            card.innerHTML = `
                <div class="agent-name">${agent.name}</div>
                <div class="agent-desc">${agent.description || '暂无描述'}</div>
            `;
            
            card.addEventListener('click', () => {
                this.switchAgent(agent.id);
            });
            
            container.appendChild(card);
        });
    }
    
    async switchAgent(agentId) {
        try {
            const res = await fetch('/api/agent/switch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ agent_id: agentId })
            });
            
            const data = await res.json();
            
            if (data.success) {
                this.currentAgent = agentId;
                this.renderAgents();
                
                // 显示切换提示
                this.showNotification(`已切换到 ${this.getAgentName(agentId)}`);
            } else {
                this.showError(data.error);
            }
        } catch (error) {
            console.error('切换Agent失败:', error);
            this.showError('切换Agent失败');
        }
    }
    
    renderSessions() {
        const container = document.getElementById('sessions-container');
        container.innerHTML = '';
        
        this.sessions.forEach(session => {
            const sessionEl = document.createElement('div');
            sessionEl.className = `session-item ${session.id === this.currentSession ? 'active' : ''}`;
            
            const lastMessage = session.history[session.history.length - 1];
            const preview = lastMessage ? lastMessage.content : '暂无消息';
            
            sessionEl.innerHTML = `
                <div class="session-title">${session.id}</div>
                <div class="session-preview">${preview}</div>
            `;
            
            sessionEl.addEventListener('click', () => {
                this.switchSession(session.id);
            });
            
            container.appendChild(sessionEl);
        });
    }
    
    switchSession(sessionId) {
        this.currentSession = sessionId;
        this.renderSessions();
        
        // 加载会话消息
        const session = this.sessions.find(s => s.id === sessionId);
        if (session) {
            const container = document.getElementById('chat-messages');
            container.innerHTML = '';
            
            session.history.forEach(msg => {
                this.addMessageToUI(msg);
            });
        }
    }
    
    renderNotes(notes = this.notes) {
        const container = document.getElementById('notes-container');
        container.innerHTML = '';
        
        notes.forEach(note => {
            const noteEl = document.createElement('div');
            noteEl.className = 'note-item';
            noteEl.innerHTML = `
                <div class="note-title">${note.title}</div>
                <div class="note-preview">${note.body}</div>
                <div class="note-tags">
                    ${(note.tags || []).map(tag => `<span class="tag">${tag}</span>`).join('')}
                </div>
            `;
            
            container.appendChild(noteEl);
        });
    }
    
    async searchNotes(query) {
        try {
            const res = await fetch(`/api/note/search?query=${encodeURIComponent(query)}`);
            const data = await res.json();
            
            if (data.results) {
                this.renderNotes(data.results);
            }
        } catch (error) {
            console.error('搜索笔记失败:', error);
        }
    }
    
    showCreateNoteDialog() {
        const title = prompt('笔记标题:');
        if (!title) return;
        
        const body = prompt('笔记内容:');
        if (!body) return;
        
        this.createNote({
            title,
            body,
            tags: [],
            category: '未分类'
        });
    }
    
    async createNote(note) {
        try {
            const res = await fetch('/api/note/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(note)
            });
            
            const data = await res.json();
            
            if (data.success) {
                this.notes.push(data.note);
                this.renderNotes();
                this.showNotification('笔记创建成功');
            } else {
                this.showError(data.error);
            }
        } catch (error) {
            console.error('创建笔记失败:', error);
            this.showError('创建笔记失败');
        }
    }
    
    showCreateGroupDialog() {
        const name = prompt('群聊名称:');
        if (!name) return;
        
        this.createGroup({
            name,
            agents: [this.currentAgent]
        });
    }
    
    async createGroup(group) {
        try {
            const res = await fetch('/api/group/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(group)
            });
            
            const data = await res.json();
            
            if (data.success) {
                this.groups.push(data.group);
                this.renderGroups();
                this.showNotification('群聊创建成功');
            } else {
                this.showError(data.error);
            }
        } catch (error) {
            console.error('创建群聊失败:', error);
            this.showError('创建群聊失败');
        }
    }
    
    renderGroups() {
        const container = document.getElementById('groups-container');
        container.innerHTML = '';
        
        this.groups.forEach(group => {
            const groupEl = document.createElement('div');
            groupEl.className = 'session-item';
            groupEl.innerHTML = `
                <div class="session-title">${group.name}</div>
                <div class="session-preview">${group.agents.length} 个Agent</div>
            `;
            
            container.appendChild(groupEl);
        });
    }
    
    handleMessage(data) {
        console.log('收到消息:', data);
        
        switch (data.type) {
            case 'connected':
                this.showNotification(data.message);
                break;
                
            case 'response':
                if (data.action === 'response') {
                    this.addMessageToUI({
                        role: 'assistant',
                        content: data.response,
                        timestamp: new Date().toISOString(),
                        agent_id: data.agent_id
                    });
                }
                break;
                
            default:
                console.log('未处理的消息类型:', data.type);
        }
    }
    
    showNotification(message) {
        // 简单的通知
        console.log('通知:', message);
        // TODO: 实现更好的通知UI
    }
    
    showError(message) {
        console.error('错误:', message);
        // TODO: 实现错误提示UI
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    window.miyaApp = new MiyaApp();
});
