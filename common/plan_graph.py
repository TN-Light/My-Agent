"""
Plan Graph Module (Phase-5A + Phase-5B)

Structured plan representation with graph semantics for preview and approval.
Phase-5B: JSON serialization for persistence.
"""

import logging
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Union
from datetime import datetime
from common.actions import Action
from common.observations import Observation

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """
    Single step in execution plan.
    
    Phase-5A: Wraps Action/Observation with metadata for preview and approval.
    """
    step_id: int
    item: Union[Action, Observation]
    intent: str  # Human-readable purpose
    expected_outcome: str  # What should happen
    dependencies: List[int] = field(default_factory=list)  # step_ids that must complete first
    requires_approval: bool = False  # Pause before executing this step
    metadata: Optional[dict] = None
    
    @property
    def is_action(self) -> bool:
        """Check if this step is an action (vs observation)."""
        return isinstance(self.item, Action)
    
    @property
    def is_observation(self) -> bool:
        """Check if this step is an observation."""
        return isinstance(self.item, Observation)


@dataclass
class PlanGraph:
    """
    Complete execution plan as graph.
    
    Phase-5A: Structured plan with preview, approval gates, and dependencies.
    Execution loop unchanged - this is metadata wrapper only.
    """
    instruction: str  # Original user instruction
    steps: List[PlanStep]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def total_actions(self) -> int:
        """Count action steps."""
        return sum(1 for step in self.steps if step.is_action)
    
    @property
    def total_observations(self) -> int:
        """Count observation steps."""
        return sum(1 for step in self.steps if step.is_observation)
    
    @property
    def approval_required(self) -> bool:
        """Check if any step requires approval."""
        return any(step.requires_approval for step in self.steps)
    
    def get_execution_order(self) -> List[PlanStep]:
        """
        Return steps in execution order.
        
        Phase-5A: Returns steps in list order (no topological sorting).
        Dependencies are metadata only for future phases.
        """
        return self.steps
    
    def get_approval_steps(self) -> List[PlanStep]:
        """Return only steps that require approval."""
        return [step for step in self.steps if step.requires_approval]
    
    def to_display_tree(self) -> str:
        """
        Generate text-based tree visualization for preview.
        
        Returns:
            Multi-line string showing plan structure
        """
        lines = []
        lines.append("┌─ Plan Preview " + "─" * 54)
        lines.append(f"│ Instruction: {self.instruction}")
        lines.append(f"│ Total Steps: {len(self.steps)} ({self.total_actions} actions, {self.total_observations} observations)")
        
        if self.approval_required:
            approval_count = len(self.get_approval_steps())
            lines.append(f"│ ⚠️  Approval Required: {approval_count} step(s) marked")
        
        lines.append("│")
        
        for step in self.steps:
            # Step header
            approval_marker = " [⚠️  REQUIRES APPROVAL]" if step.requires_approval else ""
            item_type = step.item.action_type if step.is_action else step.item.observation_type
            lines.append(f"│ Step {step.step_id}: {item_type}{approval_marker}")
            
            # Intent
            lines.append(f"│   Intent: {step.intent}")
            
            # Expected outcome
            lines.append(f"│   Expected: {step.expected_outcome}")
            
            # Target/text details
            if step.is_action:
                action = step.item
                if action.target:
                    lines.append(f"│   Target: {action.target}")
                if action.text:
                    text_preview = action.text[:50] + "..." if len(action.text) > 50 else action.text
                    lines.append(f"│   Text: '{text_preview}'")
            else:
                obs = step.item
                if obs.target:
                    lines.append(f"│   Target: {obs.target}")
            
            # Dependencies
            if step.dependencies:
                dep_str = ", ".join([f"Step {d}" for d in step.dependencies])
                lines.append(f"│   Dependencies: {dep_str}")
            else:
                lines.append(f"│   Dependencies: None")
            
            lines.append("│")
        
        lines.append("└" + "─" * 70)
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """
        Serialize PlanGraph to JSON (Phase-5B).
        
        Returns:
            JSON string representation
        """
        # Convert to serializable dict
        data = {
            "instruction": self.instruction,
            "created_at": self.created_at,
            "steps": []
        }
        
        for step in self.steps:
            step_dict = {
                "step_id": step.step_id,
                "intent": step.intent,
                "expected_outcome": step.expected_outcome,
                "dependencies": step.dependencies,
                "requires_approval": step.requires_approval,
                "metadata": step.metadata,
                "item_type": "action" if step.is_action else "observation"
            }
            
            # Serialize the item (Action or Observation)
            if step.is_action:
                item_dict = {
                    "action_type": step.item.action_type,
                    "context": getattr(step.item, 'context', 'desktop'),
                    "target": step.item.target,
                    "text": step.item.text,
                    "coordinates": step.item.coordinates,
                    "verify": step.item.verify
                }
            else:
                item_dict = {
                    "observation_type": step.item.observation_type,
                    "context": getattr(step.item, 'context', 'desktop'),
                    "target": step.item.target
                }
            
            step_dict["item"] = item_dict
            data["steps"].append(step_dict)
        
        return json.dumps(data, indent=2)
    
    @staticmethod
    def from_json(json_str: str) -> "PlanGraph":
        """
        Deserialize PlanGraph from JSON (Phase-5B).
        
        Args:
            json_str: JSON string representation
            
        Returns:
            PlanGraph instance
        """
        data = json.loads(json_str)
        
        steps = []
        for step_dict in data["steps"]:
            # Reconstruct item (Action or Observation)
            if step_dict["item_type"] == "action":
                item = Action(
                    action_type=step_dict["item"]["action_type"],
                    context=step_dict["item"].get("context", "desktop"),
                    target=step_dict["item"]["target"],
                    text=step_dict["item"]["text"],
                    coordinates=step_dict["item"]["coordinates"],
                    verify=step_dict["item"]["verify"]
                )
            else:
                item = Observation(
                    observation_type=step_dict["item"]["observation_type"],
                    context=step_dict["item"].get("context", "desktop"),
                    target=step_dict["item"]["target"]
                )
            
            # Reconstruct step
            step = PlanStep(
                step_id=step_dict["step_id"],
                item=item,
                intent=step_dict["intent"],
                expected_outcome=step_dict["expected_outcome"],
                dependencies=step_dict["dependencies"],
                requires_approval=step_dict["requires_approval"],
                metadata=step_dict["metadata"]
            )
            
            steps.append(step)
        
        return PlanGraph(
            instruction=data["instruction"],
            steps=steps,
            created_at=data["created_at"]
        )
