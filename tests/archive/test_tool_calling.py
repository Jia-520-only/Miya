"""
测试 DeepSeek Function Calling
验证工具调用是否正常工作
"""
import asyncio
import json
import os
from openai import AsyncOpenAI

async def test_simple_tool_calling():
    """测试简单的工具调用"""

    # 从环境变量获取 API key
    api_key = os.getenv('DEEPSEEK_API_KEY', '')

    if not api_key:
        # 尝试从配置文件读取
        try:
            from dotenv import load_dotenv
            load_dotenv('config/.env')
            api_key = os.getenv('DEEPSEEK_API_KEY', '')
        except:
            pass

    if not api_key:
        print("❌ 无法获取 API Key")
        return

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    # 定义一个简单的工具
    tools = [
        {
            "type": "function",
            "function": {
                "name": "start_trpg",
                "description": "启动 TRPG 跑团模式。当用户说 '启动跑团'、'开始跑团'、'进入跑团模式'、'/trpg coc7'、'/trpg dnd5e'、'COC7跑团'、'DND5E跑团'、'跑团'、'COC7'、'DND5E'、'主持游戏'、'KP'、'守秘人'、'start_trpg'、'启动COC7跑团模式'、'你作为KP开始主持游戏' 等关键词时调用此工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rule_system": {
                            "type": "string",
                            "enum": ["coc7", "dnd5e"],
                            "description": "规则系统（coc7 或 dnd5e）"
                        },
                        "session_name": {
                            "type": "string",
                            "description": "团名称（可选）"
                        }
                    }
                }
            }
        }
    ]

    # 测试消息
    test_messages = [
        {"role": "user", "content": "启动COC7跑团模式"}
    ]

    print("=" * 60)
    print("测试 1: 简单系统提示词")
    print("=" * 60)

    messages = [
        {"role": "system", "content": "你是一个游戏助手。当用户要求启动跑团时，必须调用 start_trpg 工具。"},
        {"role": "user", "content": "启动COC7跑团模式"}
    ]

    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        message = response.choices[0].message

        if message.tool_calls:
            print(f"✅ 工具调用成功！")
            print(f"调用的工具: {[tc.function.name for tc in message.tool_calls]}")
            print(f"参数: {message.tool_calls[0].function.arguments}")
        else:
            print(f"❌ 未调用工具")
            print(f"返回内容: {message.content[:200]}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")

    print("\n" + "=" * 60)
    print("测试 2: 使用 tool_choice='required'")
    print("=" * 60)

    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="required"
        )

        message = response.choices[0].message

        if message.tool_calls:
            print(f"✅ 工具调用成功！")
            print(f"调用的工具: {[tc.function.name for tc in message.tool_calls]}")
            print(f"参数: {message.tool_calls[0].function.arguments}")
        else:
            print(f"❌ 未调用工具")
            print(f"返回内容: {message.content[:200]}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")

    print("\n" + "=" * 60)
    print("测试 3: 用户原始消息")
    print("=" * 60)

    messages = [
        {"role": "system", "content": "你是弥娅，一个游戏助手。当用户要求启动跑团时，必须调用 start_trpg 工具。"},
        {"role": "user", "content": "弥娅，启动COC7跑团模式，你作为KP开始主持游戏"}
    ]

    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        message = response.choices[0].message

        if message.tool_calls:
            print(f"✅ 工具调用成功！")
            print(f"调用的工具: {[tc.function.name for tc in message.tool_calls]}")
            print(f"参数: {message.tool_calls[0].function.arguments}")
        else:
            print(f"❌ 未调用工具")
            print(f"返回内容: {message.content[:200]}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")

    print("\n" + "=" * 60)
    print("测试 4: 使用 deepseek-reasoner 模型")
    print("=" * 60)

    try:
        response = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        message = response.choices[0].message

        if message.tool_calls:
            print(f"✅ 工具调用成功！")
            print(f"调用的工具: {[tc.function.name for tc in message.tool_calls]}")
            print(f"参数: {message.tool_calls[0].function.arguments}")
        else:
            print(f"❌ 未调用工具")
            print(f"返回内容: {message.content[:200]}")
    except Exception as e:
        print(f"❌ 请求失败: {e}")

    await client.close()

if __name__ == "__main__":
    asyncio.run(test_simple_tool_calling())
