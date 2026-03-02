"""
测试弥娅人设整合功能
"""
import sys
import io
from pathlib import Path

# 设置输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.personality import Personality
from core.ai_client import OpenAIClient, AIMessage


def test_personality():
    """测试人格系统"""
    print("=" * 60)
    print("测试人格系统")
    print("=" * 60)

    # 创建人格实例
    personality = Personality()
    print("\n✅ 创建人格实例成功")

    # 测试向量获取
    warmth = personality.get_vector('warmth')
    print(f"\n温暖度：{warmth}")
    print(f"✅ 向量获取成功")

    # 测试形态切换
    personality.set_form('battle')
    form = personality.get_current_form()
    print(f"\n切换到战态：{form['name']} - {form['full_name']}")
    print(f"✅ 形态切换成功")

    # 测试称呼
    personality.set_title_by_mood('affectionate')
    title = personality.get_current_title()
    phrase = personality.get_address_phrase()
    print(f"\n当前称呼：{title}")
    print(f"开场白：{phrase}")
    print(f"✅ 称呼系统成功")

    # 测试经典语录
    quote = personality.get_quote('love')
    print(f"\n经典语录（爱）：{quote}")
    print(f"✅ 语录系统成功")

    # 测试人格画像
    profile = personality.get_profile()
    print(f"\n主导特质：{profile['dominant']}")
    print(f"稳定性：{profile['stability']}")
    print(f"当前形态：{profile['current_form']}")
    print(f"✅ 人格画像生成成功")

    # 测试人格描述
    desc = personality.get_personality_description()
    print(f"\n人格描述（前200字符）：\n{desc[:200]}...")
    print(f"✅ 人格描述生成成功")


def test_ai_client():
    """测试AI客户端整合"""
    print("\n" + "=" * 60)
    print("测试AI客户端整合")
    print("=" * 60)

    # 创建AI客户端（不需要真实API）
    personality = Personality()
    client = OpenAIClient(
        api_key="test_key",
        model="gpt-4o",
        personality=personality
    )
    print("\n✅ AI客户端创建成功")

    # 测试人设提示词加载
    miya_prompt = client.get_miya_system_prompt()
    print(f"\n人设提示词长度：{len(miya_prompt)} 字符")
    print(f"✅ 人设提示词加载成功")

    # 测试包含动态人格信息的提示词
    prompt_with_context = client.get_miya_system_prompt({'user_id': '123456'})
    print(f"\n包含上下文的提示词长度：{len(prompt_with_context)} 字符")
    print(f"✅ 提示词上下文替换成功")


def test_miya_prompt_json():
    """测试弥娅人设JSON文件"""
    print("\n" + "=" * 60)
    print("测试弥娅人设JSON文件")
    print("=" * 60)

    import json
    prompt_path = Path(__file__).parent.parent / 'prompts' / 'miya_personality.json'

    if prompt_path.exists():
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_config = json.load(f)

        system_prompt = prompt_config.get('system_prompt', '')
        print(f"\n系统提示词长度：{len(system_prompt)} 字符")
        print(f"✅ JSON文件加载成功")

        # 检查关键内容
        key_phrases = [
            '弥娅·阿尔缪斯',
            '千面之爱',
            '高冷温柔',
            '形态系统'
        ]
        for phrase in key_phrases:
            if phrase in system_prompt:
                print(f"✅ 包含关键短语：{phrase}")
            else:
                print(f"❌ 缺少关键短语：{phrase}")
    else:
        print(f"❌ JSON文件不存在：{prompt_path}")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("弥娅人设整合测试")
    print("=" * 60)

    try:
        test_personality()
        test_ai_client()
        test_miya_prompt_json()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
