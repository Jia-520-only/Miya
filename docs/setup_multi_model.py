"""
多模型配置助手（厂商无关版本）
灵活配置弥娅系统的多模型，支持自由选择API提供商
"""
import json
import os
from pathlib import Path


# 可用的厂商选项
PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek 官方",
        "description": "https://platform.deepseek.com/",
        "base_url": "https://api.deepseek.com/v1",
        "models": {
            "deepseek-chat": "DeepSeek V3",
            "deepseek-reasoner": "DeepSeek R1"
        }
    },
    "siliconflow": {
        "name": "硅基流动 SiliconFlow",
        "description": "https://cloud.siliconflow.cn/i/pEXepR3y",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": {
            "Qwen/Qwen2.5-7B-Instruct": "Qwen 2.5 7B（免费）",
            "Qwen/Qwen2.5-72B-Instruct": "Qwen 2.5 72B",
            "THUDM/glm-4-9b-chat": "GLM-4 9B",
            "internlm/internlm2_5-7b-chat": "InternLM 2.5 7B（免费）",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B": "DeepSeek R1 Distill 7B（免费）",
            "deepseek-ai/DeepSeek-V3": "DeepSeek V3",
            "meta-llama/Llama-3.1-8B-Instruct": "Llama 3.1 8B（免费）",
            "google/gemma-2-9b-it": "Gemma 2 9B（免费）"
        },
        "free_tokens": "2000万 Tokens（新用户）"
    },
    "dashscope": {
        "name": "阿里云通义千问 DashScope",
        "description": "https://dashscope.aliyun.com/",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": {
            "qwen-plus": "Qwen Plus",
            "qwen-max": "Qwen Max（最强）",
            "qwen-turbo": "Qwen Turbo（快速）"
        }
    },
    "zhipuai": {
        "name": "智谱AI ZhipuAI",
        "description": "https://open.bigmodel.cn/",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": {
            "glm-4": "GLM-4",
            "glm-4-plus": "GLM-4 Plus",
            "glm-3-turbo": "GLM-3 Turbo"
        }
    },
    "groq": {
        "name": "Groq（超高速）",
        "description": "https://console.groq.com/",
        "base_url": "https://api.groq.com/openai/v1",
        "models": {
            "llama-3.1-8b-instant": "Llama 3.1 8B（免费超高速）",
            "llama-3.1-70b-versatile": "Llama 3.1 70B",
            "mixtral-8x7b-32768": "Mixtral 8x7B"
        },
        "free_tokens": "无限免费（限速）"
    },
    "openrouter": {
        "name": "OpenRouter（模型聚合）",
        "description": "https://openrouter.ai/",
        "base_url": "https://openrouter.ai/api/v1",
        "models": {
            "openai/gpt-4o": "GPT-4o",
            "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet",
            "google/gemma-2-9b-it:free": "Gemma 2 9B（免费）",
            "meta-llama/llama-3.1-8b-instruct": "Llama 3.1 8B"
        }
    }
}


def load_config():
    """加载多模型配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'multi_model_config.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(config):
    """保存多模型配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'multi_model_config.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def show_providers():
    """显示可用厂商"""
    print("=" * 70)
    print("可用的API提供商")
    print("=" * 70)
    
    for key, provider in PROVIDERS.items():
        print(f"\n【{key}】{provider['name']}")
        print(f"  描述: {provider['description']}")
        print(f"  Base URL: {provider['base_url']}")
        print(f"  模型:")
        for model_name, model_desc in provider['models'].items():
            print(f"    - {model_name}: {model_desc}")
        if 'free_tokens' in provider:
            print(f"  🎁 免费福利: {provider['free_tokens']}")


def configure_model_slot(model_key):
    """配置单个模型槽位"""
    config = load_config()
    
    if model_key not in config['models']:
        print(f"❌ 未知的模型槽位: {model_key}")
        return False
    
    model_info = config['models'][model_key]
    print(f"\n正在配置: {model_info['description']}")
    print(f"当前配置: {model_info['name']} @ {model_info['base_url']}")
    
    # 检查是否有厂商选项
    if 'model_options' in model_info:
        print("\n可选的提供商:")
        options = list(model_info['model_options'].keys())
        for i, provider_key in enumerate(options, 1):
            option = model_info['model_options'][provider_key]
            print(f"  {i}. {option['description']}")
            print(f"     模型名: {option['name']}")
            print(f"     Base URL: {option['base_url']}")
            print(f"     费用: {option['cost']}")
        
        choice = input("\n请选择提供商 (输入序号或名称，留空保持当前): ").strip()
        
        if choice:
            # 尝试匹配序号
            if choice.isdigit() and 1 <= int(choice) <= len(options):
                provider_key = options[int(choice) - 1]
            else:
                # 尝试匹配名称
                provider_key = choice.lower()
                if provider_key not in options:
                    print(f"❌ 无效的选择")
                    return False
            
            # 应用选择的配置
            selected = model_info['model_options'][provider_key]
            config['models'][model_key]['name'] = selected['name']
            config['models'][model_key]['base_url'] = selected['base_url']
            print(f"✅ 已选择: {selected['description']}")
        
        # 询问 API Key
        api_key = input(f"\n请输入 API Key (留空跳过): ").strip()
        if api_key:
            config['models'][model_key]['api_key'] = api_key
            print(f"✅ API Key 已更新")
    else:
        # DeepSeek 官方模型
        api_key = input(f"\n请输入 DeepSeek API Key (留空跳过): ").strip()
        if api_key:
            config['models'][model_key]['api_key'] = api_key
            print(f"✅ API Key 已更新")
    
    save_config(config)
    return True


