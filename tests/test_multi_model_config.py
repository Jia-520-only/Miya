"""
测试多模型管理器
"""
import asyncio
import logging
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.multi_model_manager import MultiModelManager, TaskType
from core.ai_client import AIClientFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_multi_model():
    """测试多模型管理器"""

    # 加载配置
    config_path = Path(__file__).parent.parent / 'config' / 'multi_model_config.json'

    import json
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    logger.info("=== 多模型配置测试 ===\n")

    # 显示配置的模型
    logger.info("已配置的模型:")
    models_config = config.get('models', {})
    for model_key, model_info in models_config.items():
        logger.info(f"  - {model_key}:")
        logger.info(f"      名称: {model_info.get('name')}")
        logger.info(f"      提供商: {model_info.get('provider')}")
        logger.info(f"      API: {model_info.get('base_url', 'N/A')}")
        logger.info(f"      能力: {', '.join(model_info.get('capabilities', []))}")
        logger.info(f"      延迟: {model_info.get('latency')}")
        logger.info(f"      质量: {model_info.get('quality')}")
        logger.info(f"      成本: ${model_info.get('cost_per_1k_tokens', {}).get('input', 0):.6f}/1K 输入")
        logger.info("")

    # 创建模型客户端
    logger.info("初始化模型客户端...\n")
    model_clients = {}

    for model_key, model_info in models_config.items():
        provider = model_info.get('provider', 'openai')
        api_key = model_info.get('api_key', '')
        model_name = model_info.get('name', '')
        base_url = model_info.get('base_url', '')

        if not api_key or not model_name:
            logger.warning(f"  ⚠️ {model_key} 未配置 API 密钥或模型名称，跳过")
            continue

        try:
            client = AIClientFactory.create_client(
                provider=provider,
                api_key=api_key,
                model=model_name,
                base_url=base_url,
                temperature=0.7,
                max_tokens=2000
            )

            if client and hasattr(client, 'client') and client.client is not None:
                model_clients[model_key] = client
                logger.info(f"  ✅ {model_key}: {model_name} 初始化成功")
            else:
                logger.warning(f"  ❌ {model_key}: {model_name} 初始化失败")
        except Exception as e:
            logger.error(f"  ❌ {model_key}: 初始化异常 - {e}")

    logger.info(f"\n成功初始化 {len(model_clients)} 个模型客户端\n")

    # 创建多模型管理器
    if model_clients:
        manager = MultiModelManager(
            model_clients=model_clients,
            config_path=str(config_path)
        )
        logger.info("✅ 多模型管理器初始化成功\n")

        # 测试任务分类
        logger.info("=== 任务分类测试 ===\n")

        test_inputs = [
            "你好",
            "帮我关闭火狐浏览器",
            "写一个Python函数来排序列表",
            "分析这个代码的性能问题",
            "创作一首关于春天的诗",
            "总结这篇文章的内容",
            "检查一下你的配置文件，看看有几个大模型配置"
        ]

        for test_input in test_inputs:
            task_type = await manager.classify_task(test_input)
            model_key, client = await manager.select_model(task_type)
            model_name = client.model if client else "无"
            logger.info(f"输入: {test_input}")
            logger.info(f"  任务类型: {task_type.value}")
            logger.info(f"  选择模型: {model_key} ({model_name})")
            logger.info("")

        # 显示路由策略
        logger.info("=== 路由策略概览 ===\n")
        routing_strategy = config.get('routing_strategy', {})
        for task_type_key, strategy in routing_strategy.items():
            logger.info(f"{task_type_key}:")
            logger.info(f"  主模型: {strategy.get('primary')}")
            logger.info(f"  回退模型: {strategy.get('fallback')}")
            logger.info(f"  次选模型: {strategy.get('secondary')}")
            logger.info(f"  成本优先级: {strategy.get('cost_priority')}")
            logger.info(f"  速度优先级: {strategy.get('speed_priority')}")
            logger.info(f"  质量优先级: {strategy.get('quality_priority')}")
            logger.info("")

        # 显示预算控制
        logger.info("=== 预算控制配置 ===\n")
        budget_control = config.get('budget_control', {})
        logger.info(f"日预算: ${budget_control.get('daily_budget_usd', 0):.2f}")
        logger.info(f"月预算: ${budget_control.get('monthly_budget_usd', 0):.2f}")
        logger.info(f"告警阈值: {budget_control.get('alert_threshold', 0)*100:.0f}%")
        logger.info(f"停止阈值: {budget_control.get('stop_threshold', 0)*100:.0f}%")
        logger.info("")

    else:
        logger.error("❌ 没有成功初始化任何模型客户端")


if __name__ == '__main__':
    asyncio.run(test_multi_model())
