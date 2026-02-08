"""
Policy Engine - The Gatekeeper
Validates actions against safety rules defined in policy.yaml.

Enforces whitelist/blacklist, financial limits, and destructive action prevention.
"""
import logging
from pathlib import Path
from typing import Optional
import yaml
from common.actions import Action

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Middleware that sits between the Planner and Controller.
    
    Intercepts all actions and validates them against policy.yaml rules.
    No action can reach the Controller without Policy approval.
    """
    
    def __init__(self, policy_path: str):
        """
        Initialize the policy engine.
        
        Args:
            policy_path: Path to policy.yaml file
        """
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy()
        logger.info(f"PolicyEngine initialized from {policy_path}")
    
    def _load_policy(self) -> dict:
        """
        Load and parse policy.yaml.
        
        Returns:
            Parsed policy dictionary
            
        Raises:
            FileNotFoundError: If policy file doesn't exist
            yaml.YAMLError: If policy file is malformed
        """
        if not self.policy_path.exists():
            raise FileNotFoundError(f"Policy file not found: {self.policy_path}")
        
        with open(self.policy_path, 'r') as f:
            policy = yaml.safe_load(f)
        
        logger.info(f"Loaded policy version {policy.get('version', 'unknown')}")
        return policy
    
    def validate_action(self, action: Action) -> tuple[bool, Optional[str]]:
        """
        Validate an action against policy rules.
        
        Phase-2A: Context-aware validation (desktop/web/file).
        Phase-2B: Market analysis safety constraints.
        
        Args:
            action: Action to validate
            
        Returns:
            Tuple of (is_approved: bool, reason: Optional[str])
        """
        if action.context == "desktop":
            return self._validate_desktop_action(action)
        elif action.context == "web":
            return self._validate_web_action(action)
        elif action.context == "file":
            return self._validate_file_action(action)
        elif action.context == "market_analysis":
            return self._check_market_analysis_action(action)
        else:
            return (False, f"Unknown context: {action.context}")
    
    def _validate_desktop_action(self, action: Action) -> tuple[bool, Optional[str]]:
        """Validate desktop action."""
        if action.action_type == "launch_app":
            return self._validate_launch_app(action)
        elif action.action_type == "type_text":
            return (True, None)
        elif action.action_type == "close_app":
            return self._validate_close_app(action)
        elif action.action_type == "focus_window":
            return self._validate_focus_window(action)
        elif action.action_type == "click_control":
             # Safe action, operates on existing UI
            return (True, None)
        elif action.action_type == "wait":
            return self._validate_wait(action)
        else:
            return (False, f"Unknown action type: {action.action_type}")
    
    def _validate_web_action(self, action: Action) -> tuple[bool, Optional[str]]:
        """Validate web action against allowed domains."""
        browser_policy = self.policy.get("browser", {})
        if not browser_policy.get("enabled", False):
            return (False, "Browser access is disabled by policy")
        
        if action.action_type == "launch_app":
            url = action.target
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            allowed = browser_policy.get("allowed_domains", [])
            if not any(domain.endswith(d.replace("*.", "")) for d in allowed):
                return (False, f"Domain not allowed: {domain}")
            return (True, None)
        return (True, None)
    
    def _validate_file_action(self, action: Action) -> tuple[bool, Optional[str]]:
        """Validate file action."""
        file_policy = self.policy.get("filesystem", {})
        if action.action_type == "close_app":
            return (False, "close_app not supported for file context")
        return (True, None)
    
    def _validate_launch_app(self, action: Action) -> tuple[bool, Optional[str]]:
        """
        Validate app launch against whitelist/blacklist.
        
        Args:
            action: launch_app action
            
        Returns:
            (approved, reason) tuple
        """
        target = action.target
        if not target:
            return (False, "No target specified for launch_app")
        
        # Get whitelist and blacklist
        apps_policy = self.policy.get("apps", {})
        whitelist = apps_policy.get("whitelist", [])
        blacklist = apps_policy.get("blacklist", [])
        
        # Normalize target: check both as-is and with .exe suffix
        target_variants = [target]
        if not target.endswith(".exe"):
            target_variants.append(f"{target}.exe")
        
        # Check blacklist first (higher priority)
        for variant in target_variants:
            if variant in blacklist:
                logger.warning(f"[FAIL] DENIED: {target} is blacklisted")
                return (False, f"Application '{target}' is blacklisted by policy")
        
        # Check whitelist
        for variant in target_variants:
            if variant in whitelist:
                logger.info(f"[OK] APPROVED: {target} is whitelisted")
                return (True, None)
        
        # Not in whitelist
        logger.warning(f"[FAIL] DENIED: {target} not in whitelist")
        return (False, f"Application '{target}' is not in the whitelist")
    
    def _validate_close_app(self, action: Action) -> tuple[bool, Optional[str]]:
        """
        Validate close_app action.
        
        Phase-4A: MUST require whitelist approval (same as launch_app).
        """
        target = action.target
        apps_policy = self.policy.get("apps", {})
        whitelist = apps_policy.get("whitelist", [])
        blacklist = apps_policy.get("blacklist", [])
        
        # Normalize target: check both as-is and with .exe suffix
        target_variants = [target]
        if not target.endswith(".exe"):
            target_variants.append(f"{target}.exe")
        
        # Check blacklist first (higher priority)
        for variant in target_variants:
            if variant in blacklist:
                logger.warning(f"[FAIL] DENIED: Cannot close blacklisted app {target}")
                return (False, f"Cannot close blacklisted application '{target}'")
        
        # Check whitelist - MUST be whitelisted
        for variant in target_variants:
            if variant in whitelist:
                logger.info(f"[OK] APPROVED: Can close whitelisted app {target}")
                return (True, None)
        
        # Not in whitelist - DENY
        logger.warning(f"[FAIL] DENIED: {target} not in whitelist")
        return (False, f"Application '{target}' is not in the whitelist")
    
    def _validate_wait(self, action: Action) -> tuple[bool, Optional[str]]:
        """
        Validate wait action.
        
        Phase-4A: Always allow (duration validation happens in controller).
        """
        return (True, None)
    
    def _validate_focus_window(self, action: Action) -> tuple[bool, Optional[str]]:
        """
        Validate focus_window action.
        
        Phase-4A: Allow focusing windows to support multi-window workflows (e.g. Save As).
        Security is managed by launch_app whitelist preventing unauthorized apps from opening.
        """
        return (True, None)
    
    def requires_confirmation(self, action: Action) -> bool:
        """
        Check if an action requires user confirmation.
        
        Args:
            action: Action to check
            
        Returns:
            True if user confirmation popup should be shown
        """
        # Phase-0: No financial/destructive actions supported
        # Future: Check trading.require_confirmation, shopping.require_confirmation
        return False
    
    def _check_market_analysis_action(self, action: Action) -> tuple[bool, Optional[str]]:
        """
        Phase-2B: Validate market analysis actions (read-only mode).
        
        CRITICAL: Enforce strict read-only constraints.
        
        Args:
            action: Action with context="market_analysis"
            
        Returns:
            (approved, reason) tuple
        """
        # Get market analysis config
        ma_config = self.policy.get("market_analysis", {})
        if not ma_config.get("enabled", False):
            return (False, "Market analysis is disabled in policy")
        
        # Verify read-only mode
        if ma_config.get("mode") != "read_only":
            return (False, "Market analysis must be in read-only mode")
        
        # Get safety constraints
        safety = ma_config.get("safety", {})
        
        # CRITICAL CHECKS (NON-NEGOTIABLE)
        
        # 1. NO chart drawing
        if safety.get("allow_chart_drawing", True) == True:
            return (False, "SAFETY VIOLATION: Chart drawing must be disabled")
        
        # 2. NO trading
        if safety.get("allow_trading", True) == True:
            return (False, "SAFETY VIOLATION: Trading must be disabled")
        
        # 3. NO coordinate clicks
        if safety.get("allow_coordinate_clicks", True) == True:
            return (False, "SAFETY VIOLATION: Coordinate clicks must be disabled")
        
        # 4. NO chart manipulation
        if safety.get("allow_chart_manipulation", True) == True:
            return (False, "SAFETY VIOLATION: Chart manipulation must be disabled")
        
        # 5. ONLY observation actions allowed
        if action.action_type not in ["observe_dom", "observe_vision"]:
            return (False, f"Market analysis only allows observation actions, got: {action.action_type}")
        
        # 6. NO coordinates on ANY action
        if action.coordinates is not None:
            return (False, "SAFETY VIOLATION: Coordinates not allowed in market analysis")
        
        logger.info(f"[OK] Market analysis action approved: {action.action_type}")
        return (True, None)

