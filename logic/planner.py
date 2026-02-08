"""
Planner - Dual Mode (Deterministic + LLM)
Generates action plans from natural language instructions.

Phase-0: Deterministic (hardcoded)
Phase-1A: LLM-based (Ollama) with fallback to deterministic
Phase-2B: Mixed plans (Actions + Observations)
Phase-5A: Plan graph generation with intent and structure metadata
"""
import logging
import re
from typing import List, Optional, Union
from dataclasses import replace
from common.actions import Action
from common.observations import Observation, ObservationResult
from common.plan_graph import PlanGraph, PlanStep
from logic.llm_planner import LLMPlanner

logger = logging.getLogger(__name__)


class Planner:
    """
    Dual-mode action planner.
    
    Modes:
    - Deterministic: Hardcoded logic for specific patterns (Phase-0)
    - LLM: Natural language understanding via Ollama (Phase-1A)
    
    Mode selection via config. Falls back to deterministic on LLM failure.
    """
    
    def __init__(self, config: Optional[dict] = None, llm_client=None, file_handler=None):
        """
        Initialize the planner.
        
        Args:
            config: Agent configuration dictionary
            llm_client: LLMClient instance (optional)
            file_handler: FileHandler instance for workspace validation (optional)
        """
        self.config = config or {}
        self.llm_client = llm_client
        self.file_handler = file_handler
        
        # Determine mode
        planner_config = self.config.get("planner", {})
        self.use_llm = planner_config.get("use_llm", False)
        self.max_actions = planner_config.get("max_actions_per_plan", 5)
        
        mode = "LLM" if self.use_llm and self.llm_client else "deterministic"
        
        if mode == "LLM":
            self.llm_planner = LLMPlanner(self.llm_client)
        else:
            self.llm_planner = None
            
        logger.info(f"Planner initialized ({mode} mode)")
    
    def parse_instruction(self, instruction: str) -> List[Union[Action, Observation]]:
        """
        Parse a natural language instruction into a sequence of Actions and/or Observations.
        
        Phase-0: Only supports "open notepad and type [text]" pattern.
        Phase-2B: Added file read support (observation-only).
        
        Args:
            instruction: Natural language task description
            
        Returns:
            List of Action and/or Observation objects to execute
            
        Raises:
            ValueError: If instruction is not supported
        """
        instruction_lower = instruction.lower().strip()
        
        # Pattern: "read file [filename]" - Phase-2B deterministic file read
        # CRITICAL: File READ must generate ONLY observation, NO actions
        if "read file" in instruction_lower or "read text from file" in instruction_lower:
            # Extract filename
            filename = None
            
            # Try "read file <filename>" pattern
            if "read file" in instruction_lower:
                parts = instruction_lower.split("read file", 1)
                if len(parts) == 2:
                    filename = parts[1].strip()
            
            # Try "read text from file <filename>" pattern
            elif "read text from file" in instruction_lower:
                parts = instruction_lower.split("read text from file", 1)
                if len(parts) == 2:
                    filename = parts[1].strip()
            
            if filename:
                logger.info(f"Parsed file read instruction: read '{filename}'")
                
                # Return OBSERVATION ONLY - no actions
                return [
                    Observation(
                        observation_type="read_text",
                        context="file",
                        target=filename
                    )
                ]
            else:
                raise ValueError("Could not extract filename from read instruction")
        
        # Pattern: "open notepad and type [text]"
        if "notepad" in instruction_lower and "type" in instruction_lower:
            # Extract text to type
            if " type " in instruction_lower:
                # Split on "type" and get everything after
                parts = instruction_lower.split(" type ", 1)
                if len(parts) == 2:
                    text_to_type = parts[1].strip()
                    # Remove quotes if present
                    text_to_type = text_to_type.strip('"\'')
                    
                    logger.info(f"Parsed instruction: open notepad, type '{text_to_type}'")
                    
                    return [
                        Action(action_type="launch_app", target="notepad.exe"),
                        Action(action_type="type_text", text=text_to_type)
                    ]
        
        # Pattern: "type [text]" (standalone)
        if instruction_lower.startswith("type "):
             # Extract text
             parts = instruction_lower.split("type ", 1)
             if len(parts) == 2:
                 text = parts[1].strip().strip('"\'')
                 logger.info(f"Parsed instruction: type '{text}'")
                 return [Action(action_type="type_text", context="desktop", text=text)]

        # Pattern: just "notepad" or "open notepad" (with optional articles)
        if "notepad" in instruction_lower and ("open" in instruction_lower or "launch" in instruction_lower or instruction_lower.strip() == "notepad"):
             # Verify it's not a "type" command
             if "type" not in instruction_lower:
                logger.info("Parsed instruction: open notepad")
                return [Action(action_type="launch_app", target="notepad.exe")]
        
        # Phase-4A: Pattern "focus [window name]" or "switch to [app]"
        if "focus" in instruction_lower or "switch to" in instruction_lower:
            target = None
            if "focus" in instruction_lower:
                parts = instruction_lower.split("focus", 1)
                if len(parts) == 2:
                    target = parts[1].strip()
            elif "switch to" in instruction_lower:
                parts = instruction_lower.split("switch to", 1)
                if len(parts) == 2:
                    target = parts[1].strip()
            
            if target:
                logger.info(f"Parsed instruction: focus window '{target}'")
                return [Action(action_type="focus_window", context="desktop", target=target)]
        
        # Phase-4A: Pattern "close [app]"
        if "close" in instruction_lower or "exit" in instruction_lower:
            # Handle "close notepad"
            target = "notepad.exe" # Default
            if "notepad" in instruction_lower:
                target = "notepad.exe"
            # Extract other targets if needed (simplified)
            
            logger.info(f"Parsed instruction: close app '{target}'")
            return [Action(action_type="close_app", context="desktop", target=target)]
            
        # Phase-4A: Pattern "save ..."
        if "save" in instruction_lower:
             # Basic save logic (Ctrl+S)
             actions = [Action(action_type="type_text", context="desktop", text="^s")]
             
             # If "save as [filename]", we might need more logic handled by ExecutionEngine or user
             # For now, just send keys. Planner repair logic handles filenames if missing.
             logger.info("Parsed instruction: save (Ctrl+S)")
             return actions

        # Phase-4A: Pattern "wait [N] seconds"
        if "wait" in instruction_lower:
            import re
            # Extract number
            match = re.search(r'(\d+(?:\.\d+)?)\s*(?:second|sec|s)', instruction_lower)
            if match:
                duration = match.group(1)
                logger.info(f"Parsed instruction: wait {duration}s")
                return [Action(action_type="wait", context="desktop", target=duration)]
        
        # Unsupported instruction
        logger.error(f"Unsupported instruction in Phase-0: {instruction}")
        raise ValueError(
            f"Phase-0 only supports: 'open notepad and type [text]'. "
            f"Got: '{instruction}'"
        )
    
    def create_plan(self, instruction: str, context: Optional[List[ObservationResult]] = None) -> List[Union[Action, Observation]]:
        """
        Create an execution plan from an instruction.
        
        Routes to LLM or deterministic planner based on config.
        
        Phase-2B: Returns mixed list of Actions and Observations.
        Phase-2B Fix: File-read intents BYPASS LLM completely (deterministic override).
        
        Args:
            instruction: Natural language task description
            context: Optional prior observations (Phase-11)
            
        Returns:
            List of Action and/or Observation objects
            
        Raises:
            ValueError: If planning fails
        """
        # CRITICAL: Detect special intents BEFORE routing to LLM
        instruction_lower = instruction.lower().strip()
        
        # Market analysis intents should NOT reach planner (handled by intent resolver)
        market_keywords = ["analyze", "analysis", "technical", "support", "resistance", "trend", "tradingview"]
        trading_keywords = ["buy", "sell", "trade", "execute", "order"]
        action_keywords = ["draw", "mark", "click", "type", "open browser"]
        
        has_market_keyword = any(keyword in instruction_lower for keyword in market_keywords)
        has_trading_keyword = any(keyword in instruction_lower for keyword in trading_keywords)
        has_action_keyword = any(keyword in instruction_lower for keyword in action_keywords)
        
        if has_market_keyword and not has_trading_keyword and not has_action_keyword:
            logger.error("[PLANNER BREACH] Market analysis intent reached planner - should be handled by intent resolver")
            logger.error("Returning empty plan to prevent action generation")
            return []
        
        # File reads MUST use deterministic planning (observation-only)
        file_read_keywords = ["read file", "read text from", "show contents of", "open file", "read the file"]
        has_file_read_intent = any(keyword in instruction_lower for keyword in file_read_keywords)
        
        if has_file_read_intent:
            # BYPASS LLM - use deterministic file read planning
            logger.info("Detected file_read intent -> deterministic plan (bypassing LLM)")
            
            # Extract filename
            filename = None
            
            if "read file" in instruction_lower:
                parts = instruction_lower.split("read file", 1)
                if len(parts) == 2:
                    filename = parts[1].strip()
            elif "read text from" in instruction_lower:
                parts = instruction_lower.split("read text from", 1)
                if len(parts) == 2:
                    filename = parts[1].strip().replace("file", "").strip()
            elif "show contents of" in instruction_lower:
                parts = instruction_lower.split("show contents of", 1)
                if len(parts) == 2:
                    filename = parts[1].strip().replace("file", "").strip()
            elif "open file" in instruction_lower and "read" in instruction_lower:
                # Pattern: "open file X and read"
                parts = instruction_lower.split("open file", 1)
                if len(parts) == 2:
                    # Extract filename before "and"
                    filename_part = parts[1].split("and")[0].strip()
                    filename = filename_part
            
            if not filename:
                # Try generic filename extraction (last word)
                words = instruction_lower.split()
                if len(words) > 0:
                    filename = words[-1].strip()
            
            if filename:
                logger.info(f"File-read intent: target='{filename}' (observation-only, LLM bypassed)")
                
                # POLICY VALIDATION: Check if file path is within workspace
                if self.file_handler:
                    try:
                        # Validate path before creating observation
                        self.file_handler._validate_path(filename)
                        logger.info(f"File path validated: '{filename}' is within workspace")
                    except ValueError as e:
                        # Path escapes workspace - POLICY VIOLATION
                        logger.error(f"[POLICY VIOLATION] File path escapes workspace: {e}")
                        logger.error(f"Rejecting instruction due to workspace boundary violation")
                        # Return empty plan to abort
                        return []
                
                # Return deterministic observation-only plan
                plan = [
                    Observation(
                        observation_type="read_text",
                        context="file",
                        target=filename
                    )
                ]
                
                # Log plan details
                actions = [item for item in plan if isinstance(item, Action)]
                observations = [item for item in plan if isinstance(item, Observation)]
                logger.info(f"Generated {len(plan)} item(s): {len(actions)} action(s), {len(observations)} observation(s)")
                
                return plan
            else:
                logger.warning("File-read intent detected but could not extract filename")
                # Fall through to normal planning
        
        # CRITICAL: Detect verification intent BEFORE routing to LLM
        # Verification must generate Action with verify metadata, NOT observations
        verification_keywords = ["verify", "verify_text_visible", "verify that", "check that", "confirm that"]
        has_verification_intent = any(keyword in instruction_lower for keyword in verification_keywords)
        
        if has_verification_intent:
            # BYPASS LLM - verification must be handled by Critic, not Observer
            logger.info("Detected verification intent -> action with verification metadata (bypassing observations)")
            
            # Extract what needs to be verified
            verification_text = None
            
            # Try to extract text after "verify", "check", etc.
            for keyword in verification_keywords:
                if keyword in instruction_lower:
                    parts = instruction_lower.split(keyword, 1)
                    if len(parts) == 2:
                        # Get text after keyword, clean up common words
                        verification_text = parts[1].strip()
                        # Remove common filler words
                        verification_text = verification_text.replace("that", "").replace("the", "").strip()
                        break
            
            # Determine the action type and target
            # Default: launch_app for desktop verification
            action_type = "launch_app"
            context = "desktop"
            target = "notepad.exe"  # Default target
            
            # Check if instruction specifies an app or URL
            if "notepad" in instruction_lower:
                target = "notepad.exe"
            elif "browser" in instruction_lower or "http" in instruction_lower or "www" in instruction_lower:
                context = "web"
                # Extract URL if present
                words = instruction.split()
                for word in words:
                    if "http" in word or "www" in word or ".com" in word or ".org" in word:
                        target = word
                        break
                else:
                    target = "https://example.com"  # Default web target
            
            if verification_text:
                # Create action with verification metadata
                plan = [
                    Action(
                        action_type=action_type,
                        context=context,
                        target=target,
                        verify={
                            "type": "text_visible",
                            "value": verification_text
                        }
                    )
                ]
                
                # Log plan details
                actions = [item for item in plan if isinstance(item, Action)]
                observations = [item for item in plan if isinstance(item, Observation)]
                logger.info(f"Generated {len(plan)} item(s): {len(actions)} action(s), {len(observations)} observation(s)")
                logger.info(f"Verification metadata attached: {plan[0].verify}")
                
                return plan
            else:
                logger.warning("Verification intent detected but could not extract verification text")
                # Fall through to normal planning
        
        # Route based on mode
        if self.use_llm and self.llm_client:
            try:
                return self._create_plan_llm(instruction, context)
            except Exception as e:
                logger.error(f"LLM planning failed: {e}")
                
                # Check fallback behavior
                fallback_config = self.config.get("fallback", {})
                fallback_mode = fallback_config.get("on_llm_failure", "abort")
                
                if fallback_mode == "deterministic":
                    logger.warning("Falling back to deterministic planner")
                    return self._create_plan_deterministic(instruction)
                else:
                    # Abort
                    raise ValueError(f"Planner could not generate a safe plan: {e}")
        else:
            return self._create_plan_deterministic(instruction)
    
    def _filter_actions_by_instruction(self, plan: List[Union[Action, Observation]], instruction: str) -> List[Union[Action, Observation]]:
        """
        Filter out actions that were not explicitly requested in the instruction.
        Prevents LLM 'helpfulness' (hallucinations) like auto-typing text after opening an app.
        """
        instruction_lower = instruction.lower()
        
        # Mapping action types to required keywords
        # Must cover all valid action types in common/actions.py
        allowed_keywords = {
            "launch_app": ["open", "launch", "start", "run", "navigate", "go to"],
            "close_app": ["close", "exit", "quit", "terminate"],
            "type_text": ["type", "write", "enter", "input", "save", "press"], # Added 'press' for shortcuts
            "click_control": ["click", "press", "save", "select", "check", "uncheck"], 
            # focus and wait are safe/passive, handled typically as helpers
        }

        filtered_plan = []

        for item in plan:
            # Pass observations and safe actions through
            if isinstance(item, Observation):
                filtered_plan.append(item)
                continue
            
            if isinstance(item, Action):
                action_type = item.action_type
                
                # Allow safe/helper actions unconditionally
                if action_type in ["wait", "focus_window"]:
                    filtered_plan.append(item)
                    continue
                
                # Get constraint keywords
                keywords = allowed_keywords.get(action_type, [])
                
                # Loose check: If ANY keyword is present, allow the action
                # If 'save' is in instruction, allow 'type_text' (for filenames context)
                if not keywords: 
                    # If unknown action type, maybe allow or warn? 
                    # Let's strictly block unknown types unless explicitly handled
                    logger.warning(f"Unknown action type '{action_type}' encountered in filter. allowing strictly.")
                    # Actually, if keywords list is empty, it means we didn't define rules -> block?
                    # For safety, allow only if we are sure. But 'allowed_keywords' covers all known types.
                    pass
                
                if any(word in instruction_lower for word in keywords):
                    filtered_plan.append(item)
                else:
                    logger.warning(f"hallucination detected: Action '{action_type}' not requested in '{instruction}' - DROPPING ACTION")
                    # Do NOT raise exception, just filter it out.
                    # This allows the plan to proceed with valid actions.

        
        logger.info(f"Action-Intent Gate passed: {len(filtered_plan)} items allowed.")
        return filtered_plan

    def _create_plan_llm(self, instruction: str, context: Optional[List[ObservationResult]] = None) -> List[Union[Action, Observation]]:
        """
        Create plan using LLM.
        
        Phase-2B: Supports mixed plans with Actions and Observations.
        Phase-11: Integrated vision context.
        
        Args:
            instruction: Natural language task
            context: Optional list of ObservationResults
            
        Returns:
            List of Action and/or Observation objects from LLM
            
        Raises:
            ValueError: If LLM fails or output is invalid
        """
        logger.info("Using LLM planner")
        
        if not self.llm_planner:
            raise ValueError("LLM planner not initialized")
        
        # Phase-1B: Pre-validate instruction for obvious issues
        # Phase-2B: Read-intent rejection removed (observations supported)
        self._validate_instruction(instruction)
        
        # Call LLM Planner
        actions = self.llm_planner.generate_plan(
            instruction, 
            max_actions=self.max_actions,
            context=context
        )
        
        # 🚨 ACTION-INTENT GATE 🚨
        # Filter out hallucinated actions not requested in instruction
        actions = self._filter_actions_by_instruction(actions, instruction)

        # Phase-2B: Auto-repair actions with missing targets (e.g., close_app)
        actions = self._repair_plan_targets(actions)
        
        # Phase-3 Fix: Auto-repair save sequencing (Save before Close)
        # PASS THE INSTRUCTION to extract filename if missed
        actions = self._repair_save_sequence(actions, instruction)
        
        # Guard: Check if repair failed (ensure no missing targets remain)
        for item in actions:
            if isinstance(item, Action) and item.action_type == "close_app" and not item.target:
                raise ValueError("Planner failed: 'close_app' action has no target and could not be repaired.")
        
        # Validate action count
        if len(actions) == 0:
            raise ValueError("LLM generated empty plan")
        
        if len(actions) > self.max_actions:
            raise ValueError(f"LLM generated too many actions: {len(actions)} (max: {self.max_actions})")
        
        # Phase-2B: Intent priority guard - validate context matches instruction intent
        self._validate_intent_priority(instruction, actions)
        
        # Phase-2B: Normalize file plans before validation
        actions = self._normalize_file_plan(actions)
        
        # Phase-1B: Validate plan coherence
        # Phase-2B: Validate context exclusivity and file minimality
        self._validate_plan_coherence(actions, instruction)
        self._validate_context_exclusivity(actions)
        self._validate_file_minimality(actions)
        
        logger.info(f"LLM plan: {len(actions)} action(s)")
        return actions

    def _repair_save_sequence(self, plan: List[Union[Action, Observation]], instruction: str = "") -> List[Union[Action, Observation]]:
        """
        Repair plan sequencing errors:
        1. Save Sequence: Injects filenames if missing after ^s.
        2. Destructive Sequence: Injects WAIT if close_app immediately follows type_text.
        3. Reordering: Ensures close_app is last.
        """
        # RULE 1: Save Sequence Injection
        # Only apply this logic if the user explicitly asked to "save" something.
        # This prevents aggressive auto-saving if the LLM hallucinates a ctrl+s action.
        save_indices = [i for i, item in enumerate(plan) 
                       if isinstance(item, Action) and item.action_type == "type_text" and item.text and "^s" in item.text]
        
        has_save_intent = "save" in instruction.lower()
        
        if save_indices:
            if not has_save_intent:
                logger.warning("Plan contains save action (^s) but instruction lacks 'save' keyword. Assuming hallucination.")
                # Optional: We could remove the action here, or just refrain from injecting more steps.
                # For now, we just skip the auto-injection of filenames.
                pass
            else:
                logger.info("Save sequence detected checking for strict logic...")
                
                # REPAIR STRATEGY: 
                # If explicit 'save' requested -> allow injection
                # If implicit/hallucinated (no 'save' in instruction) -> DROP the action (safety first)
                if not has_save_intent:
                    logger.warning("Dropping hallucinated 'CTRL+S' action (user did not request save).")
                    plan.pop(save_indices[0])
                    # Re-scan in next pass if multiple exist, or just break for MVP
                    return plan
                    
                # INJECTION LOGIC: Check if filename is typed after save
            for save_idx in save_indices:
                # Check next 2-3 actions for a filename type
                has_filename_step = False
                lookahead = min(len(plan), save_idx + 4)
                
                for i in range(save_idx + 1, lookahead):
                    item = plan[i]
                    if isinstance(item, Action) and item.action_type == "type_text":
                        # Check if text looks like a filename
                        if any(ext in item.text for ext in [".txt", ".md", ".json", ".py", "\\", "/"]):
                            has_filename_step = True
                            break
                
                if not has_filename_step:
                    logger.warning(f"Save detected at step {save_idx+1} but NO filename typing found. Attempting injection...")
                    
                    # Extract filename from instruction
                    # Regex for common filenames
                    filename_match = re.search(r'([a-zA-Z0-9_\-\\]+\.(txt|md|json|csv|py))', instruction)
                    extracted_filename = "untitled.txt" # Default
                    
                    if filename_match:
                        extracted_filename = filename_match.group(1)
                        if "desktop" in instruction.lower() and "\\" not in extracted_filename:
                             extracted_filename = f"%USERPROFILE%\\Desktop\\{extracted_filename}"
                        
                        logger.info(f"Extracted missing filename from instruction: '{extracted_filename}'")
                    else:
                        logger.warning("Could not extract filename from instruction. using 'untitled.txt'")

                    new_action = Action(
                        action_type="type_text",
                        context="desktop",
                        text=extracted_filename
                    )
                    
                    plan.insert(save_idx + 1, new_action)
                    wait_action = Action(action_type="wait", context="desktop", target="1.0")
                    plan.insert(save_idx + 1, wait_action)
                    confirm_action = Action(action_type="type_text", context="desktop", text="{ENTER}")
                    plan.insert(save_idx + 3, confirm_action)
                    
                    # NOTE: Removed blind overwrite handling (Left+Enter) because it corrupts document
                    # if the overwrite confirmation dialog does NOT appear (cursor moves left, split line).
                    # Future improvement: Use Conditional Execution or Observer to handle overwrite dialogs.
                    
                    logger.info(f"Injected [wait, type_text {extracted_filename}, enter] into plan.")
                    break

        # RULE 2: Destructive Sequence Buffering
        # Identify if close_app immediately follows type_text
        i = 0
        while i < len(plan) - 1:
            current = plan[i]
            next_item = plan[i+1]
            
            if (isinstance(current, Action) and current.action_type == "type_text" and 
                isinstance(next_item, Action) and next_item.action_type == "close_app"):
                
                # Check availability of explicit wait
                # If current text is short, user might not notice, but for longer text, we need a buffer.
                logger.info(f"Detected close_app immediately after type_text. Injecting safety wait.")
                
                wait_action = Action(action_type="wait", context="desktop", target="2.0")
                plan.insert(i + 1, wait_action)
                i += 1 # Skip the inserted wait
            i += 1

        # REORDERING LOGIC: Move close_app to end
        non_close_actions = []
        close_actions = []
        
        for item in plan:
            if isinstance(item, Action) and item.action_type == "close_app":
                close_actions.append(item)
            else:
                non_close_actions.append(item)
                
        if not close_actions:
            return plan
            
        # Reassemble: everything else first, then closes
        return non_close_actions + close_actions

    def _repair_plan_targets(self, plan: List[Union[Action, Observation]]) -> List[Union[Action, Observation]]:
        """
        Auto-repair actions with missing targets using plan context.
        
        Specifically handles close_app(target=None) by inferring from
        previous launch_app or focus_window actions.
        
        Args:
            plan: List of actions/observations
            
        Returns:
            Repaired plan
        """
        repaired_plan = []
        action_history_targets = []
        
        for item in plan:
            if isinstance(item, Action):
                # Track potential targets
                if item.action_type in ["launch_app", "focus_window"] and item.target:
                    if item.target not in action_history_targets:
                        action_history_targets.append(item.target)
                
                # Check for close_app with missing target (enabled by relaxed Action validation)
                if item.action_type == "close_app" and not item.target:
                    logger.warning(f"Found close_app with missing target. Attempting repair...")
                    
                    if len(action_history_targets) == 1:
                        # Deterministic repair
                        inferred_target = action_history_targets[0]
                        logger.info(f"Auto-repaired close_app target to: '{inferred_target}'")
                        new_item = replace(item, target=inferred_target)
                        repaired_plan.append(new_item)
                        continue
                        
                    elif len(action_history_targets) == 0:
                        # Ambiguous - no history
                        print("\n" + "!"*60)
                        print("⚠️  PLANNER AMBIGUITY: LLM generated 'close_app' without target.")
                        print("No apps were launched in this plan to infer from.")
                        target = input("Enter the name of the app to close: ").strip()
                        if target:
                            new_item = replace(item, target=target)
                            repaired_plan.append(new_item)
                            continue
                        else:
                            # User skipped - keep as is (will likely fail later or be handled)
                            pass
                            
                    else:
                        # Ambiguous - multiple history
                        print("\n" + "!"*60)
                        print("⚠️  PLANNER AMBIGUITY: LLM generated 'close_app' without target.")
                        print(f"Candidates from plan history: {', '.join(action_history_targets)}")
                        target = input(f"Enter app to close (or press Enter for '{action_history_targets[-1]}'): ").strip()
                        
                        if not target:
                           target = action_history_targets[-1] # Default to most recent
                        
                        new_item = replace(item, target=target)
                        repaired_plan.append(new_item)
                        continue
            
            # Keep original item if no repair needed (or repair skipped)
            repaired_plan.append(item)
            
        return repaired_plan
    
    def _validate_intent_priority(self, instruction: str, plan: List[Union[Action, Observation]]):
        """
        Validate that plan context matches instruction intent.
        
        Phase-2B: Intent determines authority layer priority.
        File intent has highest priority and cannot generate web/desktop actions.
        
        Args:
            instruction: User instruction
            plan: Generated plan
            
        Raises:
            ValueError: If plan context violates detected intent
        """
        instruction_lower = instruction.lower().strip()
        
        # Detect file intent keywords
        file_intent_keywords = [
            "create file",
            "write file",
            "save file",
            "new file",
            "file with text",
            "make file",
            "generate file"
        ]
        
        has_file_intent = any(keyword in instruction_lower for keyword in file_intent_keywords)
        
        if has_file_intent:
            # File intent detected - enforce file context only
            action_contexts = set()
            for item in plan:
                if isinstance(item, Action):
                    action_contexts.add(item.context)
            
            # Check for invalid contexts
            invalid_contexts = action_contexts - {"file"}
            if invalid_contexts:
                logger.error(f"File intent detected but plan contains invalid contexts: {invalid_contexts}")
                raise ValueError(
                    f"Invalid plan: file intent cannot generate {', '.join(invalid_contexts)} actions. "
                    "Instruction contains file creation keywords but plan uses non-file context."
                )
            
            logger.info("Intent priority validated: file intent matched")
    
        # File-read intent detection (Phase-2B)
        # File reads must be observation-only (no actions)
        file_read_keywords = ["read file", "read text from"]
        has_file_read_intent = any(keyword in instruction_lower for keyword in file_read_keywords)
        
        if has_file_read_intent:
            # Check if plan has ANY actions (file reads must be observation-only)
            actions = [item for item in plan if isinstance(item, Action)]
            if actions:
                logger.error(f"File read intent has {len(actions)} action(s): {[a.action_type for a in actions]}")
                raise ValueError(
                    f"File read intent must generate ONLY observations, NO actions. "
                    f"Expected: [Observation(read_text, context=file)]. "
                    f"Got: {len(actions)} action(s)."
                )
            
            # Verify plan has at least one file observation
            file_observations = [item for item in plan if isinstance(item, Observation) and item.context == "file"]
            if not file_observations:
                logger.error("File read intent has no file observations")
                raise ValueError(
                    "File read intent must generate at least one file observation."
                )
            
            logger.info("Intent priority validated: file read intent matched (observation-only)")
    
    def _normalize_file_plan(self, plan: List[Union[Action, Observation]]) -> List[Union[Action, Observation]]:
        """
        Normalize file plans to enforce machine semantics.
        
        Phase-2B: LLM may generate human-like workflows (read then write).
        Planner enforces atomic file creation semantics.
        
        If plan contains:
        - context="file"
        - exactly one type_text action
        - one or more launch_app actions
        
        Then:
        - Remove all launch_app(context="file") actions
        - Keep the single type_text action
        
        Args:
            plan: Raw LLM-generated plan
            
        Returns:
            Normalized plan with redundant file reads removed
        """
        # Extract file actions
        file_actions = [item for item in plan if isinstance(item, Action) and item.context == "file"]
        
        if not file_actions:
            # No file actions, no normalization needed
            return plan
        
        # Check if pattern matches: has type_text + launch_app
        type_text_actions = [a for a in file_actions if a.action_type == "type_text"]
        launch_app_actions = [a for a in file_actions if a.action_type == "launch_app"]
        
        if len(type_text_actions) == 1 and len(launch_app_actions) > 0:
            # Normalization needed: remove redundant launch_app(file) actions
            logger.info(
                f"Normalizing file plan: removing {len(launch_app_actions)} launch_app(file) action(s) "
                f"to enforce atomic file creation"
            )
            
            # Filter out launch_app(context="file") actions
            normalized_plan = [
                item for item in plan
                if not (isinstance(item, Action) and 
                       item.context == "file" and 
                       item.action_type == "launch_app")
            ]
            
            return normalized_plan
        
        # No normalization needed
        return plan
    
    def _validate_instruction(self, instruction: str):
        """
        Validate instruction for obvious issues before sending to LLM.
        
        Args:
            instruction: User instruction
            
        Raises:
            ValueError: If instruction is obviously invalid
        """
        instruction_lower = instruction.lower().strip()
        
        # Empty or too short
        if len(instruction_lower) < 3:
            raise ValueError("Instruction too short. Please provide a clear task description.")
        
        # Too long (> 500 chars)
        if len(instruction) > 500:
            raise ValueError("Instruction too long (max 500 characters). Please simplify.")
        
        # Phase-2B: Read-intent rejection removed (observations now supported)
        
        # Contradictory patterns
        contradictions = [
            ("open", "close", "same"),  # "open notepad and close notepad"
            ("type", "delete", "text"),  # "type hello and delete hello"
        ]
        
        for word1, word2, context in contradictions:
            if word1 in instruction_lower and word2 in instruction_lower:
                logger.warning(f"Potentially contradictory instruction: {word1}/{word2}")
                # Allow it but log warning (LLM might handle it correctly)
        
        # Check for unsafe keywords (should be caught by policy, but warn early)
        unsafe_keywords = ["delete system", "format drive", "regedit", "registry"]
        for keyword in unsafe_keywords:
            if keyword in instruction_lower:
                raise ValueError(f"Unsafe instruction detected: contains '{keyword}'")
    
    def _validate_plan_coherence(self, plan: List[Union[Action, Observation]], instruction: str):
        """
        Validate that the plan makes logical sense.
        
        Phase-1B: Basic coherence checks to catch obviously wrong plans.
        Phase-2B: Handles mixed Action/Observation plans, allows observation-only plans.
        
        Args:
            plan: Generated plan (Actions and/or Observations)
            instruction: Original instruction
            
        Raises:
            ValueError: If plan is incoherent
        """
        if not plan:
            raise ValueError("Empty plan")
        
        # Separate actions from observations
        actions = [item for item in plan if isinstance(item, Action)]
        observations = [item for item in plan if isinstance(item, Observation)]
        
        logger.info(f"Plan has {len(actions)} action(s), {len(observations)} observation(s)")
        
        # Phase-2B: Allow observation-only plans (e.g., file reads)
        if len(actions) == 0 and len(observations) > 0:
            logger.info("Observation-only plan (valid for read operations)")
            return
        
        # Check: If instruction mentions "twice" or "2 times", should have duplicate actions
        instruction_lower = instruction.lower()
        if "twice" in instruction_lower or "2 times" in instruction_lower:
            # Should have at least 2 actions
            if len(actions) < 2:
                logger.warning("Instruction mentions 'twice' but plan has < 2 actions")
        
        # Check: type_text without launch_app first
        has_launch = any(a.action_type == "launch_app" for a in actions)
        has_type = any(a.action_type == "type_text" for a in actions)
        
        if has_type and not has_launch:
            # Only warn, don't fail (user might have app already open)
            logger.warning("Plan contains type_text without launch_app (assuming app is open)")
        
        # Check: Repetitive identical actions (> 3 times same action)
        from collections import Counter
        action_strs = [f"{a.action_type}:{a.target}:{a.text}" for a in actions if isinstance(a, Action)]
        action_counts = Counter(action_strs)
        
        for action_str, count in action_counts.items():
            if count > 3:
                logger.warning(f"Plan has {count} identical actions: {action_str}")
                raise ValueError(f"Plan contains suspicious repetition: {count} identical actions")
        
        logger.info("Plan coherence validated")
    
    def _validate_context_exclusivity(self, plan: List[Union[Action, Observation]]):
        """
        Validate context exclusivity rules.
        
        Phase-2B relaxed: Mixed contexts are allowed but will be segmented
        into multiple plans in create_plan_graph.
        """
        # Mixed contexts are now handled by segmentation
        pass
            
    def _repair_mixed_contexts(self, plan: List[Union[Action, Observation]]) -> List[Union[Action, Observation]]:
        """
        Repair mixed context plans by prioritizing main thread (Desktop/Web) 
        and dropping incompatible File actions.
        
        Args:
            plan: List of actions
            
        Returns:
            Sanitized plan
        """
        action_contexts = set()
        for item in plan:
            if isinstance(item, Action):
                action_contexts.add(item.context)
                
        if "file" in action_contexts and len(action_contexts) > 1:
            logger.warning("Mixed context detected (File + Desktop/Web). Dropping 'file' actions to prevent crash.")
            logger.warning("Agent relies on 'Unsaved Changes' dialog handler for file saving in Desktop context.")
            
            # Keep non-file actions
            repaired_plan = [
                item for item in plan 
                if not (isinstance(item, Action) and item.context == "file")
            ]
            return repaired_plan
            
        return plan

    def _validate_file_minimality(self, plan: List[Union[Action, Observation]]):
        """
        Validate file creation minimality rule.
        
        Phase-2B correction: File creation (type_text with context=file) must be
        a standalone single-action operation.
        Phase-2B: File read (observation with context=file) must have 0 actions.
        
        Args:
            plan: Generated plan (Actions and/or Observations)
            
        Raises:
            ValueError: If file creation plan is not minimal
        """
        # Extract file actions and observations
        file_actions = [item for item in plan if isinstance(item, Action) and item.context == "file"]
        file_observations = [item for item in plan if isinstance(item, Observation) and item.context == "file"]
        
        # Phase-2B: File read validation - must be observation-only
        if file_observations:
            if file_actions:
                logger.error(f"Invalid file read plan: contains {len(file_actions)} action(s)")
                raise ValueError(
                    "Invalid file read plan: file read operations must be observation-only (no actions allowed)."
                )
            logger.info("File read plan validated (observation-only)")
            return
        
        if not file_actions:
            # No file actions, skip validation
            return
        
        # Check if any file action is type_text (CREATE operation)
        has_file_create = any(a.action_type == "type_text" for a in file_actions)
        
        if has_file_create:
            # Rule: If creating a file, plan must have EXACTLY ONE action
            if len(file_actions) != 1:
                logger.error(f"Invalid file creation plan: {len(file_actions)} file actions (expected 1)")
                raise ValueError(
                    "Invalid file plan: file creation must be a single type_text action. "
                    "Cannot combine launch_app (read) with type_text (create)."
                )
            
            # Verify the single action is type_text
            if file_actions[0].action_type != "type_text":
                raise ValueError(
                    "Invalid file plan: file creation requires type_text action type."
                )
        
        logger.info("File minimality validated")
    
    def _create_plan_deterministic(self, instruction: str) -> List[Union[Action, Observation]]:
        """
        Create plan using deterministic logic.
        
        Phase-2B: Supports both Actions and Observations (e.g., file reads).
        
        Args:
            instruction: Natural language task
            
        Returns:
            List of Action and/or Observation objects
        """
        logger.info("Using deterministic planner")
        
        # Phase-2B: Basic validation (read-intent rejection removed)
        self._validate_instruction(instruction)
        
        plan = self.parse_instruction(instruction)
        
        # Phase-3 Fix: Auto-repair save sequencing (filename injection)
        # Even deterministic plans need this if they use generic "save" shortcuts
        plan = self._repair_save_sequence(plan, instruction)
        
        # Log action vs observation counts
        actions = [item for item in plan if isinstance(item, Action)]
        observations = [item for item in plan if isinstance(item, Observation)]
        logger.info(f"Generated {len(plan)} item(s): {len(actions)} action(s), {len(observations)} observation(s)")
        
        return plan
    
    def _estimate_actions(self, instruction: str) -> int:
        """
        Estimate the number of actions required for an instruction.
        Used for recursive task decomposition heuristics.
        """
        instruction_lower = instruction.lower()
        count = 0
        
        # Action verbs (approximate 1 action each)
        verbs = [
            "open ", "launch ", "start ", "run ", 
            "close ", "exit ", "quit ", 
            "wait ", "focus ", "switch to ",
            "verify ", "check "
        ]
        for v in verbs:
            count += instruction_lower.count(v)
            
        # Typing (approximate 1 action)
        if "type " in instruction_lower or "write " in instruction_lower:
            count += instruction_lower.count("type ") + instruction_lower.count("write ")
            
        # Save operations (complex interactions)
        if "save as" in instruction_lower:
            count += 4 # click file -> save as -> type -> enter
        elif "save" in instruction_lower:
            count += 3 # click save -> potential dialog handling (conservatively high)
            
        # Clicks/Interactions
        if "click" in instruction_lower or "press" in instruction_lower:
             count += instruction_lower.count("click") + instruction_lower.count("press")
             
        # Fallback: non-empty string is at least 1 action
        if count == 0 and len(instruction.strip()) > 0:
            count = 1
            
        return count

    def _recursive_decompose(self, instruction: str) -> List[str]:
        """
        Recursively decompose instruction based on complexity estimates.
        """
        instruction = instruction.strip()
        if not instruction:
            return []
            
        # Check complexity
        est_actions = self._estimate_actions(instruction)
        
        # If safe, return as is
        if est_actions <= self.max_actions:
            return [instruction]
            
        logger.info(f"Decomposing complex task (est {est_actions} actions): '{instruction}'")
        
        import re
        
        # Level 1: Strong separators (Explicit steps)
        # Semicolon, "then", "and then"
        strong_pattern = r';\s*|\s+,?\s*then\s+|\s+and\s+then\s+'
        parts = re.split(strong_pattern, instruction, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
        
        # If strong split occurred, recurse on parts
        if len(parts) > 1:
            results = []
            for p in parts:
                results.extend(self._recursive_decompose(p))
            return results
            
        # Level 2: Weak separators (Natural language lists)
        # Comma, "and"
        # Only reached if complexity is high and no strong separators found
        weak_pattern = r',|\s+and\s+'
        parts = re.split(weak_pattern, instruction, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) > 1:
            results = []
            for p in parts:
                results.extend(self._recursive_decompose(p))
            return results
            
        # If we can't split further but it's still complex, we have to return it
        logger.warning(f"Could not decompose complex task further: '{instruction}'")
        return [instruction]

    def _decompose_instruction(self, instruction: str) -> List[str]:
        """
        Decompose a complex instruction using recursive complexity analysis.
        """
        sub_instructions = self._recursive_decompose(instruction)
        
        if len(sub_instructions) > 1:
            logger.info(f"Task decomposition triggered. Split into {len(sub_instructions)} parts: {sub_instructions}")
            
        return sub_instructions

    def create_plan_graph(self, instruction: str, context: Optional[List[ObservationResult]] = None) -> List[PlanGraph]:
        """
        Create structured plan graph(s) from instruction.
        
        Phase-5A: Converts plan list into PlanGraph with metadata.
        Phase-6: Automatic segmentation of mixed contexts.
        Phase-7: Automatic task decomposition (pre-planning).
        Phase-11: Integrated vision context.
        
        Args:
            instruction: Natural language task
            context: Optional list of ObservationResults
            
        Returns:
            List of PlanGraph objects (sequential sub-plans)
        """
        from datetime import datetime
        
        # Step 1: Decompose Instruction (Pre-planning)
        sub_tasks = self._decompose_instruction(instruction)
        
        all_plan_graphs = []
        
        for task_idx, sub_task in enumerate(sub_tasks):
            logger.info(f"Planning for sub-task {task_idx+1}/{len(sub_tasks)}: '{sub_task}'")
            
            # Generate plan for this sub-task
            try:
                # Pass context only to the first subtask purely or all?
                # Probably all, as context is global awareness.
                plan_items = self.create_plan(sub_task, context=context)
            except Exception as e:
                logger.error(f"Planning failed for sub-task '{sub_task}': {e}")
                # We stop mostly to prevent partial execution in a broken chain?
                # Or continue? Safer to abort if a dependency fails.
                raise e

            # Segment items by context (Post-planning segmentation)
            segments = []
            current_segment_items = []
            current_context = None
            
            for item in plan_items:
                # Determine item context
                item_context = item.context
                
                # Start first segment
                if current_context is None:
                    current_context = item_context
                    current_segment_items.append(item)
                    continue
                
                # Check for context switch
                if item_context != current_context:
                    logger.info(f"Context switch detected: {current_context} -> {item_context}. Starting new plan segment.")
                    segments.append(current_segment_items)
                    current_segment_items = [item]
                    current_context = item_context
                else:
                    current_segment_items.append(item)
            
            # Add final segment
            if current_segment_items:
                segments.append(current_segment_items)
            
            # Create PlanGraph for each segment
            for i, segment_items in enumerate(segments):
                # Convert to PlanStep objects
                steps = []
                for j, item in enumerate(segment_items):
                    step_id = j + 1
                    
                    # Infer intent/outcome
                    intent = self._infer_intent(item)
                    expected_outcome = self._infer_expected_outcome(item)
                    
                    # Dependencies (sequential)
                    dependencies = [j] if j > 0 else []
                    
                    # Check for verification/approval requirements (Phase-11)
                    requires_approval = False
                    if isinstance(item, Action) and item.verify:
                        requires_approval = item.verify.get("requires_approval", False)
                        reason = item.verify.get("reason", "")
                        if reason:
                            intent += f" (Note: {reason})"

                    step = PlanStep(
                        step_id=step_id,
                        item=item,
                        intent=intent,
                        expected_outcome=expected_outcome,
                        dependencies=dependencies,
                        requires_approval=requires_approval
                    )
                    steps.append(step)
                
                # Create graph object
                # Source instruction includes context (Sub-task + Segment)
                part_info = ""
                if len(sub_tasks) > 1:
                    part_info += f"Task {task_idx+1}/{len(sub_tasks)}"
                if len(segments) > 1:
                    part_info += f", Seg {i+1}/{len(segments)}"
                
                final_instruction = sub_task if not part_info else f"{sub_task} ({part_info})"
                
                graph = PlanGraph(
                    instruction=final_instruction,
                    steps=steps
                )
                all_plan_graphs.append(graph)
                
        logger.info(f"Total plan composition: {len(all_plan_graphs)} graph(s) generated from {len(sub_tasks)} sub-task(s)")
        return all_plan_graphs
    
    def _infer_intent(self, item: Union[Action, Observation]) -> str:
        """
        Infer human-readable intent from action/observation.
        
        Phase-5A: Simple mapping for common action types.
        """
        if isinstance(item, Action):
            action_type = item.action_type
            target = item.target or ""
            text = item.text or ""
            
            if action_type == "launch_app":
                if target.startswith("http"):
                    return f"Navigate to {target}"
                else:
                    return f"Launch {target} application"
            elif action_type == "type_text":
                text_preview = text[:30] + "..." if len(text) > 30 else text
                return f"Type text '{text_preview}'"
            elif action_type == "focus_window":
                return f"Focus {target} window"
            elif action_type == "close_app":
                return f"Close {target} application"
            elif action_type == "wait":
                return f"Wait {target} seconds"
            else:
                return f"Execute {action_type}"
        else:
            # Observation
            obs_type = item.observation_type
            target = item.target or ""
            
            if obs_type == "read_text":
                return f"Read text from {target}"
            elif obs_type == "query_element":
                return f"Query element {target}"
            else:
                return f"Observe {obs_type}"
    
    def _infer_expected_outcome(self, item: Union[Action, Observation]) -> str:
        """
        Infer expected outcome from action/observation.
        
        Phase-5A: Simple outcome descriptions.
        """
        if isinstance(item, Action):
            action_type = item.action_type
            target = item.target or ""
            
            if action_type == "launch_app":
                if target.startswith("http"):
                    return f"Browser navigates to {target}"
                else:
                    return f"{target} window appears"
            elif action_type == "type_text":
                return "Text appears in focused element"
            elif action_type == "focus_window":
                return f"{target} window becomes active"
            elif action_type == "close_app":
                return f"{target} window closes"
            elif action_type == "wait":
                return f"Pause for {target} seconds"
            else:
                return "Action completes successfully"
        else:
            # Observation
            return "Data retrieved successfully"

