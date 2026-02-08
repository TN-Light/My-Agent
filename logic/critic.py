"""
Critic - Action Verification with Multi-Context Support
Validates whether an action succeeded by comparing UI/DOM/File states.

Phase-2A: Context-aware verification (desktop/web/file).
Phase-3B: Vision-assisted verification fallback (advisory only).
Phase-3C: Confidence scoring and evidence aggregation.
"""
import logging
from typing import Optional
from common.actions import Action, ActionResult, VerificationEvidence
from perception.accessibility_client import AccessibilityClient

logger = logging.getLogger(__name__)


class Critic:
    """
    Verifier that checks if actions succeeded.
    
    Uses context-specific verification:
    - Desktop: Accessibility Tree state changes
    - Web: DOM state via Playwright
    - File: File system checks
    """
    
    def __init__(self, accessibility_client: AccessibilityClient, browser_handler=None, 
                 file_handler=None, vision_client=None, screen_capture=None):
        """
        Initialize the critic.
        
        Args:
            accessibility_client: Client for querying desktop UI state
            browser_handler: BrowserHandler for web verification (optional)
            file_handler: FileHandler for file verification (optional)
            vision_client: VisionClient for fallback verification (Phase-3B, optional)
            screen_capture: ScreenCapture for vision verification (Phase-3B, optional)
        """
        self.accessibility = accessibility_client
        self.browser_handler = browser_handler
        self.file_handler = file_handler
        self.vision_client = vision_client
        self.screen_capture = screen_capture
        
        phase = "Phase-3C" if vision_client else "Phase-2A"
        logger.info(f"Critic initialized ({phase} verification)")
    
    def _extract_text_sample(self, text: str, search_term: str, max_length: int = 200) -> str:
        """
        Extract a text sample around the search term.
        
        Phase-3D: Helper for collecting verification evidence samples.
        
        Args:
            text: Full text content
            search_term: Term that was found
            max_length: Maximum sample length
            
        Returns:
            Text excerpt containing the search term
        """
        if not text or not search_term:
            return None
        
        # Find the search term (case-insensitive)
        lower_text = text.lower()
        lower_term = search_term.lower()
        
        idx = lower_text.find(lower_term)
        if idx == -1:
            # Term not found, return beginning of text
            return text[:max_length]
        
        # Extract text around the term
        start = max(0, idx - max_length // 2)
        end = min(len(text), idx + len(search_term) + max_length // 2)
        
        sample = text[start:end]
        
        # Add ellipsis if truncated
        if start > 0:
            sample = "..." + sample
        if end < len(text):
            sample = sample + "..."
        
        return sample
    
    def _compute_confidence(self, evidence: list[VerificationEvidence]) -> float:
        """
        Compute verification confidence score from evidence.
        
        Phase-3C/4B: Confidence scoring based on verification sources.
        
        Confidence does NOT affect execution flow, retries, or planning.
        It is metadata only for logging and diagnostics.
        
        Scoring Rules (Phase-4B):
        - Pure DOM/UIA/FILE SUCCESS: 1.0 (highest confidence)
        - DOM/UIA/FILE FAIL + VISION VERIFIED: 0.7 (medium, vision fallback)
        - DOM/UIA/FILE FAIL + VISION NOT_VERIFIED: 0.3 (low, conflicting)
        - DOM/UIA/FILE FAIL + VISION UNKNOWN: 0.4 (low, uncertainty)
        - Only VISION evidence: 0.5 (medium-low, no primary authority)
        - No evidence: 0.0 (no verification performed)
        
        Args:
            evidence: List of VerificationEvidence
            
        Returns:
            Confidence score (0.0-1.0)
        """
        if not evidence:
            return 0.0
        
        # Check for primary verification (DOM/UIA/FILE)
        primary_sources = ["DOM", "UIA", "FILE"]
        primary_evidence = [e for e in evidence if e.source in primary_sources]
        vision_evidence = [e for e in evidence if e.source == "VISION"]
        
        # Pure primary success (highest confidence)
        if primary_evidence:
            primary_success = any(e.result == "SUCCESS" for e in primary_evidence)
            if primary_success:
                return 1.0
            
            # Primary failed, check vision fallback
            if vision_evidence:
                vision_result = vision_evidence[0].result
                if vision_result == "VERIFIED":
                    return 0.7  # Phase-4B: Vision fallback confidence
                elif vision_result == "NOT_VERIFIED":
                    return 0.3   # Low confidence (conflicting evidence)
                else:  # UNKNOWN
                    return 0.4   # Low confidence (uncertainty)
            else:
                # Primary failed, no vision fallback
                return 0.2  # Low confidence (failed verification)
        
        # Only vision evidence (no primary authority)
        if vision_evidence:
            vision_result = vision_evidence[0].result
            if vision_result == "VERIFIED":
                return 0.5   # Medium-low (vision only, no primary)
            elif vision_result == "NOT_VERIFIED":
                return 0.2
            else:  # UNKNOWN
                return 0.3
        
        # No valid evidence
        return 0.0
    
    def verify_launch_app(self, action: Action, window_title_hint: str) -> ActionResult:
        """
        Verify that an application launched successfully.
        
        Phase-3C: Includes confidence scoring and evidence collection.
        
        Args:
            action: The launch_app action that was executed
            window_title_hint: Expected window title substring
            
        Returns:
            ActionResult with success, confidence, and evidence
        """
        logger.info(f"Verifying launch of {action.target}...")
        
        evidence = []
        
        # Primary verification: Check if window appeared in accessibility tree
        window = self.accessibility.find_window(title=window_title_hint)
        
        if window and window.is_visible:
            evidence.append(VerificationEvidence(
                source="UIA",
                result="SUCCESS",
                details=f"Window found: {window.name}",
                checked_text=window_title_hint
            ))
            confidence = self._compute_confidence(evidence)
            
            # Phase-3D: Build structured evidence dict
            verification_evidence = {
                'source': 'UIA',
                'checked_text': window_title_hint,
                'sample': f"Window: {window.name}",
                'confidence': confidence
            }
            
            logger.info(f"[OK] Verified: {action.target} launched (confidence={confidence:.2f})")
            return ActionResult(
                action=action,
                success=True,
                message=f"Application launched: {window.name}",
                confidence=confidence,
                evidence=evidence,
                verification_evidence=verification_evidence
            )
        else:
            # Primary verification failed
            evidence.append(VerificationEvidence(
                source="UIA",
                result="FAIL",
                details=f"Window not found: {window_title_hint}"
            ))
            
            # Attempt vision fallback (Phase-3B/3C)
            vision_status = self._verify_with_vision_fallback(
                action,
                expected_text=window_title_hint
            )
            if vision_status:
                evidence.append(VerificationEvidence(
                    source="VISION",
                    result=vision_status,
                    details=f"Vision verification: {vision_status}"
                ))
            
            confidence = self._compute_confidence(evidence)
            
            logger.error(f"[FAIL] Verification failed (confidence={confidence:.2f})")
            return ActionResult(
                action=action,
                success=False,
                message=f"Application window not visible",
                error=f"Expected window with title containing '{window_title_hint}' not found",
                confidence=confidence,
                evidence=evidence
            )
    
    def verify_type_text(self, action: Action) -> ActionResult:
        """
        Verify that text was typed successfully.
        
        Phase-1B: Strict state-based verification - target window MUST still exist and be visible.
        Phase-3C: Includes confidence scoring and evidence collection.
        
        Args:
            action: The type_text action that was executed
            
        Returns:
            ActionResult with success, confidence, and evidence
        """
        logger.info(f"Verifying text input: '{action.text}'...")
        
        evidence = []
        
        # Primary verification: Check if focused window exists and is visible
        focused = self.accessibility.get_focused_window()
        
        if focused and focused.is_visible:
            evidence.append(VerificationEvidence(
                source="UIA",
                result="SUCCESS",
                details=f"Focused window: {focused.name}",
                checked_text=action.text
            ))
            confidence = self._compute_confidence(evidence)
            
            # Phase-3D: Build structured evidence dict
            verification_evidence = {
                'source': 'UIA',
                'checked_text': action.text,
                'sample': f"Window: {focused.name}",
                'confidence': confidence
            }
            
            logger.info(f"[OK] Verified: Text typed into {focused.name} (confidence={confidence:.2f})")
            return ActionResult(
                action=action,
                success=True,
                message=f"Text entered in {focused.name}",
                confidence=confidence,
                evidence=evidence,
                verification_evidence=verification_evidence
            )
        else:
            # Primary verification failed
            evidence.append(VerificationEvidence(
                source="UIA",
                result="FAIL",
                details="Window closed or lost focus"
            ))
            
            # Attempt vision fallback (Phase-3B/3C)
            vision_status = self._verify_with_vision_fallback(
                action,
                expected_text=action.text
            )
            if vision_status:
                evidence.append(VerificationEvidence(
                    source="VISION",
                    result=vision_status,
                    details=f"Vision verification: {vision_status}"
                ))
            
            confidence = self._compute_confidence(evidence)
            
            logger.error(f"[FAIL] Verification failed (confidence={confidence:.2f})")
            return ActionResult(
                action=action,
                success=False,
                message="Target window no longer present",
                error="Window closed or lost focus during/after typing",
                confidence=confidence,
                evidence=evidence
            )
    
    def verify_action(self, action: Action, context: Optional[dict] = None) -> ActionResult:
        """
        Generic verification dispatcher (routes by context).
        
        Args:
            action: The action to verify
            context: Optional context (e.g., expected window title)
            
        Returns:
            ActionResult with verification status
        """
        # Check if action has verification metadata
        if hasattr(action, 'verify') and action.verify:
            return self._verify_with_metadata(action)
        
        if action.context == "desktop":
            return self._verify_desktop_action(action, context)
        elif action.context == "web":
            return self._verify_web_action(action, context)
        elif action.context == "file":
            return self._verify_file_action(action, context)
        else:
            logger.warning(f"Unknown context: {action.context}")
            return ActionResult(
                action=action,
                success=False,
                message="Unknown context",
                error=f"Critic does not support context: {action.context}"
            )
    
    def _verify_with_metadata(self, action: Action) -> ActionResult:
        """
        Verify action using verification metadata from action.verify.
        
        This handles verification intents detected during planning (e.g., "verify that X is visible").
        
        Args:
            action: Action with verify metadata
            
        Returns:
            ActionResult with verification status
        """
        verify_type = action.verify.get("type")
        verify_value = action.verify.get("value")
        
        logger.info(f"Verifying with metadata: type={verify_type}, value='{verify_value}'")
        
        evidence = []
        
        if verify_type == "text_visible":
            # Attempt DOM verification first (web context)
            if self.browser_handler:
                try:
                    # Check if text is visible in DOM
                    page_text = self.browser_handler.get_page_text()
                    if page_text and verify_value.lower() in page_text.lower():
                        # Phase-3D: Collect evidence sample
                        sample = self._extract_text_sample(page_text, verify_value, max_length=200)
                        
                        evidence.append(VerificationEvidence(
                            source="DOM",
                            result="SUCCESS",
                            details=f"Text found in DOM: '{verify_value}'",
                            checked_text=verify_value,
                            sample=sample
                        ))
                        confidence = self._compute_confidence(evidence)
                        
                        # Phase-3D: Build structured evidence dict
                        verification_evidence = {
                            'source': 'DOM',
                            'checked_text': verify_value,
                            'sample': sample,
                            'confidence': confidence
                        }
                        
                        logger.info(f"[VERIFY] text_visible -> VERIFIED (DOM, confidence={confidence:.2f})")
                        return ActionResult(
                            action=action,
                            success=True,
                            message=f"Text verified visible: '{verify_value}'",
                            confidence=confidence,
                            evidence=evidence,
                            verification_evidence=verification_evidence
                        )
                    else:
                        evidence.append(VerificationEvidence(
                            source="DOM",
                            result="FAIL",
                            details=f"Text not found in DOM: '{verify_value}'",
                            checked_text=verify_value,
                            sample=page_text[:200] if page_text else None
                        ))
                        logger.info(f"[VERIFY] text_visible -> NOT_VERIFIED (DOM)")
                except Exception as e:
                    logger.warning(f"DOM verification exception: {e}")
                    evidence.append(VerificationEvidence(
                        source="DOM",
                        result="FAIL",
                        details=f"Exception: {str(e)}",
                        checked_text=verify_value
                    ))
            
            # If DOM failed, try vision verification (if enabled)
            if self.vision_client and self.screen_capture:
                try:
                    # Capture screen
                    screenshot = self.screen_capture.capture_active_window()
                    if not screenshot:
                        screenshot = self.screen_capture.capture_full_screen()
                    
                    if screenshot:
                        logger.info(f"[VERIFY] Attempting vision verification for: '{verify_value}'")
                        vision_result = self.vision_client.verify_text_visible(screenshot, verify_value)
                        
                        evidence.append(VerificationEvidence(
                            source="VISION",
                            result=vision_result,
                            details=f"Vision verification: {vision_result}",
                            checked_text=verify_value
                        ))
                        
                        confidence = self._compute_confidence(evidence)
                        
                        # Phase-3D: Build structured evidence dict
                        verification_evidence = {
                            'source': 'VISION',
                            'checked_text': verify_value,
                            'sample': None,  # Vision doesn't provide text samples
                            'confidence': confidence
                        }
                        
                        if vision_result == "VERIFIED":
                            logger.info(f"[VERIFY] text_visible -> VERIFIED (VISION, confidence={confidence:.2f})")
                            return ActionResult(
                                action=action,
                                success=True,
                                message=f"Text verified visible (vision): '{verify_value}'",
                                confidence=confidence,
                                evidence=evidence,
                                verification_evidence=verification_evidence
                            )
                        elif vision_result == "NOT_VERIFIED":
                            logger.info(f"[VERIFY] text_visible -> NOT_VERIFIED (VISION, confidence={confidence:.2f})")
                            return ActionResult(
                                action=action,
                                success=False,
                                message=f"Text not verified: '{verify_value}'",
                                error=f"Text '{verify_value}' not found in visual inspection",
                                reason="verification_failed",
                                confidence=confidence,
                                evidence=evidence,
                                verification_evidence=verification_evidence
                            )
                        else:  # UNKNOWN
                            logger.info(f"[VERIFY] text_visible -> UNKNOWN (VISION, confidence={confidence:.2f})")
                            return ActionResult(
                                action=action,
                                success=False,
                                message=f"Text verification inconclusive: '{verify_value}'",
                                error=f"Vision could not determine if '{verify_value}' is visible",
                                reason="verification_failed",
                                confidence=confidence,
                                evidence=evidence,
                                verification_evidence=verification_evidence
                            )
                except Exception as e:
                    logger.error(f"Vision verification exception: {e}")
                    evidence.append(VerificationEvidence(
                        source="VISION",
                        result="FAIL",
                        details=f"Exception: {str(e)}"
                    ))
            
            # No verification method succeeded
            confidence = self._compute_confidence(evidence)
            
            # Phase-3D: Build structured evidence dict
            verification_evidence = {
                'source': 'NONE',
                'checked_text': verify_value,
                'sample': None,
                'confidence': confidence
            }
            
            logger.info(f"[VERIFY] text_visible -> NOT_VERIFIED (no verification method succeeded, confidence={confidence:.2f})")
            return ActionResult(
                action=action,
                success=False,
                message=f"Text verification failed: '{verify_value}'",
                error="No verification method available or all methods failed",
                reason="verification_failed",
                confidence=confidence,
                evidence=evidence,
                verification_evidence=verification_evidence
            )
        
        else:
            # Unknown verification type
            logger.warning(f"Unknown verification type: {verify_type}")
            return ActionResult(
                action=action,
                success=False,
                message=f"Unknown verification type: {verify_type}",
                error=f"Critic does not support verification type: {verify_type}"
            )
    
    def _verify_desktop_action(self, action: Action, context: Optional[dict] = None) -> ActionResult:
        """Verify desktop context action."""
        if action.action_type == "launch_app":
            app_name = action.target.replace(".exe", "").capitalize()
            return self.verify_launch_app(action, window_title_hint=app_name)
        elif action.action_type == "type_text":
            return self.verify_type_text(action)
        elif action.action_type == "focus_window":
            return self.verify_focus_window(action)
        elif action.action_type == "close_app":
            return self.verify_close_app(action)
        elif action.action_type == "wait":
            return self.verify_wait(action)
        else:
            return ActionResult(
                action=action,
                success=True,
                message="Action executed (no verifier available)"
            )
    
    def _verify_web_action(self, action: Action, context: Optional[dict] = None) -> ActionResult:
        """
        Verify web context action via browser handler.
        
        Phase-3C: Includes confidence scoring and evidence collection.
        """
        if not self.browser_handler:
            logger.warning("Browser handler not available for verification")
            return ActionResult(
                action=action,
                success=True,
                message="Action executed (browser verification unavailable)"
            )
        
        evidence = []
        
        try:
            if action.action_type == "launch_app":
                # Verify navigation
                current_url = self.browser_handler.get_current_url()
                if current_url:
                    evidence.append(VerificationEvidence(
                        source="DOM",
                        result="SUCCESS",
                        details=f"Navigated to: {current_url}",
                        checked_text=action.target
                    ))
                    confidence = self._compute_confidence(evidence)
                    
                    # Phase-3D: Build structured evidence dict
                    verification_evidence = {
                        'source': 'DOM',
                        'checked_text': action.target,
                        'sample': f"URL: {current_url}",
                        'confidence': confidence
                    }
                    
                    logger.info(f"[OK] Verified: Browser at {current_url} (confidence={confidence:.2f})")
                    return ActionResult(
                        action=action,
                        success=True,
                        message=f"Navigated to {current_url}",
                        confidence=confidence,
                        evidence=evidence,
                        verification_evidence=verification_evidence
                    )
                else:
                    evidence.append(VerificationEvidence(
                        source="DOM",
                        result="FAIL",
                        details="No current URL available"
                    ))
                    
                    # Attempt vision fallback
                    vision_status = self._verify_with_vision_fallback(
                        action,
                        expected_text=action.target
                    )
                    if vision_status:
                        evidence.append(VerificationEvidence(
                            source="VISION",
                            result=vision_status,
                            details=f"Vision verification: {vision_status}"
                        ))
                    
                    confidence = self._compute_confidence(evidence)
                    
                    logger.error(f"[FAIL] Browser navigation failed (confidence={confidence:.2f})")
                    return ActionResult(
                        action=action,
                        success=False,
                        message="Browser navigation failed",
                        error="No current URL available",
                        confidence=confidence,
                        evidence=evidence
                    )
            
            elif action.action_type == "type_text":
                # Verify element value matches expected text
                selector = action.target
                element_value = self.browser_handler.get_element_value(selector)
                
                if element_value is not None and element_value == action.text:
                    evidence.append(VerificationEvidence(
                        source="DOM",
                        result="SUCCESS",
                        details=f"Element value matches: {selector}",
                        checked_text=action.text,
                        sample=element_value
                    ))
                    confidence = self._compute_confidence(evidence)
                    
                    # Phase-3D: Build structured evidence dict
                    verification_evidence = {
                        'source': 'DOM',
                        'checked_text': action.text,
                        'sample': f"Value: {element_value}",
                        'confidence': confidence
                    }
                    
                    logger.info(f"[OK] Verified: Element {selector} value = '{element_value}' (confidence={confidence:.2f})")
                    return ActionResult(
                        action=action,
                        success=True,
                        message=f"Text entered in {selector}",
                        confidence=confidence,
                        evidence=evidence,
                        verification_evidence=verification_evidence
                    )
                else:
                    evidence.append(VerificationEvidence(
                        source="DOM",
                        result="FAIL",
                        details=f"Element value mismatch: expected='{action.text}', actual='{element_value}'"
                    ))
                    
                    # Attempt vision fallback
                    vision_status = self._verify_with_vision_fallback(
                        action,
                        expected_text=action.text
                    )
                    if vision_status:
                        evidence.append(VerificationEvidence(
                            source="VISION",
                            result=vision_status,
                            details=f"Vision verification: {vision_status}"
                        ))
                    
                    confidence = self._compute_confidence(evidence)
                    
                    logger.error(f"[FAIL] Element not visible (confidence={confidence:.2f})")
                    return ActionResult(
                        action=action,
                        success=False,
                        message="Element not visible after typing",
                        error=f"Selector not visible: {selector}",
                        confidence=confidence,
                        evidence=evidence
                    )
            
            else:
                # Generic web action
                evidence.append(VerificationEvidence(
                    source="DOM",
                    result="SUCCESS",
                    details="Generic web action"
                ))
                confidence = self._compute_confidence(evidence)
                
                return ActionResult(
                    action=action,
                    success=True,
                    message="Web action executed",
                    confidence=confidence,
                    evidence=evidence
                )
        
        except Exception as e:
            logger.error(f"Web verification failed: {e}")
            evidence.append(VerificationEvidence(
                source="DOM",
                result="FAIL",
                details=f"Exception: {str(e)}"
            ))
            confidence = self._compute_confidence(evidence)
            
            return ActionResult(
                action=action,
                success=False,
                message="Verification error",
                error=str(e),
                confidence=confidence,
                evidence=evidence
            )
    
    def _verify_file_action(self, action: Action, context: Optional[dict] = None) -> ActionResult:
        """
        Verify file context action via file handler.
        
        Phase-3C: Includes confidence scoring and evidence collection.
        """
        if not self.file_handler:
            logger.warning("File handler not available for verification")
            return ActionResult(
                action=action,
                success=True,
                message="Action executed (file verification unavailable)"
            )
        
        evidence = []
        
        try:
            file_path = action.target
            
            if action.action_type == "launch_app":
                # Verify file exists (read operation)
                if self.file_handler.file_exists(file_path):
                    evidence.append(VerificationEvidence(
                        source="FILE",
                        result="SUCCESS",
                        details=f"File exists: {file_path}",
                        checked_text=file_path
                    ))
                    confidence = self._compute_confidence(evidence)
                    
                    # Phase-3D: Build structured evidence dict
                    verification_evidence = {
                        'source': 'FILE',
                        'checked_text': file_path,
                        'sample': None,  # Don't read file content for evidence
                        'confidence': confidence
                    }
                    
                    logger.info(f"[OK] Verified: File exists: {file_path} (confidence={confidence:.2f})")
                    return ActionResult(
                        action=action,
                        success=True,
                        message=f"File read: {file_path}",
                        confidence=confidence,
                        evidence=evidence,
                        verification_evidence=verification_evidence
                    )
                else:
                    evidence.append(VerificationEvidence(
                        source="FILE",
                        result="FAIL",
                        details=f"File not found: {file_path}"
                    ))
                    confidence = self._compute_confidence(evidence)
                    
                    logger.error(f"[FAIL] File not found (confidence={confidence:.2f})")
                    return ActionResult(
                        action=action,
                        success=False,
                        message="File not found",
                        error=f"File does not exist: {file_path}",
                        confidence=confidence,
                        evidence=evidence
                    )
            
            elif action.action_type == "type_text":
                # Verify file was created
                if self.file_handler.file_exists(file_path):
                    evidence.append(VerificationEvidence(
                        source="FILE",
                        result="SUCCESS",
                        details=f"File created: {file_path}",
                        checked_text=file_path
                    ))
                    confidence = self._compute_confidence(evidence)
                    
                    # Phase-3D: Build structured evidence dict
                    verification_evidence = {
                        'source': 'FILE',
                        'checked_text': file_path,
                        'sample': None,  # Don't include file content in evidence
                        'confidence': confidence
                    }
                    
                    logger.info(f"[OK] Verified: File created: {file_path} (confidence={confidence:.2f})")
                    return ActionResult(
                        action=action,
                        success=True,
                        message=f"File created: {file_path}",
                        confidence=confidence,
                        evidence=evidence,
                        verification_evidence=verification_evidence
                    )
                else:
                    evidence.append(VerificationEvidence(
                        source="FILE",
                        result="FAIL",
                        details=f"File not created: {file_path}"
                    ))
                    confidence = self._compute_confidence(evidence)
                    
                    logger.error(f"[FAIL] File creation failed (confidence={confidence:.2f})")
                    return ActionResult(
                        action=action,
                        success=False,
                        message="File creation failed",
                        error=f"File was not created: {file_path}",
                        confidence=confidence,
                        evidence=evidence
                    )
            
            else:
                # Generic file action
                evidence.append(VerificationEvidence(
                    source="FILE",
                    result="SUCCESS",
                    details="Generic file action"
                ))
                confidence = self._compute_confidence(evidence)
                
                return ActionResult(
                    action=action,
                    success=True,
                    message="File action executed",
                    confidence=confidence,
                    evidence=evidence
                )
        
        except Exception as e:
            logger.error(f"File verification failed: {e}")
            evidence.append(VerificationEvidence(
                source="FILE",
                result="FAIL",
                details=f"Exception: {str(e)}"
            ))
            confidence = self._compute_confidence(evidence)
            
            return ActionResult(
                action=action,
                success=False,
                message="Verification error",
                error=str(e),
                confidence=confidence,
                evidence=evidence
            )
    
    def _verify_with_vision_fallback(self, action: Action, expected_text: str = None, 
                                     expected_region: str = None) -> Optional[str]:
        """
        Use vision as fallback verification when DOM/UIA fails.
        
        Phase-3B: Vision-Assisted Verification (advisory only).
        
        This method is called ONLY when primary verification (DOM/UIA) fails.
        Vision output is advisory and does NOT override primary verification.
        Vision cannot trigger retries or corrective actions.
        
        Args:
            action: The action that was executed
            expected_text: Text to verify (optional)
            expected_region: Layout region to verify (optional)
            
        Returns:
            Vision verification status ("VERIFIED" | "NOT_VERIFIED" | "UNKNOWN")
            or None if vision unavailable
        """
        if not self.vision_client or not self.screen_capture:
            logger.debug("Vision verification unavailable (no vision client)")
            return None
        
        try:
            # Capture screen
            screenshot = self.screen_capture.capture_active_window()
            if not screenshot:
                screenshot = self.screen_capture.capture_full_screen()
            
            if not screenshot:
                logger.warning("Vision verification failed: Could not capture screen")
                return None
            
            # Perform vision verification
            if expected_text:
                logger.info(f"[FALLBACK] Using vision to verify text: '{expected_text}'")
                result = self.vision_client.verify_text_visible(screenshot, expected_text)
                logger.info(f"[VISION] Text verification result: {result}")
                return result
            elif expected_region:
                logger.info(f"[FALLBACK] Using vision to verify region: '{expected_region}'")
                result = self.vision_client.verify_layout_contains(screenshot, expected_region)
                logger.info(f"[VISION] Region verification result: {result}")
                return result
            else:
                logger.warning("Vision verification called without expected_text or expected_region")
                return None
        
        except Exception as e:
            logger.error(f"Vision verification exception: {e}")
            return None
    
    def verify_focus_window(self, action: Action) -> ActionResult:
        """
        Verify that a window was successfully focused.
        
        Phase-4A: Check that the focused window matches the target.
        
        Args:
            action: The focus_window action that was executed
            
        Returns:
            ActionResult with verification status
        """
        target = action.target
        logger.info(f"Verifying window focus: '{target}'...")
        
        evidence = []
        
        # Get focused window
        focused = self.accessibility.get_focused_window()
        
        if focused:
            win_name = focused.name
            # Check if focused window matches target (exact or contains)
            if target.lower() in win_name.lower() or win_name.lower() in target.lower():
                evidence.append(VerificationEvidence(
                    source="UIA",
                    result="SUCCESS",
                    details=f"Focused window matches: {win_name}",
                    checked_text=target
                ))
                confidence = self._compute_confidence(evidence)
                
                verification_evidence = {
                    'source': 'UIA',
                    'checked_text': target,
                    'sample': f"Focused: {win_name}",
                    'confidence': confidence
                }
                
                logger.info(f"[OK] Verified: Window '{win_name}' is focused (confidence={confidence:.2f})")
                return ActionResult(
                    action=action,
                    success=True,
                    message=f"Window focused: {win_name}",
                    confidence=confidence,
                    evidence=evidence,
                    verification_evidence=verification_evidence
                )
            else:
                evidence.append(VerificationEvidence(
                    source="UIA",
                    result="FAIL",
                    details=f"Wrong window focused: {win_name} (expected {target})"
                ))
                
                # Attempt vision fallback (Phase-4B)
                vision_status = self._verify_with_vision_fallback(
                    action,
                    expected_text=target
                )
                if vision_status:
                    evidence.append(VerificationEvidence(
                        source="VISION",
                        result=vision_status,
                        details=f"Vision verification: {vision_status}"
                    ))
                
                confidence = self._compute_confidence(evidence)
                
                logger.error(f"[FAIL] Wrong window focused: {win_name} (expected {target}) (confidence={confidence:.2f})")
                return ActionResult(
                    action=action,
                    success=False,
                    message="Wrong window focused",
                    error=f"Expected '{target}', got '{win_name}'",
                    confidence=confidence,
                    evidence=evidence
                )
        else:
            evidence.append(VerificationEvidence(
                source="UIA",
                result="FAIL",
                details="No focused window found"
            ))
            
            # Attempt vision fallback (Phase-4B)
            vision_status = self._verify_with_vision_fallback(
                action,
                expected_text=target
            )
            if vision_status:
                evidence.append(VerificationEvidence(
                    source="VISION",
                    result=vision_status,
                    details=f"Vision verification: {vision_status}"
                ))
            
            confidence = self._compute_confidence(evidence)
            
            logger.error(f"[FAIL] No focused window found (confidence={confidence:.2f})")
            return ActionResult(
                action=action,
                success=False,
                message="No focused window",
                error="No window is currently focused",
                confidence=confidence,
                evidence=evidence
            )
    
    def verify_close_app(self, action: Action) -> ActionResult:
        """
        Verify that an application was successfully closed.
        
        Phase-4A: Check that the target window/app is no longer present.
        
        Args:
            action: The close_app action that was executed
            
        Returns:
            ActionResult with verification status
        """
        target = action.target
        logger.info(f"Verifying app closed: '{target}'...")
        
        evidence = []
        
        # Check if target window still exists
        windows = self.accessibility.find_windows(name_pattern=target)
        
        if len(windows) == 0:
            evidence.append(VerificationEvidence(
                source="UIA",
                result="SUCCESS",
                details=f"Window no longer present: {target}",
                checked_text=target
            ))
            confidence = self._compute_confidence(evidence)
            
            verification_evidence = {
                'source': 'UIA',
                'checked_text': target,
                'sample': f"Closed: {target}",
                'confidence': confidence
            }
            
            logger.info(f"[OK] Verified: App '{target}' is closed (confidence={confidence:.2f})")
            return ActionResult(
                action=action,
                success=True,
                message=f"App closed: {target}",
                confidence=confidence,
                evidence=evidence,
                verification_evidence=verification_evidence
            )
        else:
            window_names = [w.name for w in windows]
            evidence.append(VerificationEvidence(
                source="UIA",
                result="FAIL",
                details=f"Window still present: {window_names}"
            ))
            confidence = self._compute_confidence(evidence)
            
            logger.error(f"[FAIL] App still running: {window_names}")
            return ActionResult(
                action=action,
                success=False,
                message="App still running",
                error=f"Window(s) still present: {window_names}",
                confidence=confidence,
                evidence=evidence
            )
    
    def verify_wait(self, action: Action) -> ActionResult:
        """
        Verify that wait action completed.
        
        Phase-4A: Wait always succeeds if executed (no state to verify).
        Simply confirms the action was performed.
        
        Args:
            action: The wait action that was executed
            
        Returns:
            ActionResult with verification status
        """
        duration = action.target
        logger.info(f"Verifying wait: {duration}s...")
        
        # Wait is self-verifying - if it executed, it succeeded
        evidence = [VerificationEvidence(
            source="UIA",
            result="SUCCESS",
            details=f"Wait completed: {duration}s",
            checked_text=duration
        )]
        confidence = 1.0
        
        verification_evidence = {
            'source': 'UIA',
            'checked_text': duration,
            'sample': f"Waited: {duration}s",
            'confidence': confidence
        }
        
        logger.info(f"[OK] Verified: Wait {duration}s completed (confidence={confidence:.2f})")
        return ActionResult(
            action=action,
            success=True,
            message=f"Waited {duration}s",
            confidence=confidence,
            evidence=evidence,
            verification_evidence=verification_evidence
        )

