"""
LLM Planner - Phase-6 Brain
Generates structured plans (Actions + Observations) from natural language instructions.

Refactored from logic/llm_client.py to separate Network vs Logic.
"""
import logging
import json
from typing import List, Union, Dict, Any, Optional
from common.actions import Action
from common.observations import Observation, ObservationResult
from logic.llm_client import LLMClient

logger = logging.getLogger(__name__)

class LLMPlanner:
    """
    Reasoning engine that converts text instructions into structured Action/Observation plans.
    Uses LLMClient for the raw generation but owns the Prompt Engineering and Schema Validation.
    """

    def __init__(self, llm_client: LLMClient):
        """
        Initialize the planner.
        
        Args:
            llm_client: Initialized LLMClient for network calls
        """
        self.llm = llm_client
        logger.info("LLMPlanner initialized")

    def generate_plan(self, instruction: str, max_actions: int = 5, context: Optional[List[ObservationResult]] = None) -> List[Union[Action, Observation]]:
        """
        Generate an action plan from a natural language instruction.
        
        Phase-11: Vision-Aware Reasoning.
        Inputs may include ObservationResult context (especially from Vision).
        
        Args:
            instruction: User's natural language task
            max_actions: Maximum number of items allowed (actions + observations)
            context: Optional list of ObservationResults to inform the plan
            
        Returns:
            List of Action and/or Observation objects
            
        Raises:
            ValueError: If LLM output is malformed or unsafe
            ConnectionError: If LLMClient fails
        """
        logger.info(f"Generating LLM plan for: {instruction}")
        
        # Build system prompt
        system_prompt = self._build_system_prompt(max_actions)
        
        # Build user prompt with context if available
        context_str = ""
        if context:
            context_str = "\nCONTEXT FROM OBSERVATIONS:\n"
            for obs in context:
                # Format vision result with confidence warnings
                if obs.metadata and obs.metadata.get("source") == "vision_llm":
                    confidence = obs.metadata.get("confidence", 0)
                    context_str += f"- [VISION (Confidence: {confidence})]: {obs.result}\n"
                else:
                    context_str += f"- [{obs.observation.observation_type}]: {obs.result}\n"
            context_str += "\nUSE THIS CONTEXT to inform your plan. If Vision confidence is low (<=0.7) and uncorroborated, you MUST act cautiously.\n"

        user_prompt = f"Instruction: {instruction}\n{context_str}\nGenerate the action plan:"
        
        # Call LLM
        try:
            # Note: We rely on llm_client.generate_completion (to be refactored)
            response = self.llm.generate_completion(system_prompt, user_prompt)
            
            # Parse response into Actions/Observations
            plan = self._parse_response(response, max_actions)
            
            logger.info(f"LLM generated {len(plan)} item(s)")
            return plan
            
        except Exception as e:
            logger.error(f"LLM plan generation failed: {e}", exc_info=True)
            raise ValueError(f"Could not generate safe plan: {e}")

    def _build_system_prompt(self, max_actions: int) -> str:
        """Build the system prompt for structured output."""
        return f"""You are an action planner for a desktop automation agent with multi-context support.

STRICT OUTPUT CONTRACT:
- Output ONLY a valid JSON array of objects.
- NO explanations, NO markdown, NO additional text.
- Each object MUST be a valid JSON object with keys and values.
- DO NOT produce invalid JSON like {{"...": "...", "^s"}} (missing key).
- Maximum {max_actions} actions per plan.
- DO NOT include comments or markdown blocks (e.g. ```json).
- FORBIDDEN TOKENS: Do not use ENTER as a raw token. Use "{{ENTER}}" inside string values only.

STRICT CONTENT RULES (Phase-14.4 & 14.7):
1. NO FILLER CONTENT: If the user did not specify text to type, do NOT invent content.
   - User: "save as test.txt" -> DO NOT type "my notes" into the file body first.
   - User: "open notepad" -> Do NOT type "hello world" unless asked.
2. MISSING TEXT: If a save action requires a filename but none is provided, fail or ask clarification.
3. EXACT TYPING: Only type what is explicitly requested.
4. ATOMIC SAVE OPERATIONS: When saving a file ("Save As"), YOU MUST DECOMPOSE into these exact steps to ensure valid file handling:
   - Step A: Open Dialog -> {{"action_type": "type_text", "context": "desktop", "text": "^s"}}
   - Step B: Clear Field -> {{"action_type": "type_text", "context": "desktop", "text": "^a{{BACKSPACE}}"}} (Select All + Delete)
   - Step C: Type Filename -> {{"action_type": "type_text", "context": "desktop", "text": "filename.txt"}}
   - Step D: Confirm -> {{"action_type": "type_text", "context": "desktop", "text": "{{ENTER}}"}}
   (Do NOT merge these into one string like "^sfilename{{ENTER}}". Separate them as distinct actions.)

REQUIRED JSON STRUCTURE:
Each action object MUST have these exact fields:
1. "action_type": String ("launch_app", "type_text", "wait", "close_app", "click_control")
2. "context": String ("desktop", "web", "file")
3. "target": String (Required for launch_app, wait, close_app, click_control)
4. "text": String (Required for type_text)
5. "verify": Optional Dict {{ "requires_approval": boolean, "reason": string }} (Use for LOW CONFIDENCE steps)

EXAMPLES OF CORRECT SYNTAX:

[
  {{
    "action_type": "type_text",
    "context": "desktop",
    "text": "^s" 
  }}
]
(Notice "text" key is present. Do NOT output valid values without keys!)

VISION & CONFIDENCE RULES (Phase-11):
- If the Instruction relies on Vision Context with confidence <= 0.7:
  - You MUST include a "verify" field in the action.
  - Set "requires_approval": true.
  - Set "reason": "Action based on low-confidence vision: [details]".
- Do NOT perform actions (like clicking) blindly based on vision. Ask for confirmation via the "verify" mechanism.
- If Vision says "X appears to be Y", treat it as probable but not certain.

SUPPORTED ACTIONS BY CONTEXT:

DESKTOP CONTEXT:
- launch_app: Launch an application
  {{"action_type": "launch_app", "context": "desktop", "target": "notepad.exe"}}
- type_text: Type text (or keys) into focused window
  {{"action_type": "type_text", "context": "desktop", "text": "hello world"}}
  {{"action_type": "type_text", "context": "desktop", "text": "{{ENTER}}"}}
- wait: Wait for seconds
  {{"action_type": "wait", "context": "desktop", "target": "2.0"}}
- click_control: Click a UI element by name
  {{"action_type": "click_control", "context": "desktop", "target": "Save"}}
- close_app: Close application
  {{"action_type": "close_app", "context": "desktop", "target": "notepad.exe"}}

WEB CONTEXT:
- launch_app: Navigate to URL
  {{"action_type": "launch_app", "context": "web", "target": "https://example.com"}}
- type_text: Type into web element (needs CSS selector)
  {{"action_type": "type_text", "context": "web", "target": "#search-input", "text": "hello"}}

FILE CONTEXT:
- launch_app: Read file (returns content)
  {{"action_type": "launch_app", "context": "file", "target": "notes.txt"}}
- type_text: Create new file (fails if exists)
  {{"action_type": "type_text", "context": "file", "target": "output.txt", "text": "file content"}}

CRITICAL RULES:
1. NEVER omit the "text" key for type_text actions.
2. NEVER omit the "target" key for launch_app actions.
3. If ANY action has context="file", ALL actions must be context="file".
4. SAVING FILES: Always prefer sending Ctrl+S ("^s") to save. Do NOT rely on closing the app to trigger a save prompt.
   - YES: type_text "^s", wait, type_text filename...
   - NO: close_app, wait for prompt...

EXAMPLE COMPOSITE WORKFLOWS:
Instruction: "Open notepad, type hello, save as test.txt, close"
Plan:
[
  {{"action_type": "launch_app", "context": "desktop", "target": "notepad.exe"}},
  {{"action_type": "type_text", "context": "desktop", "text": "hello"}},
  {{"action_type": "type_text", "context": "desktop", "text": "^s"}},  // Save shortcut
  {{"action_type": "wait", "context": "desktop", "target": "1"}},       // Wait for dialog
  {{"action_type": "type_text", "context": "desktop", "text": "test.txt"}}, // Filename
  {{"action_type": "type_text", "context": "desktop", "text": "{{ENTER}}"}}, // Confirm
  {{"action_type": "close_app", "context": "desktop", "target": "notepad.exe"}}
]
- File creation is standalone: "create file X" → ONE action only
- Example INVALID: [{{"context": "file"}}, {{"context": "desktop"}}]
- Example VALID: [{{"context": "file", "action_type": "type_text", "target": "notes.txt", "text": "content"}}]

FILE CREATION RULE (NON-NEGOTIABLE):
- If the user intent is to CREATE a file:
  → Output EXACTLY ONE action
  → action_type MUST be "type_text"
  → context MUST be "file"
  → NEVER include launch_app for file creation
  → NEVER include multiple file actions
- If you generate more than one file action, the plan will be REJECTED

EXAMPLE - FILE CREATION:
USER: "create file notes.txt with text hello"
VALID OUTPUT:
[
  {{
    "action_type": "type_text",
    "context": "file",
    "target": "notes.txt",
    "text": "hello"
  }}
]

INVALID OUTPUT (DO NOT GENERATE):
[
  {{"action_type": "launch_app", "context": "file", "target": "notes.txt"}},
  {{"action_type": "type_text", "context": "file", "target": "notes.txt", "text": "hello"}}
]

PLANNING RULES:
- For "open notepad and type hello", generate TWO actions with context="desktop"
- For "go to google and search", generate TWO actions with context="web"
- For "create file with content", EXACTLY ONE action with context="file" (NO editor launch)
- For "open google and read the heading", generate ONE action + ONE observation
- Keep text fields under 200 characters
- CSS selectors must use semantic tags (h1, input, button) not invented IDs
- File paths are relative to workspace (no absolute paths needed)
- File operations NEVER include desktop/web actions
- SEQUENCING RULE: If saving a file (e.g. "Save as..."):
  1. `type_text ^s`
  2. `type_text [filename]`
  3. `click_control Save`
  4. THEN and ONLY THEN `close_app`
  (NEVER close_app before saving if a save is requested!)
- AMBIGUITY RULE: If the instruction is ambiguous (e.g., "do it", "fix the thing"), unclear, or unsafe, output an EMPTY JSON array: []

OBSERVATIONS (Phase-2B - Read-only queries):
{{"observation_type": "read_text" | "query_element", "context": "desktop" | "web" | "file", "target": "..."}}

OBSERVATION TYPES:
- read_text: Extract text from element/file (OBSERVATION ONLY - never use as action_type!)
  {{"observation_type": "read_text", "context": "web", "target": "h1"}}
  {{"observation_type": "read_text", "context": "file", "target": "notes.txt"}}
- query_element: Check if element exists
  {{"observation_type": "query_element", "context": "web", "target": "#search"}}

CRITICAL: "read_text" is ONLY valid as observation_type, NEVER as action_type.
File read instructions (e.g., "read file test.txt") must generate ONLY observations, NO actions.

MIXED PLANS:
- Actions cause side effects (navigate, type, create)
- Observations read state (no side effects)
- Example: "open example.com and read heading"
  [{{"action_type": "launch_app", "context": "web", "target": "https://example.com"}}, {{"observation_type": "read_text", "context": "web", "target": "h1"}}]

SAFETY:
- Never generate destructive actions
- Never generate more than {max_actions} actions
- Never omit the "context" field
- Never use coordinates (not supported)

OUTPUT FORMAT EXAMPLES:

Desktop (Launch & Type):
[{{"action_type": "launch_app", "context": "desktop", "target": "notepad.exe"}}, {{"action_type": "type_text", "context": "desktop", "text": "hello"}}]

Desktop (Save Workflow):
Instruction: "open notepad, type hello, save as test.txt, close"
[
  {{"action_type": "launch_app", "context": "desktop", "target": "notepad.exe"}},
  {{"action_type": "type_text", "context": "desktop", "text": "hello"}},
  {{"action_type": "type_text", "context": "desktop", "text": "^s"}}, 
  {{"action_type": "wait", "context": "desktop", "target": "2.0"}},
  {{"action_type": "type_text", "context": "desktop", "text": "%USERPROFILE%\\\\Desktop\\\\test.txt"}},
  {{"action_type": "click_control", "context": "desktop", "target": "Save"}},
  {{"action_type": "wait", "context": "desktop", "target": "2.0"}},
  {{"action_type": "close_app", "context": "desktop", "target": "notepad.exe"}}
]

Web:
[{{"action_type": "launch_app", "context": "web", "target": "https://google.com"}}, {{"action_type": "type_text", "context": "web", "target": "input[name='q']", "text": "search query"}}]

File:
[{{"action_type": "type_text", "context": "file", "target": "notes.txt", "text": "my notes here"}}]

Now generate the plan."""

    def _parse_response(self, response: str, max_items: int) -> List[Union[Action, Observation]]:
        """
        Parse LLM response into Action and/or Observation objects.
        
        Args:
            response: Raw LLM output
            max_items: Maximum items allowed (actions + observations)
            
        Returns:
            List of Action and/or Observation objects
            
        Raises:
            ValueError: If response is malformed or unsafe
        """
        # Clean response (remove markdown code blocks if present)
        cleaned = response.strip()
        
        # Phase-1B: More aggressive cleaning
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]  # Remove ```json
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]  # Remove ```
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        # Find JSON array in response
        try:
            # Try to find JSON array
            start = cleaned.find("[")
            end = cleaned.rfind("]") + 1
            
            if start == -1 or end == 0:
                raise ValueError("No JSON array found in LLM response. Please rephrase your instruction.")
            
            json_str = cleaned[start:end]
            item_dicts = json.loads(json_str)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nResponse: {response}")
            raise ValueError(f"LLM output is malformed (invalid JSON). Please rephrase your instruction.")
        
        # Validate it's a list
        if not isinstance(item_dicts, list):
            raise ValueError("LLM output must be a JSON array. Please rephrase your instruction.")
        
        # Check item count
        if len(item_dicts) == 0:
            # Check if it was explicit empty list (reject/ambiguous)
            raise ValueError("Ambiguous or unsafe instruction (Empty Plan).")
        
        if len(item_dicts) > max_items:
            raise ValueError(
                f"Plan too complex: {len(item_dicts)} items (max: {max_items}). "
                "Please break your task into smaller steps."
            )
            
        # Phase-13.4: Forbidden token check
        # Explicitly reject plans containing raw "ENTER" if it wasn't caught by JSON parser
        # (Though text: "ENTER" is valid JSON string, but user wants to block unsafe usage)
        # Actually user said "FORBIDDEN_TOKENS = {"ENTER", ...}" - but "ENTER" is safe inside "text" field IF it's string.
        # User concern 'ENTER is not defined' was Python eval error.
        # Since we use json.loads, we are safe from evaluation.
        # We can implement schema whitelist here.
        
        ALLOWED_ACTIONS = {"launch_app", "type_text", "wait", "close_app", "focus_window", "click_control", 
                           "read_text", "query_element", "vision", "check_app_state", "vision_buffer_read"}
        
        # Convert to Action/Observation objects
        plan = []
        for i, item_dict in enumerate(item_dicts):
            try:
                # Schema Validation
                if "action_type" in item_dict:
                    atype = item_dict["action_type"]
                    if atype not in ALLOWED_ACTIONS:
                        raise ValueError(f"Illegal action type: {atype}")
                
                item = self._dict_to_plan_item(item_dict)
                plan.append(item)
            except Exception as e:
                logger.error(f"Invalid item at index {i}: {item_dict}")
                raise ValueError(
                    f"Invalid item at position {i+1}: {e}. "
                    "Please ensure your instruction is clear and uses supported actions/observations."
                )
        
        return plan

    def _dict_to_plan_item(self, item_dict: Dict[str, Any]) -> Union[Action, Observation]:
        """Convert dictionary to Action or Observation object."""
        # Auto-correct common LLM confusion where observations are returned as actions
        if "action_type" in item_dict:
            if item_dict["action_type"] in ["read_text", "query_element", "vision", "check_app_state"]:
                # Convert to observation
                item_dict["observation_type"] = item_dict.pop("action_type")
                if "observation_type" in item_dict:
                    return self._dict_to_observation(item_dict)

        if "action_type" in item_dict:
            return self._dict_to_action(item_dict)
        elif "observation_type" in item_dict:
            return self._dict_to_observation(item_dict)
        else:
            raise ValueError("Item must have either 'action_type' or 'observation_type' field")

    def _dict_to_action(self, action_dict: Dict[str, Any]) -> Action:
        """Convert dictionary to Action object."""
        # Validate required fields
        if "action_type" not in action_dict:
            raise ValueError("Missing 'action_type' field")
        
        if "context" not in action_dict:
            raise ValueError("Missing 'context' field (required: 'desktop', 'web', or 'file')")
        
        action_type = action_dict["action_type"]
        context = action_dict["context"]
        
        if action_type == "read_text":
            raise ValueError("Invalid action_type: read_text is an OBSERVATION.")
        
        REQUIRED_FIELDS_MAP = {
            "launch_app": ["target"],
            "type_text": ["text"],
            "wait": ["target"],
            "close_app": ["target"],
            "focus_window": ["target"],
            "click_control": ["target"]
        }
        
        if action_type not in REQUIRED_FIELDS_MAP:
             raise ValueError(f"Invalid action_type: {action_type}")
             
        if context not in ["desktop", "web", "file"]:
             raise ValueError(f"Invalid context: {context}")
        
        target = action_dict.get("target")
        text = action_dict.get("text")
        
        # Generic Required Field Validation
        if action_type in REQUIRED_FIELDS_MAP:
             for field in REQUIRED_FIELDS_MAP[action_type]:
                 if field == "target" and not target:
                     raise ValueError(f"{action_type} requires 'target' field")
                 if field == "text" and not text:
                     raise ValueError(f"{action_type} requires 'text' field")

        if context == "web" and action_type == "type_text" and not target:
            raise ValueError("type_text (web) requires 'target' selector")
        
        if context == "file" and not target:
            raise ValueError("File operations require 'target' file path")
        
        verify = action_dict.get("verify")
        
        return Action(
            action_type=action_type,
            context=context,
            target=target,
            text=text,
            verify=verify
        )

    def _dict_to_observation(self, obs_dict: Dict[str, Any]) -> Observation:
        """Convert dictionary to Observation object."""
        if "observation_type" not in obs_dict:
            raise ValueError("Missing 'observation_type' field")
        
        if "context" not in obs_dict:
            raise ValueError("Missing 'context' field")
        
        observation_type = obs_dict["observation_type"]
        context = obs_dict["context"]
        
        valid_types = ["read_text", "query_element", "vision", "check_app_state", "vision_buffer_read"]
        if observation_type not in valid_types:
            raise ValueError(f"Invalid observation_type: {observation_type}")
        
        if context not in ["desktop", "web", "file", "vision", "vision_buffer"]:
            raise ValueError(f"Invalid context: {context}")
        
        target = obs_dict.get("target")
        if not target:
            raise ValueError(f"Observation requires 'target' field")
        
        return Observation(
            observation_type=observation_type,
            context=context,
            target=target
        )
