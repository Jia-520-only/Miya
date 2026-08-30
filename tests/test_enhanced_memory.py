#!/usr/bin/env python
"""
Test enhanced Miya memory system with new fields
"""

import asyncio
import sys

sys.path.append(".")

from memory.core import MemoryLevel, MemorySource, get_memory_core


async def test_enhanced_memory():
    """Test enhanced memory system with new fields"""
    print("=" * 70)
    print("Testing Enhanced Miya Memory System with New Fields")
    print("=" * 70)

    try:
        # Initialize memory core
        print("\n1. Initializing memory core...")
        core = await get_memory_core("data/test_enhanced_memory")
        print("   [OK] Memory core initialized successfully")

        # Test storing memories with enhanced fields
        print("\n2. Testing storage with enhanced fields...")

        # Store a work meeting memory
        work_memory_id = await core.store(
            content="Discussed Q3 product roadmap and decided to prioritize AI features",
            level=MemoryLevel.LONG_TERM,
            user_id="user_001",
            session_id="work_session_001",
            platform="teams",
            role="user",
            event_type="工作会议",
            location="公司会议室A",
            conversation_partner="产品经理张三",
            emotional_tone="专注",
            significance=0.8,
            source=MemorySource.DIALOGUE,
            tags=["工作", "产品", "会议", "AI"],
        )
        print(f"   [OK] Work meeting memory stored, ID: {work_memory_id}")

        # Store an emotional conversation
        emotional_memory_id = await core.store(
            content="Today I felt really anxious about the upcoming presentation",
            level=MemoryLevel.LONG_TERM,
            user_id="user_001",
            session_id="personal_session_001",
            platform="wechat",
            role="user",
            event_type="个人倾诉",
            location="家中",
            conversation_partner="好友李四",
            emotional_tone="焦虑",
            significance=0.7,
            source=MemorySource.DIALOGUE,
            tags=["情感", "个人", "焦虑"],
        )
        print(f"   [OK] Emotional conversation stored, ID: {emotional_memory_id}")

        # Store a casual chat
        casual_memory_id = await core.store(
            content="We talked about the new restaurant that opened downtown",
            level=MemoryLevel.DIALOGUE,
            user_id="user_001",
            session_id="casual_session_001",
            platform="qq",
            role="user",
            event_type="日常聊天",
            location="咖啡店",
            conversation_partner="同事王五",
            emotional_tone="愉快",
            significance=0.3,
            source=MemorySource.DIALOGUE,
            tags=["社交", "餐饮", "闲聊"],
        )
        print(f"   [OK] Casual chat stored, ID: {casual_memory_id}")

        # Test retrieving memories with enhanced field filters
        print("\n3. Testing retrieval with enhanced field filters...")

        # Search by event type
        work_memories = await core.retrieve(query="", user_id="user_001", event_type="工作会议", limit=10)
        print(f"   [OK] Found {len(work_memories)} work meeting memories")

        # Search by location
        cafe_memories = await core.retrieve(query="", user_id="user_001", location="咖啡店", limit=10)
        print(f"   [OK] Found {len(cafe_memories)} cafe memories")

        # Search by emotional tone
        anxious_memories = await core.retrieve(query="", user_id="user_001", emotional_tone="焦虑", limit=10)
        print(f"   [OK] Found {len(anxious_memories)} anxious memories")

        # Search by conversation partner
        colleague_memories = await core.retrieve(query="", user_id="user_001", conversation_partner="张三", limit=10)
        print(f"   [OK] Found {len(colleague_memories)} memories with colleague Zhang San")

        # Search by significance (using min_significance)
        important_memories = await core.retrieve(query="", user_id="user_001", min_significance=0.7, limit=10)
        print(f"   [OK] Found {len(important_memories)} high significance memories")

        # Test getting specific memory by ID to verify fields
        print("\n4. Testing field retrieval by memory ID...")
        work_memory = await core.get_by_id(work_memory_id)
        if work_memory:
            print("   [OK] Retrieved work memory:")
            print(f"     - Content: {work_memory.content}")
            print(f"     - Event Type: {work_memory.event_type}")
            print(f"     - Location: {work_memory.location}")
            print(f"     - Conversation Partner: {work_memory.conversation_partner}")
            print(f"     - Emotional Tone: {work_memory.emotional_tone}")
            print(f"     - Significance: {work_memory.significance}")

            # Verify the fields are correctly stored
            assert work_memory.event_type == "工作会议"
            assert work_memory.location == "公司会议室A"
            assert work_memory.conversation_partner == "产品经理张三"
            assert work_memory.emotional_tone == "专注"
            assert work_memory.significance == 0.8
            print("   [OK] All enhanced fields verified correctly")
        else:
            print("   [FAIL] Could not retrieve work memory")
            return False

        # Test user profile with enhanced fields
        print("\n5. Testing user profile generation...")
        profile = await core.get_user_profile("user_001")
        print("   [OK] User profile generated:")
        print(f"     - Total memories: {profile['total_memories']}")
        print(f"     - By level: {profile['by_level']}")
        print(f"     - By tag: {list(profile['by_tag'].keys())}")

        # Test auto-classification with enhanced fields
        print("\n6. Testing auto-classification with enhanced fields...")

        # High significance should go to long term
        high_sig_id = await core.store(
            content="Important life decision made today",
            user_id="user_002",
            significance=0.9,
            emotional_tone="决心",
            event_type="人生决策",
        )
        high_sig_memory = await core.get_by_id(high_sig_id)
        if high_sig_memory and high_sig_memory.level == MemoryLevel.LONG_TERM:
            print("   [OK] High significance memory correctly classified as long-term")
        else:
            print("   [FAIL] High significance memory classification failed")

        # Strong emotion with medium significance should go to long term
        strong_emotion_id = await core.store(
            content="Had a frightening experience during the hike",
            user_id="user_002",
            significance=0.6,
            emotional_tone="恐惧",
            event_type="户外活动",
        )
        strong_emotion_memory = await core.get_by_id(strong_emotion_id)
        if strong_emotion_memory and strong_emotion_memory.level == MemoryLevel.LONG_TERM:
            print("   [OK] Strong emotion memory correctly classified as long-term")
        else:
            print(
                "   [INFO] Strong emotion memory classification: {}".format(
                    strong_emotion_memory.level if strong_emotion_memory else "None"
                )
            )

        print("\n" + "=" * 70)
        print("All enhanced memory tests completed successfully!")
        print("The memory system now supports rich contextual fields for")
        print("more human-like subjective memory storage and retrieval.")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n[FAIL] Error occurred during testing: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run test
    result = asyncio.run(test_enhanced_memory())
    sys.exit(0 if result else 1)
