"""
Quick import test for MIYA
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("Testing imports...")

try:
    print("[1/5] Importing core modules...")
    from core import Personality, Ethics, Identity, Arbitrator, Entropy
    print("  OK")
except Exception as e:
    print(f"  FAILED: {e}")
    sys.exit(1)

try:
    print("[2/5] Importing hub modules...")
    from hub import MemoryEmotion, MemoryEngine, Emotion, Decision, Scheduler
    print("  OK")
except Exception as e:
    print(f"  FAILED: {e}")
    sys.exit(1)

try:
    print("[3/5] Importing mlink modules...")
    from mlink import MLinkCore, Message, Router
    print("  OK")
except Exception as e:
    print(f"  FAILED: {e}")
    sys.exit(1)

try:
    print("[4/5] Importing perceive modules...")
    from perceive import PerceptualRing, AttentionGate
    print("  OK")
except Exception as e:
    print(f"  FAILED: {e}")
    sys.exit(1)

try:
    print("[5/5] Importing webnet modules...")
    from webnet import NetManager, CrossNetEngine
    print("  OK")
except Exception as e:
    print(f"  FAILED: {e}")
    sys.exit(1)

print("\n✓ All imports successful!")
print("\nMIYA is ready to launch!")
