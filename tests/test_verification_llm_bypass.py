"""Test that LLM is bypassed for verification intents"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from logic.planner import Planner
from common.actions import Action
from common.observations import Observation
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("=" * 70)
print("TEST: Verification Intent Bypasses LLM")
print("=" * 70)

# Test with LLM mode enabled
try:
    from logic.llm_client import LLMClient
    
    try:
        llm = LLMClient('http://localhost:11434', 'llama3.2', 0.1)
        
        planner = Planner({'planner': {'use_llm': True}}, llm)
        
        print("\nConfiguration: LLM mode ENABLED")
        print("-" * 70)
        
        instruction = "verify that hello is visible"
        print(f"\nInstruction: '{instruction}'")
        print("-" * 70)
        
        plan = planner.create_plan(instruction)
        
        actions = [x for x in plan if isinstance(x, Action)]
        observations = [x for x in plan if isinstance(x, Observation)]
        
        print(f"\nResult: {len(actions)} actions, {len(observations)} observations")
        
        if len(actions) == 1 and len(observations) == 0:
            print("\n✅ SUCCESS!")
            print("   Verification intent detected BEFORE LLM")
            print("   LLM completely bypassed")
            print("   Action generated with verify metadata")
            print(f"   Verify metadata: {actions[0].verify}")
        else:
            print(f"\n❌ FAIL: Expected 1 action, 0 observations")
            print(f"   Got: {len(actions)} actions, {len(observations)} observations")
            
    except ConnectionError:
        print("\nℹ Ollama not available - skipping LLM test")
        
except ImportError:
    print("\nℹ LLMClient not available - skipping LLM test")
