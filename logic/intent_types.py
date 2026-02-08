from enum import Enum

class CanonicalIntent(Enum):
    ACTION = "action"                  # Explicit command to change state (open, type, click)
    ACTION_COMPOSITE = "action_composite" # Multi-step action (save and close)
    OBSERVE_SCREEN = "observe_screen"  # Request to perceive current state (what do you see)
    MARKET_ANALYSIS = "market_analysis" # Market analysis request (analyze stock, technical analysis)
    MARKET_SCAN = "market_scan"        # Multi-instrument market scan (Phase-11.5)
    FOLLOWUP = "followup"              # Reference to past context (read it, explain that)
    GREETING = "greeting"              # Social (hello)
    UNKNOWN = "unknown"                # Fallback for planner
