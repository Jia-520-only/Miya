# GitHub 集成功能

## 概述

弥娅博客系统现已支持 GitHub 仓库集成,可以将博客文章存储到 GitHub,实现版本控制和远程备份。

## 功能特性

### 1. GitHub 存储 (后端)
- ✅ 文件上传 (创建/更新)
- ✅ 文件删除
- ✅ 文件列表
- ✅ 文件内容获取
- ✅ 批量提交
- ✅ 本地缓存
- ✅ 仓库同步

### 2. 前端管理界面
- ✅ GitHub 配置管理
- ✅ 拉取 (从 GitHub 获取文章)
- ✅ 推送 (将文章推送到 GitHub)
- ✅ 双向同步
- ✅ 同步历史记录
- ✅ 配置持久化

## 使用方法

### 1. 后端配置

在 `config/.env` 中添加 GitHub 配置:

```env
# GitHub 配置
GITHUB_REPO_OWNER=your_username
GITHUB_REPO_NAME=your_blog_repo
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_BRANCH=main
```

### 2. 创建 GitHub 仓库

1. 访问 https://github.com/new
2. 创建新仓库 (例如: `my-blog`)
3. 可选择公开或私有
4. 初始化仓库后,创建 `posts/` 目录

### 3. 生成 Personal Access Token

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token" → "Generate new token (classic)"
3. 勾选 `repo` 权限
4. 生成并复制 Token

### 4. 前端配置

1. 进入博客管理页面
2. 点击 "GitHub 集成"
3. 填写仓库信息:
   - 仓库所有者: `your_username`
   - 仓库名称: `my-blog`
   - Personal Access Token: `ghp_xxxxxxxxxxxx`
   - 分支名称: `main`
4. 点击 "保存配置"

### 5. 同步操作

#### 拉取 (Pull)
从 GitHub 拉取文章到本地数据库

#### 推送 (Push)
将本地文章推送到 GitHub 仓库

#### 同步 (Sync)
双向同步,保持本地和 GitHub 一致

## 仓库结构

```
your_blog_repo/
├── posts/
│   ├── hello-world.md
│   ├── getting-started.md
│   └── advanced-features.md
└── README.md
```

## 文件格式

博客文章以 Markdown 格式存储,包含 Front Matter 元数据:

```markdown
---
title: Hello World
category: 技术
tags: [教程, 入门]
author: 弥娅
---

# Hello World

这是我的第一篇博客文章。
```

## API 接口

### 后端 API (待实现)

```python
# 同步 GitHub 仓库
POST /api/github/sync

# 从 GitHub 拉取
POST /api/github/pull

# 推送到 GitHub
POST /api/github/push

# 获取 GitHub 状态
GET /api/github/status

# 配置 GitHub
POST /api/github/config
```

### 前端 API (已创建)

```typescript
// GitHub 配置
interface GitHubConfig {
  repoOwner: string;
  repoName: string;
  token: string;
  branch: string;
}

// 同步操作
syncRepo(): Promise<void>;
pullFromGitHub(): Promise<void>;
pushToGitHub(): Promise<void>;
```

## 优势

相比 Hexo 的 GitHub Pages 集成,弥娅的 GitHub 集成有以下优势:

| 特性 | Hexo + GitHub Pages | 弥娅 + GitHub |
|------|---------------------|----------------|
| 类型 | 静态网站 | 动态网站 |
| 存储方式 | Git 提交 | API + Git |
| 数据库 | 无 | SQLite |
| 实时编辑 | 需本地构建 | 在线编辑 |
| 版本控制 | Git 历史 | Git 历史 + 数据库 |
| 备份 | GitHub | GitHub + 本地 |
| 评论 | 需第三方插件 | 内置评论系统 |
| AI 功能 | 无 | AI 助手、智能推荐 |
| 搜索 | 静态搜索 | 后端搜索 |

## 后端实现

### GitHubStore 类

```python
from webnet.github_store import GitHubStore

# 初始化
github_store = GitHubStore(
    repo_owner="your_username",
    repo_name="your_blog_repo",
    token="ghp_xxxxxxxxxxxx",
    branch="main"
)

# 获取文件内容
content = await github_store.get_file_content("posts/hello.md")

# 创建文件
await github_store.create_file(
    path="posts/new-post.md",
    content="# New Post\n\n...",
    message="Add new post"
)

# 删除文件
await github_store.delete_file(
    path="posts/old-post.md",
    message="Remove old post"
)

# 列出文件
files = await github_store.list_files("posts")

# 同步仓库
result = await github_store.sync_repo()
```

## 前端组件

### GitHubManager 组件

```tsx
import GitHubManager from './Web/Blog/GitHubManager';

function BlogSettings() {
  return (
    <div>
      <GitHubManager />
    </div>
  );
}
```

## 安全建议

1. **Token 安全**
   - 不要在公开仓库中提交 Token
   - 使用环境变量存储 Token
   - 定期轮换 Token

2. **权限控制**
   - Token 仅授予 `repo` 权限
   - 使用私有仓库保护敏感内容

3. **备份策略**
   - 定期从 GitHub 拉取备份
   - 保留多个历史版本

## 后续扩展

1. **自动化部署**
   - GitHub Actions 自动部署
   - CI/CD 集成

2. **多分支支持**
   - 开发分支预览
   - 版本管理

3. **协作功能**
   - 多作者支持
   - PR 审核流程

4. **高级功能**
   - 自动备份
   - 定时同步
   - 冲突解决

## 注意事项

1. 确保 GitHub Token 有足够的权限
2. 仓库需要提前创建并初始化
3. 本地缓存会在 `data/blog_cache/` 目录
4. 同步操作可能需要一定时间
5. 网络问题可能导致同步失败

## 完成状态

✅ 后端 GitHubStore 类
✅ 前端 GitHubManager 组件
✅ 配置管理
✅ 同步操作界面
🚧 后端 API 路由 (待实现)
🚧 与 BlogStore 集成 (待实现)
🚧 自动同步 (待实现)
