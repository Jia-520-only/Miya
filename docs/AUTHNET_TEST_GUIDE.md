# AuthNet 鉴权系统测试指南

## 快速开始

### 1. 运行完整测试套件
```bash
cd d:\AI_MIYA_Facyory\MIYA\Miya
python tests/test_authnet.py
```

### 2. 手动测试权限检查
```python
from webnet.AuthNet.permission_core import PermissionCore

perm_core = PermissionCore()
result = perm_core.check_permission('system_admin', 'tool.web_search')
print(f"有权限: {result}")
```

### 3. 测试用户创建
```python
from webnet.AuthNet.user_mapper import UserMapper

mapper = UserMapper()
user_id = mapper.ensure_user_exists('qq', '12345', '用户名', ['User'])
print(f"用户ID: {user_id}")
```

## 测试场景

### 场景1: 系统管理员权限
- 用户ID: `system_admin`
- 预期: 拥有所有权限（包括通配符 *）

### 场景2: 普通用户权限
- 用户ID: 自动格式化为 `platform_id`（如 qq_12345）
- 预期: 拥有基础权限（web_search, data_analyze等）

### 场景3: 跨平台用户
- QQ用户: `qq_12345`
- Web用户: `web_user001`
- 桌面用户: `desktop_local_user`
- 终端用户: `terminal_cli_user`

## 集成测试

### 通过弥娅系统测试

1. 启动弥娅系统
2. 从任意平台（QQ、Web、桌面）发送消息
3. DecisionHub会自动检查权限：
   - 用户ID格式化为 `platform_id`
   - 检查 `api.access` 基础权限
   - 无权限时返回提示信息

### 测试工具调用

```python
import asyncio
from webnet.AuthNet import AuthSubnet

async def test_tools():
    auth = AuthSubnet()

    # 检查权限
    result = await auth.execute_tool(
        'check_permission',
        {'user_id': 'qq_12345', 'permission': 'tool.web_search'},
        user_id=123
    )

    # 列出权限组
    result = await auth.execute_tool(
        'list_groups',
        {},
        user_id=123
    )

    print(result)

asyncio.run(test_tools())
```

## 权限组

| 组名 | 描述 | 权限范围 |
|------|------|----------|
| SuperAdmin | 超级管理员 | * (所有权限) |
| Admin | 管理员 | system.*, user.*, tool.*, agent.*, api.* |
| Developer | 开发者 | 代码生成、文件访问、GitHub推送、任务执行 |
| User | 普通用户 | 搜索、分析、图表、读取、基础访问 |
| Guest | 访客 | 搜索、读取 |

## 权限节点示例

- `tool.web_search` - 网页搜索
- `tool.terminal_command` - 终端命令执行
- `api.access` - 基础API访问
- `agent.task.execute` - Agent任务执行
- `system.config.*` - 系统配置（通配符）

## 验证清单

- [ ] AuthNet初始化成功
- [ ] 7个鉴权工具正常工作
- [ ] 权限检查算法正确
- [ ] 用户ID跨平台映射正常
- [ ] 权限组继承正常
- [ ] 与DecisionHub集成正常
- [ ] 数据文件UTF-8编码正确

## 故障排查

### 问题: 编码错误
```
UnicodeDecodeError: 'utf-8' codec can't decode byte
```
解决: 删除 `data/auth/users.json` 和 `data/auth/groups.json`，重新初始化

### 问题: 权限检查失败
解决: 检查用户ID格式是否为 `platform_id`

### 问题: 用户没有权限
解决: 检查用户所属权限组，或直接授予权限

## 下一步

测试通过后，可以：
1. 在ToolNet中添加工具级权限检查
2. 在Web API中添加权限验证中间件
3. 创建用户管理界面
4. 实现审计日志功能
