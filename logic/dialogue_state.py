"""
Dialogue State - Phase-12 (CIL)
Single source of conversational truth. Tracks context, intents, and resolves follow-ups.

Responsibilities:
- Maintain last observation, user intent, agent response
- Resolve pronouns ("it", "this", "that")
- Handle conversational flow (clarifications, continuations)
"""
import logging
from typing import Optional, Dict, Any, Union
from common.observations import ObservationResult

logger = logging.getLogger(__name__)

CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"

class DialogueState:
    def __init__(self):
        self.last_observation: Optional[ObservationResult] = None
        self.last_user_intent: Optional[str] = None # Raw text
        self.last_canonical_intent: Optional[str] = None # Enum value
        self.last_agent_response: Optional[str] = None
        self.history: list = [] # [(role, content), ...]

    def update_observation(self, result: ObservationResult):
        """Update state with new observation."""
        if result.status == "success":
            self.last_observation = result

    def update_interaction(self, user_input: str, canonical_intent: str, agent_response: str):
        """Update state with completed interaction."""
        self.last_user_intent = user_input
        self.last_canonical_intent = canonical_intent
        self.last_agent_response = agent_response
        self.history.append(("user", user_input))
        self.history.append(("agent", agent_response))

    # DEPRECATED: Logic moved to IntentResolver
    # def resolve_intent(self, instruction: str) -> Union[str, object]:
    #     """
    #     Resolve user instruction based on context.
    #     Returns rewriten instruction OR CLARIFICATION_REQUIRED.
    #     """
    #     text = instruction.strip().lower().rstrip("?")
    #     # ... rest of deprecated function ...

    # DEPRECATED helper methods (moved to IntentResolver)
    # def _is_followup(self, text: str) -> bool: ...
    # def _is_detail_request(self, text: str) -> bool: ...
    # def _is_raw_request(self, text: str) -> bool: ...
    # def _is_summary_request(self, text: str) -> bool: ...
