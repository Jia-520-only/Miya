"""
地球online API — 弥娅与现实生活的游戏化模块

功能:
- 背包物品管理 (现实物品 + 图片上传)
- 任务系统 (必须/可选任务, 奖励与惩罚)
- 剧情事件记录 (生活剧情化)
- 角色好感度 (现实中的人物, 手动记录互动)
- 玩家状态 (等级/经验/地球币)
"""

import logging
import os
import uuid
from typing import Any, Dict, Optional

from core.earth_online_store import get_earth_store

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, File, HTTPException, UploadFile

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object
    File = None
    HTTPException = None
    UploadFile = None


class EarthOnlineRoutes:
    """地球online 路由"""

    def __init__(self, web_net=None, decision_hub=None):
        self.web_net = web_net
        self.decision_hub = decision_hub

        if not FASTAPI_AVAILABLE:
            logger.warning("[EarthOnline] FastAPI 不可用")
            self.router = None
            return

        self.store = get_earth_store()
        self.router = APIRouter(prefix="/api/earth", tags=["EarthOnline"])
        self._setup_routes()
        logger.info("[EarthOnline] 地球online 路由已初始化")

    # ── 工具 ────────────────────────────────────────

    def _save_upload(self, upload: UploadFile) -> str:
        """保存上传图片, 返回相对路径 (大小受 earth_online.items.max_image_size_mb 限制)"""
        max_mb = max(1.0, float(self.store._cfg("items", "max_image_size_mb", default=10)))
        image_dir = self.store.image_dir
        os.makedirs(image_dir, exist_ok=True)
        ext = os.path.splitext(upload.filename or "")[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            ext = ".jpg"
        filename = f"{uuid.uuid4().hex[:16]}{ext}"
        dest = os.path.join(image_dir, filename)
        size = 0
        limit = int(max_mb * 1024 * 1024)
        with open(dest, "wb") as f:
            while True:
                chunk = upload.file.read(1024 * 256)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    f.close()
                    os.remove(dest)
                    raise HTTPException(status_code=400, detail=f"图片超过大小上限 {max_mb} MB")
                f.write(chunk)
        try:
            from io import BytesIO
            from PIL import Image
            max_pixels = int(self.store._cfg("items", "max_image_pixels", default=40_000_000))
            with Image.open(dest) as image:
                if image.width * image.height > max_pixels:
                    raise HTTPException(status_code=400, detail="图片像素数量超过安全上限")
                image.verify()
            with Image.open(dest) as image:
                clean = BytesIO()
                output_format = {
                    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".gif": "GIF",
                    ".webp": "WEBP", ".bmp": "BMP",
                }[ext]
                clean_image = image.convert("RGBA" if image.mode in ("RGBA", "LA") and output_format in ("PNG", "WEBP") else "RGB")
                save_options = {"quality": 92} if output_format in ("JPEG", "WEBP") else {}
                clean_image.save(clean, format=output_format, **save_options)
                with open(dest, "wb") as output:
                    output.write(clean.getvalue())
        except HTTPException:
            os.remove(dest)
            raise
        except Exception as exc:
            os.remove(dest)
            raise HTTPException(status_code=400, detail="上传文件不是有效图片") from exc
        return f"/api/earth/images/{filename}"

    # ── v17.5 桥接: 游戏事件 → 弥娅本体 (统一主动窗口 + 统一记忆) ──

    async def _deliver_redeem(self, result: Dict[str, Any]) -> None:
        """服务券使用后: 弥娅用当前人格重新表达并经活跃平台发送；同时写入统一记忆。"""
        try:
            from core.earth_online_bridge import deliver_via_proactive, remember

            name = str(result.get("name", ""))
            interaction = str(result.get("interaction", ""))
            await deliver_via_proactive(
                {
                    "source": "earth_online",
                    "event": "service_ticket_redeemed",
                    "ticket": name,
                    "reference_interaction": interaction,
                    "candidate_message": interaction,
                    "note": "佳刚在网页背包使用了服务券。请基于这张券的作用，用你当前的人格向他回应；reference_interaction 只是原本的基调文案，不要照念。",
                    "urgency": "normal",
                },
                key=f"earth_service:{name}",
                trigger_type="earth_service",
                decision_hub=self.decision_hub,
            )
            await remember(
                f"[地球online] 佳使用了服务券「{name}」，我的回应基调: {interaction[:80]}",
                decision_hub=self.decision_hub,
                source="earth_service",
            )
        except Exception as exc:
            logger.debug(f"[EarthOnline] 服务券投递失败: {exc}")

    async def _remember_purchase(self, name: str, shop: str) -> None:
        """兑换纪念: 让弥娅记得佳换走了什么 (不主动打扰，只入记忆)。"""
        try:
            from core.earth_online_bridge import remember

            await remember(
                f"[地球online] 佳在{shop}兑换了「{name}」。",
                decision_hub=self.decision_hub,
                source="earth_purchase",
            )
        except Exception as exc:
            logger.debug(f"[EarthOnline] 兑换记忆写入失败: {exc}")

    def _setup_routes(self):
        """设置地球online相关路由"""

        # ── 静态图片服务 ──

        @self.router.get("/images/{filename}")
        async def get_image(filename: str):
            from fastapi.responses import FileResponse

            safe = os.path.basename(filename)
            path = os.path.join(self.store.image_dir, safe)
            if not os.path.isfile(path):
                raise HTTPException(status_code=404, detail="图片不存在")
            return FileResponse(path)

        # ── 玩家状态 ──

        @self.router.get("/player")
        async def get_player():
            """获取玩家状态 (等级/经验/地球币 + 开拓者角色卡)"""
            return self.store.get_player()

        @self.router.put("/player")
        async def update_player(request: Dict[str, Any] = None):
            """更新开拓者角色卡 (name/title/avatar_path/bio/attrs)"""
            request = request or {}
            return self.store.update_player(request)

        @self.router.post("/player/exp")
        async def add_exp(request: Dict[str, Any] = None):
            """增加经验 (弥娅发放)"""
            request = request or {}
            try:
                amount = int(request.get("amount", 0))
                return self.store.add_exp(amount)
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

        @self.router.post("/player/currency")
        async def add_currency(request: Dict[str, Any] = None):
            """增减弥娅币 (弥娅发放/扣除)"""
            request = request or {}
            try:
                amount = int(request.get("amount", 0))
                return self.store.add_miya_currency(amount)
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

        @self.router.post("/player/spend")
        async def spend_miya_coins(request: Dict[str, Any] = None):
            """扣除弥娅币 (佳用弥娅币兑换弥娅的互动服务)"""
            request = request or {}
            amount = int(request.get("amount", 0))
            reason = str(request.get("reason", ""))
            result = self.store.spend_miya_coins(amount, reason)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "扣除失败"))
            return result

        @self.router.post("/player/earth-currency")
        async def adjust_earth_currency(request: Dict[str, Any] = None):
            """调整现实资产 (人民币元, 可正可负, 记流水)。amount=+50 记一笔收入, -12.5 记一笔支出"""
            request = request or {}
            try:
                amount = float(request.get("amount", 0))
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="amount 必须是数字") from e
            result = self.store.adjust_earth_currency(amount, str(request.get("reason", "")))
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "调整失败"))
            return result

        @self.router.get("/currency/ledger")
        async def currency_ledger(limit: int = 100, currency: str = ""):
            """货币/经验流水 (弥娅币/地球币/经验 统一记账)"""
            return self.store.list_currency_ledger(limit=limit, currency=currency)

        # ── JSON 可视化 (记事本模式) ──

        @self.router.get("/export")
        async def export_json():
            """导出全部数据为 JSON (写入可视化镜像文件后返回)"""
            self.store._write_mirror()
            return self.store.export_json()

        @self.router.get("/json")
        async def read_json():
            """读取可视化 JSON 文件内容"""
            return self.store.read_mirror()

        @self.router.post("/import")
        async def import_json(request: Dict[str, Any] = None):
            """从 JSON 整体导入 (自动备份数据库, 结构与 export 一致)"""
            request = request or {}
            data = request.get("data")
            if not isinstance(data, dict):
                raise HTTPException(status_code=400, detail="缺少 data 字段 (JSON 对象)")
            try:
                return self.store.import_json(data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"导入失败: {e}") from e

        # ── 模板库 ──

        @self.router.get("/templates")
        async def get_templates():
            """获取物品/角色/任务模板"""
            return self.store.get_templates()

        @self.router.put("/templates")
        async def save_templates(request: Dict[str, Any] = None):
            """保存自定义模板"""
            request = request or {}
            try:
                return self.store.save_templates(request)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"模板保存失败: {e}") from e

        # ── 通用图片上传 (物品照片/开拓者头像/角色头像) ──

        @self.router.post("/upload")
        async def upload_image(file: UploadFile = File(...), item_id: Optional[int] = None):
            """通用图片上传: 返回 image_path, 可直接用于物品/头像"""
            path = self._save_upload(file)
            result = {"success": True, "image_path": path, "url": path}
            if item_id:
                item = self.store.update_item(item_id, {"image_path": path})
                result["item"] = item
            return result

        # ── 背包物品 ──

        @self.router.get("/items")
        async def list_items(category: str = "", status: str = ""):
            """获取背包物品列表"""
            return self.store.list_items(category=category, status=status)

        @self.router.get("/items/{item_id}")
        async def get_item(item_id: int):
            """获取单个物品"""
            item = self.store.get_item(item_id)
            if not item:
                raise HTTPException(status_code=404, detail="物品不存在")
            return item

        @self.router.post("/items")
        async def create_item(request: Dict[str, Any] = None):
            """新增背包物品"""
            request = request or {}
            name = str(request.get("name", "")).strip()
            if not name:
                raise HTTPException(status_code=400, detail="物品名称不能为空")
            try:
                item = self.store.create_item(
                    name=name,
                    category=str(request.get("category", "other")),
                    rarity=str(request.get("rarity", "common")),
                    quantity=int(request.get("quantity", 1)),
                    description=str(request.get("description", "")),
                    image_path=str(request.get("image_path", "")),
                    markdown=str(request.get("markdown", "")),
                    fields=request.get("fields") if isinstance(request.get("fields"), dict) else None,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
            return item

        @self.router.post("/items/upload")
        async def upload_item_image(file: UploadFile = File(...), item_id: Optional[int] = None):
            """上传物品图片 (手机拍照直接入库)"""
            path = self._save_upload(file)
            result = {"success": True, "image_path": path, "url": path}
            if item_id:
                item = self.store.update_item(item_id, {"image_path": path})
                result["item"] = item
            return result

        @self.router.put("/items/{item_id}")
        async def update_item(item_id: int, request: Dict[str, Any] = None):
            """更新物品信息"""
            item = self.store.update_item(item_id, request or {})
            if not item:
                raise HTTPException(status_code=404, detail="物品不存在")
            return item

        @self.router.delete("/items/{item_id}")
        async def delete_item(item_id: int):
            """删除物品"""
            if not self.store.delete_item(item_id):
                raise HTTPException(status_code=404, detail="物品不存在")
            return {"success": True}

        # ── 任务 ──

        @self.router.get("/quests")
        async def list_quests(status: str = "", quest_type: str = ""):
            """获取任务列表"""
            return self.store.list_quests(status=status, quest_type=quest_type)

        @self.router.get("/quests/history")
        async def get_quest_history(limit: int = 50):
            """获取任务历史"""
            return self.store.quest_history(limit=limit)

        @self.router.post("/quests")
        async def create_quest(request: Dict[str, Any] = None):
            """新增任务 (弥娅安排/佳手动创建)"""
            request = request or {}
            title = str(request.get("title", "")).strip()
            if not title:
                raise HTTPException(status_code=400, detail="任务标题不能为空")
            quest = self.store.create_quest(
                title=title,
                description=str(request.get("description", "")),
                quest_type=str(request.get("quest_type", "branch")),
                must_complete=bool(request.get("must_complete", False)),
                reward_currency=int(request.get("reward_currency", 0)),
                reward_exp=int(request.get("reward_exp", 0)),
                penalty_currency=int(request.get("penalty_currency", 0)),
                deadline=str(request.get("deadline", "")),
                source=str(request.get("source", "manual")),
                difficulty=int(request.get("difficulty", 1)),
                fields=request.get("fields") if isinstance(request.get("fields"), dict) else None,
                subtasks=request.get("subtasks") if isinstance(request.get("subtasks"), list) else None,
                recurring=str(request.get("recurring", "")),
            )
            return quest

        @self.router.put("/quests/{quest_id}")
        async def update_quest(quest_id: int, request: Dict[str, Any] = None):
            """更新任务"""
            quest = self.store.update_quest(quest_id, request or {})
            if not quest:
                raise HTTPException(status_code=404, detail="任务不存在")
            return quest

        @self.router.post("/quests/{quest_id}/accept")
        async def accept_quest(quest_id: int):
            """接取任务: pending → ongoing (前台任务板)"""
            result = self.store.accept_quest(quest_id)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "操作失败"))
            return result

        @self.router.post("/quests/{quest_id}/complete")
        async def complete_quest(quest_id: int):
            """完成任务: 发放经验/地球币"""
            result = self.store.complete_quest(quest_id)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "操作失败"))
            return result

        @self.router.post("/quests/{quest_id}/fail")
        async def fail_quest(quest_id: int):
            """任务失败: 扣除惩罚"""
            result = self.store.fail_quest(quest_id)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "操作失败"))
            return result

        @self.router.post("/quests/{quest_id}/cancel")
        async def cancel_quest(quest_id: int):
            """取消任务: 无惩罚"""
            result = self.store.cancel_quest(quest_id)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "操作失败"))
            return result

        @self.router.post("/quests/check-overdue")
        async def check_overdue():
            """检查逾期任务: 自动失败 + 惩罚 (弥娅每日调用)"""
            return self.store.check_overdue()

        @self.router.post("/quests/{quest_id}/subtasks")
        async def toggle_subtask(quest_id: int, request: Dict[str, Any] = None):
            """更新任务子任务完成状态 (index 从 0 开始; done 缺省则切换)"""
            request = request or {}
            index = int(request.get("index", -1))
            done = request.get("done")
            result = self.store.toggle_subtask(quest_id, index, None if done is None else bool(done))
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "更新失败"))
            return result

        # ── 全局事件动态流 (数据互通) ──

        @self.router.get("/activity")
        async def list_activity(limit: int = 50, kind: str = ""):
            """获取全局动态流 (任务/物品/角色/剧情/签到/成就/寄语)"""
            return self.store.list_activity(limit=min(500, max(1, limit)), kind=kind)

        @self.router.post("/activity/{activity_id}/comment")
        async def comment_activity(activity_id: int, request: Dict[str, Any] = None):
            """弥娅对一条动态写评论"""
            request = request or {}
            comment = str(request.get("comment", "")).strip()
            if not comment:
                raise HTTPException(status_code=400, detail="评论内容不能为空")
            row = self.store.update_activity_comment(activity_id, comment)
            if not row:
                raise HTTPException(status_code=404, detail="动态不存在")
            return row

        # ── 币种换算 ──

        @self.router.get("/exchange-rates")
        async def exchange_rates():
            """地球币 → 现实货币换算汇率 (配置化)"""
            return self.store.get_exchange_rates()

        # ── 前台主题 ──

        @self.router.get("/theme")
        async def get_theme():
            """前台主题 (配色/壁纸/磨砂玻璃)"""
            return self.store.get_theme()

        @self.router.put("/theme")
        async def save_theme(request: Dict[str, Any] = None):
            """保存前台主题"""
            return self.store.save_theme(request or {})

        @self.router.post("/theme/reset")
        async def reset_theme():
            """恢复前台主题默认值 (鎏金)"""
            return self.store.reset_theme()

        # ── 弥娅策划 ──

        @self.router.get("/analysis")
        async def get_analysis():
            """全量数据综合分析 (弥娅担任策划)"""
            return self.store.get_analysis()

        @self.router.post("/daily-ritual")
        async def daily_ritual():
            """弥娅每日仪式 (逾期检查 + 到期提醒 + 签到状态)"""
            return self.store.daily_ritual()

        @self.router.get("/life-hub")
        async def life_hub():
            """现实优先的生活中枢快照。"""
            return self.store.get_life_hub()

        # ── 称号系统 ──

        @self.router.get("/titles")
        async def get_titles():
            """可佩戴称号 (默认 + 已解锁成就称号 + 当前佩戴)"""
            return self.store.list_titles()

        @self.router.post("/titles/equip")
        async def equip_title(request: Dict[str, Any] = None):
            """佩戴称号"""
            request = request or {}
            result = self.store.equip_title(str(request.get("title", "")))
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "佩戴失败"))
            return result

        # ── 到期提醒 ──

        @self.router.get("/quests/due-soon")
        async def due_soon(days: int = 3):
            """即将到期/已逾期的未完成任务"""
            return self.store.list_due_soon(days=days)

        # ── 每周报告 ──

        @self.router.get("/weekly-report")
        async def weekly_report():
            """本周统计报告"""
            return self.store.get_weekly_report()

        # ── 单人开放世界探索 ──

        @self.router.get("/world")
        async def world_regions():
            """获取世界地图区域与个人探索进度"""
            return {
                "regions": self.store.list_world_regions(),
                "discoveries": self.store.list_world_discoveries(limit=200),
                "status": self.store.get_world_status(),
            }

        @self.router.get("/world/status")
        async def world_status():
            """获取当前世界时间、天气和限时区域状态"""
            return self.store.get_world_status()

        @self.router.get("/world/real-context")
        async def world_real_context():
            """获取现实数据连接状态与最近天气快照"""
            return self.store.get_real_context(auto_refresh=True)

        @self.router.post("/world/real-context/refresh")
        async def refresh_world_real_context(request: Dict[str, Any] = None):
            """主动刷新现实天气；失败时返回明确的未同步状态"""
            return self.store.refresh_real_context(request or {})

        @self.router.get("/world/real-context/settings")
        async def world_real_context_settings():
            return self.store.get_real_context_settings()

        @self.router.put("/world/real-context/settings")
        async def update_world_real_context_settings(request: Dict[str, Any] = None):
            return self.store.update_real_context_settings(request or {})

        @self.router.put("/world/real-context/api-key")
        async def update_world_weather_api_key(request: Dict[str, Any] = None):
            try:
                return self.store.update_weather_api_key(str((request or {}).get("api_key", "")))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.router.put("/world/regions/{region_key}")
        async def update_world_region(region_key: str, request: Dict[str, Any] = None):
            region = self.store.update_world_region(region_key, request or {})
            if not region:
                raise HTTPException(status_code=404, detail="世界区域不存在")
            return region

        @self.router.get("/world/events")
        async def list_world_events(region_key: str = ""):
            return self.store.list_world_custom_events(region_key=region_key)

        @self.router.post("/world/events")
        async def create_world_event(request: Dict[str, Any] = None):
            request = request or {}
            event = self.store.create_world_custom_event(
                region_key=str(request.get("region_key", "")), title=str(request.get("title", "")), text=str(request.get("text", "")),
                reward_currency=int(request.get("reward_currency", 0)), reward_exp=int(request.get("reward_exp", 0)), kind=str(request.get("kind", "story")),
            )
            if not event:
                raise HTTPException(status_code=400, detail="自定义世界事件内容不完整或区域不存在")
            return event

        @self.router.delete("/world/events/{event_id}")
        async def delete_world_event(event_id: int):
            if not self.store.delete_world_custom_event(event_id):
                raise HTTPException(status_code=404, detail="世界事件不存在")
            return {"success": True}

        @self.router.get("/world/events/{event_key}/shop")
        async def world_event_shop(event_key: str):
            return self.store.list_world_event_shop(event_key)

        @self.router.post("/world/events/{event_key}/shop/{item_key}/buy")
        async def buy_world_event_item(event_key: str, item_key: str):
            result = self.store.purchase_world_event_item(event_key, item_key)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "兑换失败"))
            import asyncio

            asyncio.create_task(self._remember_purchase(str(result.get("item", {}).get("name", item_key)), f"活动商店「{event_key}」"))
            return result

        @self.router.get("/miya-shop")
        async def miya_shop():
            return self.store.list_miya_shop()

        @self.router.post("/miya-shop/{item_key}/buy")
        async def buy_miya_shop_item(item_key: str):
            result = self.store.purchase_miya_shop_item(item_key)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "商城兑换失败"))
            import asyncio

            asyncio.create_task(self._remember_purchase(str(result.get("item", {}).get("name", item_key)), "弥娅兑换所"))
            return result

        @self.router.post("/miya-shop/redeem")
        async def redeem_miya_service(request: Dict[str, Any] = None):
            """使用一张服务券 (body: item_id 或 item_key)。返回互动文案；弥娅会另经消息平台用人格回应并记住这件事"""
            request = request or {}
            item_id = request.get("item_id")
            result = self.store.redeem_service_ticket(
                item_id=int(item_id) if item_id else None,
                item_key=str(request.get("item_key", "")),
            )
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "使用失败"))
            import asyncio

            asyncio.create_task(self._deliver_redeem(result))  # 后台投递，不阻塞前端
            return result

        # ── 弥娅商城货架管理 (后台/弥娅自主上架) ──

        @self.router.get("/miya-shop/manage")
        async def manage_miya_shop():
            """管理视图: 内置商品(不可改删) + 全部自定义商品(含下架)"""
            return self.store.list_miya_shop_managed()

        @self.router.post("/miya-shop/manage")
        async def create_miya_shop_item(request: Dict[str, Any] = None):
            item = self.store.create_miya_shop_item(request or {})
            if not item:
                raise HTTPException(status_code=400, detail="商品参数不完整 (需要 key/name)，或 key 与内置商品冲突")
            return {"success": True, "item": item}

        @self.router.put("/miya-shop/manage/{item_key}")
        async def update_miya_shop_item(item_key: str, request: Dict[str, Any] = None):
            item = self.store.update_miya_shop_item(item_key, request or {})
            if not item:
                raise HTTPException(status_code=404, detail="自定义商品不存在 (内置商品不可修改)")
            return {"success": True, "item": item}

        @self.router.delete("/miya-shop/manage/{item_key}")
        async def delete_miya_shop_item(item_key: str):
            if not self.store.delete_miya_shop_item(item_key):
                raise HTTPException(status_code=404, detail="自定义商品不存在 (内置商品不可删除)")
            return {"success": True}

        @self.router.get("/world/discoveries")
        async def world_discoveries(region_key: str = "", limit: int = 100):
            """获取已发现的世界事件"""
            return self.store.list_world_discoveries(region_key=region_key, limit=limit)

        @self.router.post("/world/{region_key}/explore")
        async def explore_world_region(region_key: str, request: Dict[str, Any] = None):
            """探索一个区域，首次发现事件会发放奖励；区域启用地理围栏时需携带真实坐标"""
            request = request or {}
            result = self.store.explore_world_region(
                region_key,
                latitude=request.get("latitude"),
                longitude=request.get("longitude"),
            )
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "探索失败"))
            return result

        # ── 限时活动管理 (内置 + 后台自定义) ──

        @self.router.get("/world/event-areas")
        async def list_world_event_areas():
            today = self.store.get_world_status().get("date", "")
            areas = self.store.list_world_event_areas()
            for area in areas:
                area["running"] = area["start"] <= today <= area["end"] and bool(area.get("active", 1))
            return areas

        @self.router.post("/world/event-areas")
        async def create_world_event_area(request: Dict[str, Any] = None):
            area = self.store.create_world_event_area(request or {})
            if not area:
                raise HTTPException(status_code=400, detail="活动参数不完整 (需要 key/name/start/end，且 start ≤ end)")
            return {"success": True, "area": area}

        @self.router.put("/world/event-areas/{event_key}")
        async def update_world_event_area(event_key: str, request: Dict[str, Any] = None):
            area = self.store.update_world_event_area(event_key, request or {})
            if not area:
                raise HTTPException(status_code=404, detail="自定义活动不存在 (内置活动不可修改)")
            return {"success": True, "area": area}

        @self.router.delete("/world/event-areas/{event_key}")
        async def delete_world_event_area(event_key: str):
            if not self.store.delete_world_event_area(event_key):
                raise HTTPException(status_code=404, detail="自定义活动不存在 (内置活动不可删除)")
            return {"success": True}

        @self.router.post("/world/event-areas/{event_key}/items")
        async def create_world_event_shop_item(event_key: str, request: Dict[str, Any] = None):
            item = self.store.create_world_event_shop_item(event_key, request or {})
            if not item:
                raise HTTPException(status_code=400, detail="商品参数不完整 (需要 key/name)")
            return {"success": True, "item": item}

        @self.router.delete("/world/event-areas/{event_key}/items/{item_key}")
        async def delete_world_event_shop_item(event_key: str, item_key: str):
            if not self.store.delete_world_event_shop_item(event_key, item_key):
                raise HTTPException(status_code=404, detail="自定义商品不存在")
            return {"success": True}

        @self.router.post("/world/discoveries/{discovery_id}/choice")
        async def choose_world_discovery(discovery_id: int, request: Dict[str, Any] = None):
            result = self.store.choose_world_discovery(discovery_id, str((request or {}).get("choice", "")))
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "同行选择失败"))
            return result

        @self.router.post("/world/{region_key}/image")
        async def upload_world_region_image(region_key: str, file: UploadFile = File(...)):
            """上传并绑定区域现实照片，作为世界地图区域底图。"""
            path = self._save_upload(file)
            region = self.store.update_world_region_image(region_key, path)
            if not region:
                raise HTTPException(status_code=404, detail="世界区域不存在")
            return {"success": True, "image_path": path, "region": region}

        @self.router.post("/world/{region_key}/commission")
        async def world_commission(region_key: str):
            """领取指定区域当天的专属委托"""
            result = self.store.create_region_commission(region_key)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "领取委托失败"))
            return result

        # ── 剧情 ──

        @self.router.get("/story")
        async def list_story(event_type: str = "", limit: int = 100):
            """获取剧情事件列表"""
            return self.store.list_story(event_type=event_type, limit=limit)

        @self.router.post("/story")
        async def create_story(request: Dict[str, Any] = None):
            """新增剧情事件 (弥娅/佳记录生活)"""
            request = request or {}
            title = str(request.get("title", "")).strip()
            if not title:
                raise HTTPException(status_code=400, detail="剧情标题不能为空")
            event = self.store.create_story(
                title=title,
                content=str(request.get("content", "")),
                event_type=str(request.get("event_type", "life")),
                character_id=int(request["character_id"]) if request.get("character_id") else None,
                item_id=int(request["item_id"]) if request.get("item_id") else None,
                happened_at=str(request.get("happened_at", "")),
                fields=request.get("fields") if isinstance(request.get("fields"), dict) else None,
                image_path=str(request.get("image_path", "")),
            )
            return event

        @self.router.delete("/story/{story_id}")
        async def delete_story(story_id: int):
            """删除剧情事件"""
            if not self.store.delete_story(story_id):
                raise HTTPException(status_code=404, detail="剧情不存在")
            return {"success": True}

        @self.router.put("/story/{story_id}")
        async def update_story(story_id: int, request: Dict[str, Any] = None):
            """编辑剧情事件 (标题/内容/类型/关联/时间/图片)"""
            story = self.store.update_story(story_id, request or {})
            if not story:
                raise HTTPException(status_code=404, detail="剧情不存在")
            return story

        # ── 角色好感度 ──

        @self.router.get("/characters")
        async def list_characters():
            """获取角色列表 (按好感度排序)"""
            return self.store.list_characters()

        @self.router.post("/characters")
        async def create_character(request: Dict[str, Any] = None):
            """新增角色 (现实中的人物)"""
            request = request or {}
            name = str(request.get("name", "")).strip()
            if not name:
                raise HTTPException(status_code=400, detail="角色名称不能为空")
            character = self.store.create_character(
                name=name,
                nickname=str(request.get("nickname", "")),
                relationship=str(request.get("relationship", "friend")),
                affinity=int(request.get("affinity", 0)),
                avatar_path=str(request.get("avatar_path", "")),
                notes=str(request.get("notes", "")),
                birthday=str(request.get("birthday", "")),
                markdown=str(request.get("markdown", "")),
                fields=request.get("fields") if isinstance(request.get("fields"), dict) else None,
            )
            return character

        @self.router.put("/characters/{character_id}")
        async def update_character(character_id: int, request: Dict[str, Any] = None):
            """更新角色信息"""
            character = self.store.update_character(character_id, request or {})
            if not character:
                raise HTTPException(status_code=404, detail="角色不存在")
            return character

        @self.router.delete("/characters/{character_id}")
        async def delete_character(character_id: int):
            """删除角色"""
            if not self.store.delete_character(character_id):
                raise HTTPException(status_code=404, detail="角色不存在")
            return {"success": True}

        @self.router.post("/characters/{character_id}/affinity")
        async def add_affinity(character_id: int, request: Dict[str, Any] = None):
            """好感度变动 (手动记录互动: delta 可正可负, reason 说明原因)"""
            request = request or {}
            delta = int(request.get("delta", 0))
            if delta == 0:
                raise HTTPException(status_code=400, detail="delta 不能为 0")
            character = self.store.add_affinity(
                character_id=character_id,
                delta=delta,
                reason=str(request.get("reason", "")),
            )
            if not character:
                raise HTTPException(status_code=404, detail="角色不存在")
            return character

        @self.router.get("/characters/{character_id}/affinity-logs")
        async def get_affinity_logs(character_id: int, limit: int = 50):
            """获取好感度变动记录"""
            return self.store.affinity_logs(character_id, limit=limit)

        # ── 成就系统 ──

        @self.router.get("/achievements")
        async def list_achievements():
            """获取成就列表 (含进度与解锁状态)"""
            return self.store.list_achievements()

        @self.router.post("/achievements/refresh")
        async def refresh_achievements():
            """按当前数据刷新成就进度, 返回新解锁列表"""
            return {"success": True, "newly_unlocked": self.store.refresh_achievements()}

        @self.router.post("/achievements/custom")
        async def add_achievement(request: Dict[str, Any] = None):
            """弥娅自定义成就"""
            request = request or {}
            result = self.store.add_achievement(
                key=str(request.get("key", "")),
                title=str(request.get("title", "")),
                description=str(request.get("description", "")),
                icon=str(request.get("icon", "✦")),
                category=str(request.get("category", "custom")),
                target=int(request.get("target", 1)),
                reward_currency=int(request.get("reward_currency", 0)),
                reward_exp=int(request.get("reward_exp", 0)),
                title_award=str(request.get("title_award", "")),
                hidden=bool(request.get("hidden", False)),
            )
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "创建失败"))
            return result

        @self.router.post("/achievements/progress")
        async def set_achievement_progress(request: Dict[str, Any] = None):
            """弥娅更新成就进度 (达标自动解锁发奖励)"""
            request = request or {}
            key = str(request.get("key", "")).strip()
            if not key:
                raise HTTPException(status_code=400, detail="key 不能为空")
            result = self.store.set_achievement_progress(key, int(request.get("progress", 0)))
            if not result.get("success"):
                raise HTTPException(status_code=404, detail=result.get("message", "成就不存在"))
            return result

        # ── 每日签到 ──

        @self.router.get("/checkin")
        async def get_checkin():
            """获取签到状态 (是否已签/连续天数/历史)"""
            return self.store.get_checkin_status()

        @self.router.post("/checkin")
        async def do_checkin(request: Dict[str, Any] = None):
            """签到: 发放奖励 (可带 sleep_hours 昨晚睡眠时长, 按睡眠回复体力; 重复签到返回 already)"""
            request = request or {}
            sleep_hours = request.get("sleep_hours")
            try:
                return self.store.checkin(None if sleep_hours in (None, "") else float(sleep_hours))
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="sleep_hours 必须是数字 (小时)") from e

        @self.router.get("/checkin/history")
        async def checkin_history(limit: int = 100):
            """获取签到历史"""
            return self.store.list_checkins(limit=limit)

        # ── 弥娅寄语 ──

        @self.router.get("/notes")
        async def list_notes(limit: int = 30):
            """获取弥娅寄语 (置顶优先)"""
            return self.store.list_notes(limit=limit)

        @self.router.post("/notes")
        async def add_note(request: Dict[str, Any] = None):
            """新增弥娅寄语 (弥娅给佳的公告/留言)"""
            request = request or {}
            result = self.store.add_note(
                content=str(request.get("content", "")),
                mood=str(request.get("mood", "neutral")),
                pinned=bool(request.get("pinned", False)),
            )
            if not result.get("success", True):
                raise HTTPException(status_code=400, detail=result.get("message", "内容不能为空"))
            return result

        @self.router.post("/notes/{note_id}/pin")
        async def pin_note(note_id: int, request: Dict[str, Any] = None):
            """置顶/取消置顶寄语"""
            request = request or {}
            note = self.store.pin_note(note_id, bool(request.get("pinned", True)))
            if not note:
                raise HTTPException(status_code=404, detail="寄语不存在")
            return note

        @self.router.delete("/notes/{note_id}")
        async def delete_note(note_id: int):
            """删除寄语"""
            if not self.store.delete_note(note_id):
                raise HTTPException(status_code=404, detail="寄语不存在")
            return {"success": True}

        # ── 统计数据中心 ──

        @self.router.get("/stats")
        async def get_stats():
            """可视化统计: 任务/物品/角色/剧情/签到/成就 多维分布"""
            return self.store.get_stats()

        # ── 回忆抽卡 (v17) ──

        @self.router.get("/memory")
        async def memory_pool():
            """回忆卡池信息: 价格/保底/权重/收集进度"""
            return self.store.get_memory_pool_info()

        @self.router.post("/memory/pull")
        async def memory_pull(request: Dict[str, Any] = None):
            """回忆抽卡: times=1 单抽 / times=10 十连 (九折+保底)。消耗弥娅币，重复碎片自动转化"""
            request = request or {}
            result = self.store.pull_memory(int(request.get("times", 1)))
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "抽取失败"))
            return result

        @self.router.get("/memory/pulls")
        async def memory_pulls(limit: int = 50):
            """回忆抽卡历史记录"""
            return self.store.list_memory_pulls(limit=limit)

        # ── 每周纪行 + 周挑战 (v17) ──

        @self.router.get("/battle-pass")
        async def battle_pass():
            """本周纪行: 积分来自真实游玩数据，达到阈值可领奖励"""
            return self.store.get_battle_pass()

        @self.router.post("/battle-pass/{tier}/claim")
        async def claim_battle_pass_tier(tier: int):
            """领取纪行某一档奖励"""
            result = self.store.claim_battle_pass_tier(tier)
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "领取失败"))
            return result

        @self.router.get("/weekly-challenge")
        async def weekly_challenge():
            """本周挑战: 主题轮换 + 委托完成星级"""
            return self.store.get_weekly_challenge()

        # ── 纪念日 (v17) ──

        @self.router.get("/commemorations")
        async def list_commemorations():
            """纪念日列表 (含距今天数与阶段)"""
            return self.store.list_commemorations()

        @self.router.post("/commemorations")
        async def add_commemoration(request: Dict[str, Any] = None):
            """新增纪念日 (date 格式 MM-DD, 每年循环; 临近自动开限时活动)"""
            request = request or {}
            result = self.store.add_commemoration(
                key=str(request.get("key", "")),
                name=str(request.get("name", "")),
                date=str(request.get("date", "")),
                description=str(request.get("description", "")),
                icon=str(request.get("icon", "✦")),
                lead_days=int(request.get("lead_days", 2)),
            )
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message", "创建失败"))
            return result

        @self.router.put("/commemorations/{key}")
        async def update_commemoration(key: str, request: Dict[str, Any] = None):
            """编辑纪念日 (name/date/description/icon/lead_days/enabled)"""
            memo = self.store.update_commemoration(key, request or {})
            if not memo:
                raise HTTPException(status_code=404, detail="纪念日不存在")
            return memo

        @self.router.delete("/commemorations/{key}")
        async def delete_commemoration(key: str):
            if not self.store.delete_commemoration(key):
                raise HTTPException(status_code=404, detail="纪念日不存在")
            return {"success": True}

        @self.router.post("/commemorations/sync")
        async def sync_commemorations():
            """手动触发纪念日同步 (临近开活动/当天写寄语)。每日仪式会自动执行"""
            return self.store.sync_commemorations()

        # ── 每日日常委托 (v17) ──

        @self.router.post("/quests/generate-daily")
        async def generate_daily_commissions():
            """手动生成今日日常委托 (幂等, 配置 earth_online.daily.*)"""
            return self.store.generate_daily_commissions()

        # ── 汇总 ──

        @self.router.get("/summary")
        async def get_summary():
            """获取地球online 汇总 (玩家状态 + 统计)"""
            return self.store.summary()

    def get_router(self):
        return self.router
