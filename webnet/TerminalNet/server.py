"""
Web终端管理API - 弥娅V4.0

提供Web界面管理终端
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
import asyncio
import json

from core.local_terminal_manager import LocalTerminalManager
from core.ssh_terminal_manager import SSHTerminalManager
from core.terminal_orchestrator import IntelligentTerminalOrchestrator
from core.session_persistence import SessionPersistence
from core.scenario_templates import ScenarioLibrary
from core.workflow_engine import WorkflowEngine, Workflow

app = FastAPI(title="弥娅V4.0 - Web终端管理系统")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化管理器
terminal_manager = LocalTerminalManager()
ssh_manager = SSHTerminalManager()
orchestrator = IntelligentTerminalOrchestrator()
session_persistence = SessionPersistence()
scenario_library = ScenarioLibrary()
workflow_engine = WorkflowEngine(terminal_manager)

@app.get("/")
async def index():
    """主页"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>弥娅V4.0 - Web终端管理系统</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1e1e2e; color: #e0e0e0; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; padding: 30px 0; border-bottom: 1px solid #333; margin-bottom: 30px; }
        .header h1 { font-size: 2.5em; margin: 0; color: #00d4ff; }
        .header p { color: #888; margin-top: 10px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .panel { background: #252525; border-radius: 8px; padding: 20px; border: 1px solid #333; }
        .panel h2 { margin-top: 0; color: #00d4ff; border-bottom: 1px solid #333; padding-bottom: 10px; }
        .terminal-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }
        .terminal-card { background: #2d2d2d; border-radius: 6px; padding: 15px; border: 1px solid #444; transition: all 0.3s; }
        .terminal-card:hover { border-color: #00d4ff; transform: translateY(-2px); }
        .terminal-card.active { border-color: #00d4ff; box-shadow: 0 0 10px rgba(0, 212, 255, 0.2); }
        .terminal-card h3 { margin: 0 0 10px 0; font-size: 1.2em; }
        .terminal-info { color: #888; font-size: 0.9em; }
        .terminal-status { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; margin-top: 10px; }
        .status-idle { background: #4CAF50; }
        .status-executing { background: #FF9800; }
        .status-error { background: #f44336; }
        .status-closed { background: #9e9e9e; }
        .btn { padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 1em; transition: all 0.3s; }
        .btn-primary { background: #00d4ff; color: white; }
        .btn-primary:hover { background: #00b8e6; }
        .btn-success { background: #4CAF50; color: white; }
        .btn-danger { background: #f44336; color: white; }
        .command-input { width: 100%; padding: 12px; background: #1e1e2e; border: 1px solid #444; border-radius: 5px; color: white; font-family: monospace; }
        .output-area { width: 100%; height: 300px; padding: 15px; background: #1a1a1a; border: 1px solid #333; border-radius: 5px; color: #00ff00; font-family: monospace; overflow-y: auto; white-space: pre-wrap; }
        .scenario-card { background: #2d2d2d; border-radius: 6px; padding: 15px; margin-bottom: 15px; border: 1px solid #444; }
        .scenario-card:hover { border-color: #00d4ff; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>弥娅V4.0</h1>
            <p>多终端智能管理系统</p>
        </div>
        
        <div class="grid">
            <div class="panel">
                <h2>📱 终端列表</h2>
                <div id="terminalList" class="terminal-list">
                    <p>加载中...</p>
                </div>
                <button class="btn btn-primary" onclick="createTerminal()" style="margin-top: 15px;">+ 新建终端</button>
            </div>
            
            <div class="panel">
                <h2>💬 命令执行</h2>
                <input type="text" id="commandInput" class="command-input" placeholder="输入命令..." onkeypress="if(event.key === 'Enter') executeCommand();">
                <button class="btn btn-primary" onclick="executeCommand()" style="margin-top: 10px;">执行命令</button>
                <div id="outputArea" class="output-area" style="margin-top: 15px;">
                    <p style="color: #888;">命令输出将显示在这里...</p>
                </div>
            </div>
        </div>
        
        <div class="panel" style="margin-top: 20px;">
            <h2>📋 场景模板</h2>
            <div id="scenarioList">
                <p>加载中...</p>
            </div>
        </div>
    </div>
    
    <script>
        async function loadTerminals() {{
            const response = await fetch('/api/terminals');
            const data = await response.json();
            
            const container = document.getElementById('terminalList');
            container.innerHTML = '';
            
            data.forEach(term => {{
                const statusClass = term.is_active ? 'active' : '';
                const statusBadge = `<span class="terminal-status status-${{term.status}}">${{term.status}}</span>`;
                
                container.innerHTML += `
                    <div class="terminal-card ${{statusClass}}" onclick="switchTerminal('${{term.id}}')">
                        <h3>${{term.name}}</h3>
                        <div class="terminal-info">
                            <p>类型: ${{term.type}}</p>
                            <p>目录: ${{term.directory}}</p>
                            ${{statusBadge}}
                        </div>
                    </div>
                `;
            }});
        }}
        
        async function loadScenarios() {{
            const response = await fetch('/api/scenarios');
            const data = await response.json();
            
            const container = document.getElementById('scenarioList');
            container.innerHTML = '';
            
            data.forEach(scenario => {{
                container.innerHTML += `
                    <div class="scenario-card" onclick="applyScenario('${{scenario.id}}')">
                        <h3>${{scenario.name}}</h3>
                        <p style="color: #888; margin: 5px 0;">${{scenario.description}}</p>
                        <button class="btn btn-success" style="margin-top: 10px; width: 100%;">应用场景</button>
                    </div>
                `;
            }});
        }}
        
        async function createTerminal() {{
            const name = prompt('输入终端名称:', '新终端');
            if (!name) return;
            
            await fetch('/api/terminals', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ name: name, type: 'cmd' }})
            }});
            
            loadTerminals();
        }}
        
        async function switchTerminal(id) {{
            await fetch(`/api/terminals/${{id}}/switch`, {{ method: 'POST' }});
            loadTerminals();
        }}
        
        async function executeCommand() {{
            const command = document.getElementById('commandInput').value;
            if (!command.trim()) return;
            
            const outputArea = document.getElementById('outputArea');
            outputArea.innerHTML = '<p style="color: #00d4ff;">执行中...</p>';
            
            const response = await fetch('/api/execute', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ command: command }})
            }});
            
            const data = await response.json();
            
            if (data.success) {{
                outputArea.innerHTML = `<p style="color: #00ff00;">${{data.output}}</p>`;
            }} else {{
                outputArea.innerHTML = `<p style="color: #ff0000;">错误: ${{data.error}}</p>`;
            }}
            
            loadTerminals();
        }}
        
        async function applyScenario(id) {{
            const response = await fetch(`/api/scenarios/${{id}}/apply`);
            const data = await response.json();
            
            if (data.success) {{
                alert('场景应用成功！');
                loadTerminals();
            }} else {{
                alert('场景应用失败: ' + (data.error || '未知错误'));
            }}
        }}
        
        // 初始化加载
        loadTerminals();
        loadScenarios();
        
        // 每3秒刷新终端状态
        setInterval(loadTerminals, 3000);
    </script>
</body>
</html>
    """)

# API端点

@app.get("/api/terminals")
async def list_terminals():
    """列出所有终端"""
    status = terminal_manager.get_all_status()
    return JSONResponse(content=status)

@app.post("/api/terminals")
async def create_terminal(request: dict):
    """创建新终端"""
    from core.terminal_types import TerminalType
    
    name = request.get('name', '新终端')
    term_type = TerminalType.from_string(request.get('type', 'cmd'))
    
    session_id = await terminal_manager.create_terminal(name, term_type)
    
    return JSONResponse(content={"success": True, "session_id": session_id})

@app.post("/api/terminals/{session_id}/switch")
async def switch_terminal(session_id: str):
    """切换终端"""
    await terminal_manager.switch_session(session_id)
    return JSONResponse(content={"success": True})

@app.delete("/api/terminals/{session_id}")
async def close_terminal(session_id: str):
    """关闭终端"""
    await terminal_manager.close_session(session_id)
    return JSONResponse(content={"success": True})

@app.post("/api/execute")
async def execute_command(request: dict):
    """执行命令"""
    command = request.get('command', '')
    session_id = terminal_manager.active_session_id
    
    if not session_id:
        return JSONResponse(content={"success": False, "error": "没有活动终端"})
    
    result = await terminal_manager.execute_command(session_id, command)
    
    return JSONResponse(content=result.to_dict())

@app.post("/api/execute/parallel")
async def execute_parallel(request: dict):
    """并行执行命令"""
    commands = request.get('commands', {})
    results = await terminal_manager.execute_parallel(commands)
    
    return JSONResponse(content={"success": True, "results": {k: v.to_dict() for k, v in results.items()}})

@app.get("/api/scenarios")
async def list_scenarios():
    """列出场景"""
    scenarios = scenario_library.list_scenarios()
    return JSONResponse(content=scenarios)

@app.post("/api/scenarios/{scenario_id}/apply")
async def apply_scenario(scenario_id: str):
    """应用场景"""
    result = await scenario_library.apply_scenario(scenario_id, terminal_manager)
    return JSONResponse(content=result)

@app.get("/api/status")
async def get_system_status():
    """获取系统状态"""
    return JSONResponse(content={
        "terminals": len(terminal_manager.sessions),
        "active_terminal": terminal_manager.active_session_id,
        "scenarios": len(scenario_library.scenarios)
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
