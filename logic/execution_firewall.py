"""
PHASE-9: EXECUTION FIREWALL
Purpose: Last line of defense before ANY order reaches broker

NON-NEGOTIABLE RULES:
1. Dumb and brutal (no intelligence, only checks)
2. Hard blocks on ANY violation
3. No retries, no exceptions
4. Logs all blocks for audit

HARD BLOCKS:
- Overconfidence flags active
- Unresolved Phase-8 expectancy (no proven edge)
- Missing confirmations (ASSISTED mode)
- API/connection failures
- Latency anomalies
- Request throttling

Philosophy:
"This module must be dumb and brutal. No exceptions. Ever."
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import time


@dataclass
class FirewallResult:
    """Result of firewall check."""
    
    passed: bool
    reason: str
    blocked_category: Optional[str] = None
    
    def __bool__(self) -> bool:
        """Allow boolean evaluation."""
        return self.passed


class ExecutionFirewall:
    """
    Last line of defense before order execution.
    
    Dumb and brutal - no intelligence, only hard checks.
    """
    
    # Throttling limits
    MAX_REQUESTS_PER_MINUTE = 10
    MAX_REQUESTS_PER_HOUR = 100
    
    # Latency threshold (milliseconds)
    MAX_LATENCY_MS = 5000
    
    def __init__(self):
        """Initialize execution firewall."""
        self.request_history = []
        self.blocked_count = 0
        self.last_api_check = None
        self.api_healthy = True
    
    def check(
        self,
        overconfidence_flag: bool,
        expectancy_resolved: bool,
        expectancy_value: float,
        confirmation_required: bool,
        confirmation_received: bool,
        api_healthy: bool,
        latency_ms: Optional[float] = None
    ) -> FirewallResult:
        """
        Perform firewall checks.
        
        ALL checks must pass. Single failure = HARD BLOCK.
        
        Args:
            overconfidence_flag: Whether overconfidence warning is active
            expectancy_resolved: Whether Phase-8 expectancy is resolved
            expectancy_value: Phase-8 expectancy value
            confirmation_required: Whether human confirmation required
            confirmation_received: Whether confirmation was received
            api_healthy: Whether API/broker connection is healthy
            latency_ms: Current latency (milliseconds)
        
        Returns:
            FirewallResult (passed=True/False with reason)
        """
        current_time = datetime.now()
        
        # ========================================
        # CHECK 1: Overconfidence Flag
        # ========================================
        if overconfidence_flag:
            self.blocked_count += 1
            return FirewallResult(
                passed=False,
                reason="OVERCONFIDENCE_FLAG_ACTIVE: System detected bias, execution blocked",
                blocked_category="OVERCONFIDENCE"
            )
        
        # ========================================
        # CHECK 2: Expectancy Resolution
        # ========================================
        if not expectancy_resolved:
            self.blocked_count += 1
            return FirewallResult(
                passed=False,
                reason="EXPECTANCY_UNRESOLVED: No proven edge, execution blocked",
                blocked_category="EXPECTANCY"
            )
        
        # ========================================
        # CHECK 3: Expectancy Value
        # ========================================
        if expectancy_value <= 0:
            self.blocked_count += 1
            return FirewallResult(
                passed=False,
                reason=f"NEGATIVE_EXPECTANCY: Expectancy={expectancy_value:.2f}R ≤ 0, execution blocked",
                blocked_category="EXPECTANCY"
            )
        
        # ========================================
        # CHECK 4: Human Confirmation
        # ========================================
        if confirmation_required and not confirmation_received:
            self.blocked_count += 1
            return FirewallResult(
                passed=False,
                reason="CONFIRMATION_MISSING: ASSISTED mode requires human confirmation",
                blocked_category="CONFIRMATION"
            )
        
        # ========================================
        # CHECK 5: API Health
        # ========================================
        if not api_healthy:
            self.blocked_count += 1
            return FirewallResult(
                passed=False,
                reason="API_UNHEALTHY: Broker/API connection failed, execution blocked",
                blocked_category="API"
            )
        
        # ========================================
        # CHECK 6: Latency Anomaly
        # ========================================
        if latency_ms is not None and latency_ms > self.MAX_LATENCY_MS:
            self.blocked_count += 1
            return FirewallResult(
                passed=False,
                reason=f"LATENCY_ANOMALY: {latency_ms:.0f}ms > {self.MAX_LATENCY_MS}ms threshold",
                blocked_category="LATENCY"
            )
        
        # ========================================
        # CHECK 7: Request Throttling
        # ========================================
        throttle_result = self._check_throttling(current_time)
        if not throttle_result.passed:
            return throttle_result
        
        # ========================================
        # ALL CHECKS PASSED
        # ========================================
        self.request_history.append(current_time)
        
        return FirewallResult(
            passed=True,
            reason="ALL_CHECKS_PASSED: Firewall cleared",
            blocked_category=None
        )
    
    def _check_throttling(self, current_time: datetime) -> FirewallResult:
        """
        Check request throttling limits.
        
        Args:
            current_time: Current timestamp
        
        Returns:
            FirewallResult
        """
        # Clean old requests (older than 1 hour)
        cutoff_time = current_time - timedelta(hours=1)
        self.request_history = [
            t for t in self.request_history
            if t > cutoff_time
        ]
        
        # Count requests in last minute
        minute_cutoff = current_time - timedelta(minutes=1)
        requests_last_minute = sum(
            1 for t in self.request_history
            if t > minute_cutoff
        )
        
        if requests_last_minute >= self.MAX_REQUESTS_PER_MINUTE:
            self.blocked_count += 1
            return FirewallResult(
                passed=False,
                reason=f"THROTTLE_MINUTE: {requests_last_minute} requests/min ≥ {self.MAX_REQUESTS_PER_MINUTE} limit",
                blocked_category="THROTTLE"
            )
        
        # Count requests in last hour
        requests_last_hour = len(self.request_history)
        
        if requests_last_hour >= self.MAX_REQUESTS_PER_HOUR:
            self.blocked_count += 1
            return FirewallResult(
                passed=False,
                reason=f"THROTTLE_HOUR: {requests_last_hour} requests/hour ≥ {self.MAX_REQUESTS_PER_HOUR} limit",
                blocked_category="THROTTLE"
            )
        
        return FirewallResult(
            passed=True,
            reason="Throttle check passed",
            blocked_category=None
        )
    
    def reset_throttle(self) -> None:
        """Reset throttle history (admin function)."""
        self.request_history = []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get firewall statistics.
        
        Returns:
            Dictionary with stats
        """
        current_time = datetime.now()
        minute_cutoff = current_time - timedelta(minutes=1)
        hour_cutoff = current_time - timedelta(hours=1)
        
        requests_last_minute = sum(
            1 for t in self.request_history
            if t > minute_cutoff
        )
        
        requests_last_hour = sum(
            1 for t in self.request_history
            if t > hour_cutoff
        )
        
        return {
            "total_blocked": self.blocked_count,
            "requests_last_minute": requests_last_minute,
            "requests_last_hour": requests_last_hour,
            "api_healthy": self.api_healthy
        }
    
    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_stats()
        return (
            f"ExecutionFirewall("
            f"blocked={stats['total_blocked']}, "
            f"requests_min={stats['requests_last_minute']}, "
            f"requests_hour={stats['requests_last_hour']})"
        )