def show_config_status():
    """显示配置状态"""
    config = load_config()
    
    print("=" * 70)
    print("弥娅多模型配置状态")
    print("=" * 70)
    
    # 统计配置状态
    total = len(config['models'])
    configured = 0
    providers_used = set()
    
    print("\n【模型槽位配置】")
    for model_key, model_info in config['models'].items():
        api_key = model_info.get('api_key', '')
        base_url = model_info.get('base_url', '')
        
        # 判断配置状态
        if api_key and 'YOUR_' not in api_key and 'YOUR_PROVIDER' not in api_key:
            status = "✅ 已配置"
            configured += 1
        else:
            status = "⚠️ 待配置"
        
        # 识别提供商
        if 'siliconflow' in base_url.lower():
            provider = "硅基流动"
        elif 'deepseek' in base_url.lower():
            provider = "DeepSeek 官方"
        elif 'dashscope' in base_url.lower():
            provider = "阿里云"
        elif 'bigmodel' in base_url.lower():
            provider = "智谱AI"
        elif 'groq' in base_url.lower():
            provider = "Groq"
        elif 'openrouter' in base_url.lower():
            provider = "OpenRouter"
        else:
            provider = "自定义"
        
        providers_used.add(provider)
        
        # 显示模型信息
        model_name = model_info['name']
        if 'YOUR_' in model_name or 'YOUR_PROVIDER' in model_name:
            model_name = "未指定"
        
        print(f"\n  {model_key}:")
        print(f"    描述: {model_info['description']}")
        print(f"    模型: {model_name}")
        print(f"    提供商: {provider}")
        print(f"    Base URL: {base_url}")
        print(f"    状态: {status}")
        
        if status == "✅ 已配置":
            print(f"    API Key: {api_key[:10]}...{api_key[-4:]}")
    
    print("\n" + "=" * 70)
    print(f"配置进度: {configured}/{total} 个模型槽位已配置")
    print(f"使用的提供商: {', '.join(sorted(providers_used))}")
    print("=" * 70)
    
    # 提供推荐
    if configured < total:
        print("\n💡 推荐配置顺序:")
        print("  1. DeepSeek 官方（已有 Key）")
        print("  2. 硅基流动（新用户免费 2000万 Tokens）")
        print("  3. Groq（免费超高速，适合简单任务）")
        print("\n运行此脚本并选择 'configure' 来配置每个槽位")


def quick_configure_all(provider_name):
    """快速配置所有槽位到指定提供商"""
    config = load_config()
    
    provider_name = provider_name.lower()
    if provider_name not in PROVIDERS:
        print(f"❌ 未知的提供商: {provider_name}")
        print(f"可用的提供商: {', '.join(PROVIDERS.keys())}")
        return False
    
    provider = PROVIDERS[provider_name]
    
    print(f"\n正在将所有模型槽位配置到: {provider['name']}")
    api_key = input(f"请输入 {provider['name']} API Key (留空跳过): ").strip()
    
    if not api_key:
        print("❌ API Key 不能为空")
        return False
    
    updated = 0
    for model_key, model_info in config['models'].items():
        # 只更新有 model_options 的模型
        if 'model_options' in model_info and provider_name in model_info['model_options']:
            option = model_info['model_options'][provider_name]
            config['models'][model_key]['name'] = option['name']
            config['models'][model_key]['base_url'] = option['base_url']
            config['models'][model_key]['api_key'] = api_key
            updated += 1
            print(f"  ✓ {model_key} → {option['name']}")
    
    if updated > 0:
        save_config(config)
        print(f"\n✅ 已更新 {updated} 个模型槽位")
    else:
        print("\n⚠️ 该提供商没有可用的模型")
    
    return True


def interactive_setup():
    """交互式配置"""
    print("=" * 70)
    print("弥娅多模型配置助手（厂商无关版本）")
    print("=" * 70)
    print("\n请选择操作:")
    print("1. 查看所有可用提供商")
    print("2. 查看当前配置状态")
    print("3. 配置单个模型槽位")
    print("4. 快速配置：使用 DeepSeek 官方")
    print("5. 快速配置：使用硅基流动")
    print("6. 快速配置：使用 Groq（免费超高速）")
    print("7. 快速配置：使用 OpenRouter（模型聚合）")
    print("0. 退出")

    choice = input("\n请输入选项 (0-7): ").strip()

    if choice == '1':
        show_providers()
    elif choice == '2':
        show_config_status()
    elif choice == '3':
        config = load_config()
        print("\n可配置的模型槽位:")
        for model_key in config['models'].keys():
            model_info = config['models'][model_key]
            status = "✅" if 'YOUR_' not in model_info.get('api_key', '') else "⚠️"
            print(f"  {status} {model_key}: {model_info['description']}")
        
        model_key = input("\n请输入要配置的模型槽位名称: ").strip()
        if model_key:
            configure_model_slot(model_key)
    elif choice == '4':
        quick_configure_all('deepseek')
    elif choice == '5':
        quick_configure_all('siliconflow')
    elif choice == '6':
        quick_configure_all('groq')
    elif choice == '7':
        quick_configure_all('openrouter')
    elif choice == '0':
        print("退出配置助手。")
        return
    else:
        print("❌ 无效的选项")


if __name__ == '__main__':
    # 设置项目根目录
    project_root = Path(__file__).parent
    os.chdir(project_root)

    # 运行交互式配置
    interactive_setup()
