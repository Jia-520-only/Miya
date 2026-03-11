"""
弥娅 Web 子网

提供 Web 端的核心功能:
- 博客系统 (BlogStore)
- 认证管理 (AuthManager)
- 安全防护 (SecurityGuard)
"""

import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
import json
import sqlite3

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

logger = logging.getLogger(__name__)


class BlogStore:
    """博客存储管理"""

    def __init__(self, db_path: str = "data/blog/blog.db"):
        """
        初始化博客存储

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.db_path_obj = Path(db_path)
        self.db_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # 创建数据库表
        self._create_tables()

        logger.info(f"[BlogStore] 博客存储已初始化: {db_path}")

    def _create_tables(self):
        """创建数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建 posts 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                excerpt TEXT,
                author TEXT,
                category TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published BOOLEAN DEFAULT TRUE,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0
            )
        """)

        # 创建 comments 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER,
                author TEXT,
                email TEXT,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts (id)
            )
        """)

        conn.commit()
        conn.close()


class AuthManager:
    """认证管理器"""

    def __init__(self, db_path: str = "data/auth.db"):
        """
        初始化认证管理器

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.db_path_obj = Path(db_path)
        self.db_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # 创建数据库表
        self._create_tables()

        # 创建默认管理员账户
        self._create_default_admin()

        logger.info(f"[AuthManager] 认证管理器已初始化: {db_path}")

    def _create_tables(self):
        """创建数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建 users 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                level INTEGER DEFAULT 0,
                trust_score REAL DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def _create_default_admin(self):
        """创建默认管理员账户"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 检查是否已有管理员
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("admin",))
        if cursor.fetchone()[0] == 0:
            # 创建默认管理员
            import hashlib
            password_hash = hashlib.sha256("admin123".encode()).hexdigest()

            cursor.execute("""
                INSERT INTO users (username, email, password_hash, level, trust_score)
                VALUES (?, ?, ?, ?, ?)
            """, ("admin", "admin@miya.ai", password_hash, 5, 1.0))

            conn.commit()
            logger.info("[AuthManager] 默认管理员账户已创建: admin/admin123")

        conn.close()


class SecurityGuard:
    """安全防护系统"""

    def __init__(self):
        """初始化安全防护"""
        self.blocked_ips = set()
        self.security_events = []

        # 攻击检测规则
        self.attack_patterns = [
            r'<script.*?>.*?</script>',  # XSS
            r'(union|select|insert|update|delete|drop|create|alter)\s+',  # SQL注入
            r'\.\./',  # 路径遍历
            r'(rm\s+-rf|del\s+/q|format\s+c:)',  # 恶意命令
        ]

        logger.info("[SecurityGuard] 安全防护系统已初始化")

    def scan_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        扫描请求，检测攻击

        Args:
            request: 请求信息 {ip, path, body, params}

        Returns:
            检测到的安全事件，如果没有则返回 None
        """
        import re

        ip = request.get("ip", "unknown")
        path = request.get("path", "")
        body = request.get("body", "")
        params = request.get("params", {})

        # 检查IP是否被封禁
        if ip in self.blocked_ips:
            return {
                "type": "blocked_ip",
                "severity": "critical",
                "source_ip": ip,
                "message": f"IP {ip} 已被封禁",
                "timestamp": datetime.utcnow().isoformat()
            }

        # 检测攻击模式
        all_content = f"{path} {body} {json.dumps(params)}"

        for pattern in self.attack_patterns:
            if re.search(pattern, all_content, re.IGNORECASE):
                event = {
                    "type": "attack_detected",
                    "severity": "high",
                    "source_ip": ip,
                    "pattern": pattern,
                    "message": f"检测到攻击模式: {pattern}",
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.security_events.append(event)
                return event

        return None

    def block_ip(self, ip: str, duration: int = 3600):
        """
        封禁IP

        Args:
            ip: IP地址
            duration: 封禁时长（秒）
        """
        self.blocked_ips.add(ip)

        event = {
            "type": "ip_blocked",
            "severity": "medium",
            "source_ip": ip,
            "message": f"IP {ip} 已被封禁 {duration} 秒",
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.security_events.append(event)

        logger.warning(f"[SecurityGuard] IP已封禁: {ip} ({duration}秒)")


class WebNet:
    """弥娅 Web 子网

    整合博客、认证、安全等 Web 功能
    """

    def __init__(self, memory_engine=None, emotion_manager=None):
        """
        初始化 Web 子网

        Args:
            memory_engine: 记忆引擎
            emotion_manager: 情绪管理器
        """
        self.memory_engine = memory_engine
        self.emotion_manager = emotion_manager

        # 初始化子模块
        self.blog_store = BlogStore()
        self.auth_manager = AuthManager()
        self.security_guard = SecurityGuard()

        logger.info("[WebNet] Web 子网初始化成功")

    # ==================== 博客方法 ====================

    async def get_blog_posts(
        self,
        page: int = 1,
        per_page: int = 10,
        category: Optional[str] = None,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取博客列表"""
        conn = sqlite3.connect(self.blog_store.db_path)
        cursor = conn.cursor()

        # 构建查询
        query = "SELECT * FROM posts WHERE published = ?"
        params = [True]

        if category:
            query += " AND category = ?"
            params.append(category)

        if tag:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")

        # 获取总数
        cursor.execute(query, params)
        total = len(cursor.fetchall())

        # 分页查询
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        posts = []
        for row in rows:
            post = {
                "id": row[0],
                "title": row[1],
                "slug": row[2],
                "content": row[3],
                "excerpt": row[4],
                "author": row[5],
                "category": row[6],
                "tags": json.loads(row[7]) if row[7] else [],
                "created_at": row[8],
                "updated_at": row[9],
                "published": row[10],
                "views": row[11],
                "likes": row[12]
            }
            posts.append(post)

        conn.close()

        return {
            "posts": posts,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        }

    async def get_blog_post(self, slug: str) -> Optional[Dict[str, Any]]:
        """获取单篇博客"""
        conn = sqlite3.connect(self.blog_store.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM posts WHERE slug = ?", (slug,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        # 更新浏览量
        cursor.execute("UPDATE posts SET views = views + 1 WHERE slug = ?", (slug,))
        conn.commit()

        post = {
            "id": row[0],
            "title": row[1],
            "slug": row[2],
            "content": row[3],
            "excerpt": row[4],
            "author": row[5],
            "category": row[6],
            "tags": json.loads(row[7]) if row[7] else [],
            "created_at": row[8],
            "updated_at": row[9],
            "published": row[10],
            "views": row[11],
            "likes": row[12]
        }

        conn.close()
        return post

    async def create_blog_post(
        self,
        title: str,
        content: str,
        author: str,
        category: str,
        tags: List[str],
        published: bool = True
    ) -> Dict[str, Any]:
        """创建博客"""
        conn = sqlite3.connect(self.blog_store.db_path)
        cursor = conn.cursor()

        # 生成slug
        slug = title.lower().replace(" ", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")

        # 生成摘要
        excerpt = content[:200] + "..." if len(content) > 200 else content

        # 插入数据
        cursor.execute("""
            INSERT INTO posts (title, slug, content, excerpt, author, category, tags, published)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, slug, content, excerpt, author, category, json.dumps(tags), published))

        conn.commit()

        # 获取新创建的博客
        post_id = cursor.lastrowid
        post = await self.get_blog_post(slug)

        conn.close()

        logger.info(f"[WebNet] 博客已创建: {title} by {author}")
        return post

    async def update_blog_post(
        self,
        slug: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        published: Optional[bool] = None
    ) -> Dict[str, Any]:
        """更新博客"""
        conn = sqlite3.connect(self.blog_store.db_path)
        cursor = conn.cursor()

        # 检查博客是否存在
        cursor.execute("SELECT id FROM posts WHERE slug = ?", (slug,))
        if not cursor.fetchone():
            conn.close()
            raise ValueError("文章不存在")

        # 构建更新语句
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)

        if content is not None:
            updates.append("content = ?")
            params.append(content)
            # 更新摘要
            excerpt = content[:200] + "..." if len(content) > 200 else content
            updates.append("excerpt = ?")
            params.append(excerpt)

        if category is not None:
            updates.append("category = ?")
            params.append(category)

        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))

        if published is not None:
            updates.append("published = ?")
            params.append(published)

        # 添加更新时间
        updates.append("updated_at = ?")
        params.append(datetime.datetime.now().isoformat())

        # 添加slug参数
        params.append(slug)

        if updates:
            query = f"UPDATE posts SET {', '.join(updates)} WHERE slug = ?"
            cursor.execute(query, params)
            conn.commit()

        # 获取更新后的博客
        post = await self.get_blog_post(slug)
        conn.close()

        logger.info(f"[WebNet] 博客已更新: {slug}")
        return post

    async def delete_blog_post(self, slug: str) -> bool:
        """删除博客"""
        conn = sqlite3.connect(self.blog_store.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM posts WHERE slug = ?", (slug,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        if deleted:
            logger.info(f"[WebNet] 博客已删除: {slug}")

        return deleted

    # ==================== 认证方法 ====================

    async def register_user(
        self,
        username: str,
        email: str,
        password: str
    ) -> Dict[str, Any]:
        """用户注册"""
        import hashlib

        conn = sqlite3.connect(self.auth_manager.db_path)
        cursor = conn.cursor()

        # 检查用户名是否已存在
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return {
                "success": False,
                "message": "用户名已存在"
            }

        # 检查邮箱是否已存在
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            return {
                "success": False,
                "message": "邮箱已被注册"
            }

        # 创建用户
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        cursor.execute("""
            INSERT INTO users (username, email, password_hash, level, trust_score)
            VALUES (?, ?, ?, ?, ?)
        """, (username, email, password_hash, 1, 0.5))

        conn.commit()

        # 获取新用户
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()

        user = {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "level": row[4],
            "trust_score": row[5],
            "created_at": row[6]
        }

        conn.close()

        logger.info(f"[WebNet] 用户已注册: {username}")
        return {
            "success": True,
            "message": "注册成功",
            "user": user
        }

    async def login_user(
        self,
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """用户登录"""
        import hashlib

        # 每次登录时重新检查 JWT 是否可用
        try:
            import jwt
            jwt_available = True
        except ImportError:
            jwt_available = False

        logger.info(f"[WebNet] 收到登录请求: username={username}, JWT可用={jwt_available}")

        if not jwt_available:
            logger.error("[WebNet] JWT库未安装")
            return {
                "success": False,
                "message": "JWT库未安装，请运行: pip install pyjwt"
            }

        conn = sqlite3.connect(self.auth_manager.db_path)
        cursor = conn.cursor()

        # 查找用户
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()

        logger.info(f"[WebNet] 查询用户结果: found={row is not None}")

        if not row:
            conn.close()
            return {
                "success": False,
                "message": "用户名或密码错误"
            }

        # 验证密码
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        logger.info(f"[WebNet] 验证密码: hash_match={row[3] == password_hash}")

        if row[3] != password_hash:
            conn.close()
            logger.warning(f"[WebNet] 密码错误: username={username}")
            return {
                "success": False,
                "message": "用户名或密码错误"
            }

        # 更新最后登录时间
        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.utcnow().isoformat(), row[0]))
        conn.commit()

        # 生成JWT Token (使用动态导入的 jwt)
        token = jwt.encode({
            "sub": row[1],
            "level": row[4],
            "exp": datetime.utcnow().timestamp() + 86400  # 24小时
        }, "miya_secret_key", algorithm="HS256")

        logger.info(f"[WebNet] 登录成功: username={username}, user_id={row[0]}, level={row[4]}")

        user = {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "level": row[4],
            "trust_score": row[5],
            "created_at": row[6]
        }

        conn.close()

        logger.info(f"[WebNet] 用户已登录: {username}")
        return {
            "success": True,
            "message": "登录成功",
            "user": user,
            "token": token
        }

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证Token"""
        if not JWT_AVAILABLE:
            return None

        try:
            payload = jwt.decode(token, "miya_secret_key", algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def block_ip(self, ip: str, duration: int = 3600):
        """封禁IP"""
        self.security_guard.block_ip(ip, duration)

    def scan_security(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """扫描安全"""
        return self.security_guard.scan_request(request)

    # ==================== 系统状态方法 ====================

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        # 这里应该从Miya主类获取真实状态
        # 现在返回基本状态
        return {
            "identity": {
                "name": "Miya",
                "version": "1.0.0"
            },
            "personality": {
                "state": "normal",
                "dominant_trait": "helpful",
                "vectors": {
                    "warmth": 0.8,
                    "logic": 0.7,
                    "creativity": 0.6,
                    "empathy": 0.9,
                    "resilience": 0.7
                }
            },
            "emotion": {
                "primary": "calm",
                "intensity": 0.5,
                "state": "balanced",
                "current": {
                    "joy": 0.6,
                    "sadness": 0.1,
                    "anger": 0.1,
                    "fear": 0.1,
                    "surprise": 0.1
                }
            },
            "memory_stats": {
                "tide_count": 0,
                "longterm_count": 0
            },
            "stats": {
                "total_visits": 0,
                "total_posts": 0,
                "total_users": 1
            },
            "timestamp": datetime.utcnow().isoformat()
        }
