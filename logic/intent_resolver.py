"""
Intent Resolver - Phase-12 (CIL)
Normalizes user instructions into Canonical Intents.
Shields the Planner from conversational/observational/vague queries.
"""
import logging
from typing import Tuple
from logic.intent_types import CanonicalIntent
from logic.dialogue_state import DialogueState

logger = logging.getLogger(__name__)

class IntentResolver:
    def __init__(self, dialogue_state: DialogueState):
        self.state = dialogue_state
        
    def resolve(self, text: str) -> Tuple[CanonicalIntent, str]:
        """
        Map user text to CanonicalIntent.
        Returns (Intent, NormalizedText)
        """
        clean_text = text.lower().strip().rstrip("?.!")
        
        # 1. Check for Observation Intents (Strong Signals)
        # phrases like "what do you see", "describe screen"
        obs_triggers = [
            "what do you see", "what are you seeing", "tell me what you see",
            "describe the screen", "describe screen", "what is on my screen",
            "whats on my screen", "read the screen", "analyze the chart",
            "do you see", "is the app running", "check if",
            "what is on the screen", "whats on the screen"
        ]
        
        # Normalize smart quotes to standard
        clean_text = clean_text.replace("’", "'").replace("“", '"').replace("”", '"')
        
        if any(t in clean_text for t in obs_triggers):
             # Hard rule: If asking about screen content, it is OBSERVE_SCREEN
             return CanonicalIntent.OBSERVE_SCREEN, text

        # 2. Check for Follow-up/Clarification (Context Dependent)
        # "now?", "read it", "explain"
        followup_triggers = [
            "now", "now?", "ok", "then", "what next", "next",
            "read it", "read that", "explain", "details", 
            "what does it say", "raw", "ocr", "summary"
        ]
        
        # Exact match or starts with simple trigger
        is_followup_phrase = clean_text in followup_triggers
        
        # Check pronouns ONLY if not a clear action
        has_pronoun = any(p in clean_text.split() for p in ["it", "this", "that"]) 
        # "type it" -> ACTION (handled below by action verbs)
        # "read it" -> FOLLOWUP (handled above)
        
        if is_followup_phrase:
             # If we have a recent observation, this is likely a drill-down
             if self.state.last_observation:
                 return CanonicalIntent.FOLLOWUP, text
             else:
                 # "Now?" but no history -> treating as "What do you see now?"
                 return CanonicalIntent.OBSERVE_SCREEN, "what do you see now?"

        # 3. MARKET_SCAN: Phase-11.5 multi-instrument scanner
        scan_keywords = ["scan", "scanner", "market scan", "scan market", "nifty 50", "bank nifty", "options scan", "ce pe"]
        has_scan_keyword = any(keyword in clean_text for keyword in scan_keywords)
        
        if has_scan_keyword:
            logger.info(f"Classified as MARKET_SCAN intent (Phase-11.5)")
            return CanonicalIntent.MARKET_SCAN, text

        # 4. MARKET_ANALYSIS: Market/stock analysis requests
        market_keywords = ["analyze", "analysis", "technical analysis", "support", "resistance", "trend", "rsi", "macd", "ema", "tradingview", "phase-3", "phase 3", "phase3", "reasoning", "synthesis", "synthesize", "multi-timeframe", "multi timeframe", "multitimeframe", "mtf", "scenario", "continuation", "pullback", "failure", "dominant", "alignment", "reversion", "stability"]
        trading_keywords = ["buy", "sell", "trade", "execute", "order"]
        action_keywords = ["draw", "mark", "click", "type", "open browser"]
        
        has_market_keyword = any(keyword in clean_text for keyword in market_keywords)
        has_trading_keyword = any(keyword in clean_text for keyword in trading_keywords)
        has_action_keyword = any(keyword in clean_text for keyword in action_keywords)
        
        # Classify as MARKET_ANALYSIS if:
        # - Has market keyword AND
        # - Does NOT have trading keyword AND
        # - Does NOT have action keyword
        if has_market_keyword and not has_trading_keyword and not has_action_keyword:
            logger.info(f"Classified as MARKET_ANALYSIS intent (market_keyword={has_market_keyword}, no trading/action keywords)")
            return CanonicalIntent.MARKET_ANALYSIS, text
        
        # 5. Check for Actions (The rest)
        # We assume if it's not strictly observation or fluffy follow-up, it's a request for action.
        # But we can be smarter.
        
        action_verbs = ["open", "close", "type", "click", "save", "select", "launch", "run", "wait"]
        if any(clean_text.startswith(v) for v in action_verbs):
            if " and " in clean_text or " then " in clean_text:
                return CanonicalIntent.ACTION_COMPOSITE, text
            return CanonicalIntent.ACTION, text

        # 5. Fallback Logic for queries like "can you describe what is in the screen"
        # The first check might miss "can you..." prefix or variations
        # Expanded Heuristic: (Question Word + Visual Target)
        if ("describe" in clean_text or "tell me" in clean_text or "what is" in clean_text) and \
           ("screen" in clean_text or "window" in clean_text or "see" in clean_text):
            return CanonicalIntent.OBSERVE_SCREEN, text

        # Default to ACTION (Planner will try to handle it, or fail)
        # But for safety, if it looks like a question, maybe unknown?
        if clean_text.startswith("can you ") or clean_text.startswith("how do i"):
            # "can you open notepad" -> ACTION
             if any(v in clean_text for v in action_verbs):
                 return CanonicalIntent.ACTION, text
             # "can you see the button" -> OBSERVE
             if "see" in clean_text:
                 return CanonicalIntent.OBSERVE_SCREEN, text
                 
        return CanonicalIntent.ACTION, text
