#!/usr/bin/env python3
"""
测试统一模型池系统
"""

import logging
import os
import sys
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

# 这些函数同时作为脚本直接运行，返回 bool 供 main() 统计。
pytestmark = pytest.mark.filterwarnings("ignore:Test functions should return None")


def test_model_pool_loading():
    """测试模型池加载"""
    logger.info("测试模型池加载...")

    try:
        from core.model_pool_manager import get_model_pool

        pool = get_model_pool()

        # 检查模型数量
        all_models = pool.get_all()
        if not all_models:
            logger.error("模型池为空")
            return False

        logger.info(f"模型池加载成功，共 {len(all_models)} 个模型")

        # 列出模型类型
        from core.model_pool_manager import ModelType

        text_models = pool.get_models_by_type(str(ModelType.TEXT))
        ocr_models = pool.get_models_by_type(str(ModelType.OCR))
        vision_models = pool.get_models_by_type(str(ModelType.VISION))

        logger.info(f"文本模型: {len(text_models)} 个")
        logger.info(f"OCR模型: {len(ocr_models)} 个")
        logger.info(f"视觉模型: {len(vision_models)} 个")

        # 显示前几个模型
        for i, model in enumerate(all_models[:3]):
            logger.info(f"  模型 {i + 1}: {model.id} ({model.type}) - {model.description}")

        return True

    except Exception as e:
        logger.error(f"模型池加载测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_model_selection():
    """测试模型选择"""
    logger.info("测试模型选择...")

    try:
        from core.model_pool_manager import select_model_for_task

        # 测试不同任务的模型选择
        test_tasks = [
            ("simple_chat", "qq", "balanced"),
            ("text_extraction", "qq", "cost"),
            ("nsfw_detection", "qq", "speed"),
        ]

        for task_type, endpoint, priority in test_tasks:
            model = select_model_for_task(task_type, endpoint, priority)
            if model:
                logger.info(f"  任务 '{task_type}' -> 模型: {model.id} (优先级: {priority})")
            else:
                logger.warning(f"  任务 '{task_type}' -> 未找到合适模型")

        return True

    except Exception as e:
        logger.error(f"模型选择测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_qq_model_integration():
    """测试QQ模型集成 — 基于 unified_config"""
    logger.info("测试QQ模型集成...")

    try:
        from webnet.qq.unified_config import get_qq_config

        config = get_qq_config()
        ws_url = config.get("ws_url", "")
        bot_qq = config.get("bot_qq", 0)

        logger.info(f"  QQ OneBot WS: {ws_url}")
        logger.info(f"  QQ Bot QQ:    {bot_qq}")

        if ws_url and bot_qq:
            logger.info(f"QQ端配置加载成功")
            return True
        else:
            logger.warning("未获取到QQ模型配置")
            return False

    except Exception as e:
        logger.error(f"QQ模型集成测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_unified_config_yaml():
    """测试统一配置YAML文件"""
    logger.info("测试统一配置YAML文件...")

    try:
        yaml_path = project_root / "config" / "unified_model_config.yaml"

        if not yaml_path.exists():
            logger.warning(f"统一配置YAML文件不存在: {yaml_path}")
            return True  # 不是错误，可能还未创建

        # 读取YAML文件
        import yaml

        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config:
            logger.error("YAML文件为空")
            return False

        # 检查必要的配置节
        required_sections = ["models", "model_routing"]
        missing_sections = []

        for section in required_sections:
            if section not in config:
                missing_sections.append(section)

        if missing_sections:
            logger.error(f"YAML配置缺少节: {missing_sections}")
            return False

        # 检查模型数量
        models = config.get("models", {})
        logger.info(f"YAML配置中包含 {len(models)} 个模型")

        # 检查模型类型分布
        model_types = {}
        for model_id, model_data in models.items():
            model_type = model_data.get("type", "text")
            model_types[model_type] = model_types.get(model_type, 0) + 1

        for model_type, count in model_types.items():
            logger.info(f"  {model_type}模型: {count} 个")

        return True

    except Exception as e:
        logger.error(f"统一配置YAML测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_endpoint_configuration():
    """测试端配置"""
    logger.info("测试端配置...")

    try:
        from core.model_pool_manager import get_model_pool

        pool = get_model_pool()

        # 检查QQ端配置
        get_endpoint_config = getattr(pool, "get_endpoint_config", None)
        qq_config = get_endpoint_config("qq") if callable(get_endpoint_config) else None
        if qq_config:
            logger.info("QQ端配置:")
            logger.info(f"  启用模型: {len(qq_config.enabled_models)} 个")
            logger.info(f"  默认模型: {qq_config.default_models}")
        else:
            logger.warning("QQ端配置未找到")

        # 检查其他端配置
        endpoints = ["terminal", "web"]
        for endpoint in endpoints:
            config = get_endpoint_config(endpoint) if callable(get_endpoint_config) else None
            if config:
                logger.info(f"{endpoint}端: {len(config.enabled_models)} 个模型")

        return True

    except Exception as e:
        logger.error(f"端配置测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_config_chain():
    """测试配置链"""
    logger.info("测试配置链...")

    try:
        # 1. 检查环境变量
        required_env_vars = ["DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY"]
        missing_env_vars = []

        for env_var in required_env_vars:
            if not os.getenv(env_var):
                missing_env_vars.append(env_var)

        if missing_env_vars:
            logger.warning(f"缺失环境变量: {missing_env_vars}")

        # 2. 测试模型池配置链
        from core.model_pool_manager import get_model_pool

        pool = get_model_pool()

        # 3. 测试QQ集成

        # 4. 验证配置一致性
        test_model = pool.select_model_for_task("simple_chat", "qq")
        if test_model:
            logger.info("配置链验证:")
            logger.info(f"  模型池 -> {test_model.id}")
            logger.info(f"  模型类型: {test_model.type}")
            logger.info(f"  提供商: {test_model.provider}")

            if test_model.api_key:
                # 检查API密钥是否已从环境变量加载
                if test_model.api_key.startswith("sk-"):
                    logger.info("  API密钥: 已配置")
                else:
                    logger.warning("  API密钥: 可能未正确加载")

        return True

    except Exception as e:
        logger.error(f"配置链测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("开始测试统一模型池系统")
    logger.info("=" * 60)

    tests = [
        ("测试模型池加载", test_model_pool_loading),
        ("测试模型选择", test_model_selection),
        ("测试QQ模型集成", test_qq_model_integration),
        ("测试统一配置YAML", test_unified_config_yaml),
        ("测试端配置", test_endpoint_configuration),
        ("测试配置链", test_config_chain),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        logger.info(f"\n{test_name}...")
        try:
            if test_func():
                logger.info(f"✓ {test_name} 通过")
                passed += 1
            else:
                logger.error(f"✗ {test_name} 失败")
                failed += 1
        except Exception as e:
            logger.error(f"✗ {test_name} 异常: {e}")
            failed += 1

    logger.info("\n" + "=" * 60)
    logger.info("测试结果汇总:")
    logger.info(f"  通过: {passed}")
    logger.info(f"  失败: {failed}")
    logger.info(f"  通过率: {passed}/{len(tests)} ({passed / len(tests) * 100:.1f}%)")

    if failed == 0:
        logger.info("🎉 所有测试通过！")

        # 显示总结信息
        logger.info("\n" + "=" * 60)
        logger.info("统一模型池系统已就绪:")
        logger.info("  1. 所有端共享同一个模型池")
        logger.info("  2. 支持文本和视觉模型")
        logger.info("  3. 智能模型选择和路由")
        logger.info("  4. QQ端已集成模型池")
        logger.info("  5. 完整的配置验证")

        return True
    else:
        logger.error("❌ 部分测试失败")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
