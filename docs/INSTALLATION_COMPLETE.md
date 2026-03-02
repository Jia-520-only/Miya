# MIYA Installation Complete

## Status: Ready to Launch

### Installation Summary

All dependencies have been successfully installed and MIYA is ready to use.

### Environment Details

- **Python Version**: 3.11.9
- **Virtual Environment**: `venv/`
- **Package Source**: PyPI (via proxy)
- **Installation Date**: 2026-02-28

### Installed Packages (140+ total)

#### Core Framework
- fastapi 0.134.0
- uvicorn 0.41.0
- websockets 16.0

#### Database Clients
- redis 7.2.1
- neo4j 6.1.0
- pymilvus 2.6.9
- chromadb 1.5.2

#### AI & NLP
- tiktoken 0.12.0
- numpy 2.4.2
- numba 0.64.0

#### Document Processing
- pymupdf 1.27.1 (PDF)
- python-docx 1.2.0 (Word)
- python-pptx 1.0.2 (PowerPoint)
- openpyxl 3.1.5 (Excel)
- markdown 3.10.2

#### Utilities
- httpx 0.28.1
- aiofiles 25.1.0
- APScheduler 3.11.2
- rich 14.3.3
- psutil 7.2.2

### Quick Start Guide

#### Step 1: Configure Environment

```batch
notepad config\.env
```

**Minimum Required Configuration:**

```env
# QQ Bot Configuration
QQ_BOT_QQ=your_bot_qq_number
QQ_SUPERADMIN_QQ=your_admin_qq_number
QQ_ONEBOT_WS_URL=ws://localhost:3001
```

**Optional Full Configuration:**

```env
# Database Services
REDIS_HOST=localhost
MILVUS_HOST=localhost
NEO4J_URI=bolt://localhost:7687

# API Configuration
API_ENABLED=true
API_PORT=8000

# WebUI Configuration
WEBUI_ENABLED=true
WEBUI_PORT=8080

# Personality Configuration
PERSONALITY_WARMTH=0.8
PERSONALITY_LOGIC=0.7
PERSONALITY_CREATIVITY=0.6
PERSONALITY_EMPATHY=0.75
PERSONALITY_RESILIENCE=0.7
```

#### Step 2: Test Environment

```batch
test_environment.bat
```

This will verify:
- Python availability
- Virtual environment
- Core packages installation
- Configuration file

#### Step 3: Launch MIYA

```batch
start.bat
```

**Available Launch Modes:**

| Mode | Description |
|------|-------------|
| 1 | Main Program (Full Features) |
| 2 | QQ Bot Only |
| 3 | PC UI Only |
| 4 | Runtime API Server |
| 5 | Health Check |
| 6 | System Status |

#### Step 4: Access Management Panel

**Option 1: Direct File**
```
Open: pc_ui/manager.html
```

**Option 2: Local Server**
```batch
cd pc_ui
python -m http.server 8080
# Then visit: http://localhost:8080/manager.html
```

**Option 3: Runtime API**
```
Visit: http://localhost:8000
Docs:  http://localhost:8000/docs
```

### Management Panel Features

- 📊 System Status Monitoring
- 🎮 Endpoint Management (QQ/PC/Web)
- 🤖 Agent Management
- 🧠 Memory System Query
- 📈 Queue Statistics
- ⚙️ Configuration Management

### Troubleshooting

#### Issue: Redis Connection Failed

**Solution:**
1. Install Redis: https://redis.io/download
2. Start Redis server
3. Verify `REDIS_HOST` in `config/.env`

#### Issue: QQ Bot Cannot Connect

**Solution:**
1. Install OneBot: https://github.com/Mrs4s/go-cqhttp
2. Start OneBot server
3. Verify `QQ_ONEBOT_WS_URL` in `config/.env`

#### Issue: API Not Accessible

**Solution:**
1. Check port 8000 is not occupied
2. Check firewall settings
3. Verify `API_ENABLED=true` in `config/.env`

#### Issue: Import Errors

**Solution:**
```batch
# Reinstall dependencies
venv\Scripts\activate
pip install -r requirements.txt
```

### Documentation

- **Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **System Architecture**: `MIYA_SYSTEM_STRUCTURE_ANALYSIS.md`
- **PC Panel Usage**: `pc_ui/MANAGER_README.md`
- **Integration Reports**:
  - `COMPLETE_AGENT_INTEGRATION_REPORT.md`
  - `COMPLETE_FUSION_VERIFICATION_REPORT.md`
  - `UNDEFINED_COMPLETE_INTEGRATION_REPORT.md`

### System Capabilities

MIYA now supports:

- ✅ Five-layer cognitive architecture
- ✅ Spider-web distributed design
- ✅ Memory-emotion coupling
- ✅ Personality constant mechanism
- ✅ Multi-endpoint support (QQ/PC/Web/IoT)
- ✅ Skills plugin system
- ✅ Runtime API management
- ✅ PC management panel
- ✅ Three-layer memory system
- ✅ Queue management (station-train model)
- ✅ Configuration hot-reload

### Architecture Overview

```
MIYA/
├── core/           # Core layer (kernel)
├── hub/            # Hub layer (coordination)
├── mlink/          # M-Link layer (routing)
├── webnet/         # WebNet layer (subnetworks)
├── perceive/       # Perception layer
├── evolve/         # Evolution layer
├── memory/         # Memory layer
├── storage/        # Storage layer
├── detect/         # Detection layer
├── trust/          # Trust layer
├── plugin/         # Plugin layer (Skills)
├── run/            # Entry points
└── pc_ui/          # PC management panel
```

### Next Steps

1. ✅ Configure `config/.env` with your settings
2. ✅ Run `test_environment.bat` to verify setup
3. ✅ Launch MIYA with `start.bat`
4. ✅ Open management panel `pc_ui/manager.html`
5. ✅ Explore features and customize configuration

### Support

For issues or questions:
1. Check `DEPLOYMENT_GUIDE.md` for troubleshooting
2. Review logs in `logs/` directory
3. Verify all services are running (Redis, Milvus, Neo4j)

---

## MIYA is Ready! 🚀

Your AI agent system is fully installed and configured.

**Start your journey:**
```batch
start.bat
```

Thank you for choosing MIYA! ✨
