"""
PHASE-9: HUMAN CONFIRMATION PROTOCOL
Purpose: Present trade setups neutrally for ASSISTED mode

NON-NEGOTIABLE RULES:
1. No emotional language
2. No persuasion
3. No urgency
4. Facts only
5. Clear invalidation point

Output Format:
STRUCTURAL SETUP DETECTED

Scenario: B (Reversion)
Probability: 0.54
Risk: 0.6R
Invalidation: HTF support break

Confirm execution? (YES / NO)

Philosophy:
"Human remains sovereign. System proposes, human decides."
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class TradeSetup:
    """Trade setup for human confirmation."""
    
    symbol: str
    scenario: str
    scenario_description: str
    probability: float
    risk_amount: float
    invalidation: str
    entry_price: float
    direction: str
    
    def format_confirmation_prompt(self) -> str:
        """
        Format neutral confirmation prompt.
        
        Returns:
            Formatted prompt string
        """
        scenario_names = {
            "A": "Continuation",
            "B": "Reversion",
            "C": "Structure Break"
        }
        
        scenario_desc = scenario_names.get(self.scenario, "Unknown")
        
        prompt = f"""
╔════════════════════════════════════════════════════════════════╗
║              STRUCTURAL SETUP DETECTED                         ║
╚════════════════════════════════════════════════════════════════╝

Symbol:       {self.symbol}
Scenario:     {self.scenario} ({scenario_desc})
Probability:  {self.probability:.2%}
Risk:         ₹{self.risk_amount:.2f}
Direction:    {self.direction}
Entry:        {self.entry_price:.2f}
Invalidation: {self.invalidation}

────────────────────────────────────────────────────────────────

Confirm execution? (YES / NO)
"""
        return prompt.strip()


class HumanConfirmationProtocol:
    """
    Handle human confirmation for ASSISTED mode.
    
    Presents setups neutrally without emotion or persuasion.
    """
    
    def __init__(self):
        """Initialize confirmation protocol."""
        self.pending_confirmations = {}
    
    def request_confirmation(
        self,
        setup_id: str,
        symbol: str,
        scenario: str,
        probability: float,
        risk_amount: float,
        invalidation: str,
        entry_price: float,
        direction: str
    ) -> str:
        """
        Request confirmation for a trade setup.
        
        Args:
            setup_id: Unique setup identifier
            symbol: Trading symbol
            scenario: Active scenario (A/B/C)
            probability: Scenario probability
            risk_amount: Risk amount (INR)
            invalidation: Invalidation condition
            entry_price: Entry price
            direction: Trade direction (LONG/SHORT)
        
        Returns:
            Formatted confirmation prompt
        """
        scenario_descriptions = {
            "A": "Continuation",
            "B": "Reversion",
            "C": "Structure Break"
        }
        
        setup = TradeSetup(
            symbol=symbol,
            scenario=scenario,
            scenario_description=scenario_descriptions.get(scenario, "Unknown"),
            probability=probability,
            risk_amount=risk_amount,
            invalidation=invalidation,
            entry_price=entry_price,
            direction=direction
        )
        
        # Store pending confirmation
        self.pending_confirmations[setup_id] = {
            "setup": setup,
            "confirmed": None
        }
        
        return setup.format_confirmation_prompt()
    
    def process_confirmation(
        self,
        setup_id: str,
        user_response: str
    ) -> bool:
        """
        Process user confirmation response.
        
        Args:
            setup_id: Setup identifier
            user_response: User's response (YES/NO)
        
        Returns:
            True if confirmed, False otherwise
        """
        if setup_id not in self.pending_confirmations:
            raise ValueError(f"No pending confirmation for setup_id: {setup_id}")
        
        user_response_upper = user_response.strip().upper()
        
        # Strict YES required
        if user_response_upper == "YES":
            self.pending_confirmations[setup_id]["confirmed"] = True
            return True
        else:
            # Anything other than YES = NO
            self.pending_confirmations[setup_id]["confirmed"] = False
            return False
    
    def is_confirmed(self, setup_id: str) -> Optional[bool]:
        """
        Check if setup is confirmed.
        
        Args:
            setup_id: Setup identifier
        
        Returns:
            True if confirmed, False if rejected, None if pending
        """
        if setup_id not in self.pending_confirmations:
            return None
        
        return self.pending_confirmations[setup_id]["confirmed"]
    
    def clear_confirmation(self, setup_id: str) -> None:
        """
        Clear confirmation (after execution or timeout).
        
        Args:
            setup_id: Setup identifier
        """
        if setup_id in self.pending_confirmations:
            del self.pending_confirmations[setup_id]
    
    def get_pending_count(self) -> int:
        """
        Get count of pending confirmations.
        
        Returns:
            Number of pending confirmations
        """
        return sum(
            1 for c in self.pending_confirmations.values()
            if c["confirmed"] is None
        )
    
    def __repr__(self) -> str:
        """String representation."""
        pending = self.get_pending_count()
        return f"HumanConfirmationProtocol(pending={pending})"
