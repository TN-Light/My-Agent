"""
Replay Engine - Phase-7A Deterministic Plan Replay

Replays persisted PlanGraphs using existing execution infrastructure.
Human-controlled, non-autonomous, deterministic replay only.
"""

import logging
from typing import Optional
from datetime import datetime

from common.plan_graph import PlanGraph, PlanStep
from storage.plan_logger import PlanLogger
from storage.step_approval_logger import StepApprovalLogger
from execution.controller import Controller
from logic.critic import Critic
from logic.policy_engine import PolicyEngine

logger = logging.getLogger(__name__)


class ReplayEngine:
    """
    Deterministic plan replay engine.
    
    Phase-7A: Loads persisted PlanGraphs and re-executes them step-by-step
    with human approval gates. Zero autonomy, no plan modification.
    """
    
    def __init__(
        self,
        plan_logger: PlanLogger,
        step_approval_logger: StepApprovalLogger,
        controller: Controller,
        critic: Critic,
        policy_engine: PolicyEngine
    ):
        """
        Initialize replay engine.
        
        Args:
            plan_logger: For loading persisted plans
            step_approval_logger: For logging step decisions during replay
            controller: For executing actions
            critic: For verifying outcomes
            policy_engine: For enforcing safety policies
        """
        self.plan_logger = plan_logger
        self.step_approval_logger = step_approval_logger
        self.controller = controller
        self.critic = critic
        self.policy_engine = policy_engine
        
        logger.info("ReplayEngine initialized (deterministic, human-controlled)")
    
    def replay_plan(self, plan_id: int) -> bool:
        """
        Replay a persisted plan from database.
        
        Phase-7A: Loads plan JSON, reconstructs PlanGraph, executes sequentially
        with human approval gates. Treats replay as NEW execution session.
        
        Args:
            plan_id: ID of plan to replay from plans.db
            
        Returns:
            True if replay completed successfully, False if aborted/failed
            
        Constraints:
            - NO planner usage
            - NO plan modification
            - NO automatic retries
            - Human approval required BEFORE replay starts
            - Human approval per step (reuse Phase-6A logic)
            - Deterministic execution only
        """
        # Load plan from database
        plan_record = self.plan_logger.get_plan(plan_id)
        
        if not plan_record:
            logger.error(f"[REPLAY] Plan {plan_id} not found in database")
            return False
        
        # Deserialize PlanGraph
        try:
            plan_graph = PlanGraph.from_json(plan_record["plan_json"])
            logger.info(f"[REPLAY] Loaded plan {plan_id}: {plan_graph.instruction}")
            logger.info(f"[REPLAY] Steps: {len(plan_graph.steps)} ({plan_graph.total_actions} actions, {plan_graph.total_observations} observations)")
        except Exception as e:
            logger.error(f"[REPLAY] Failed to deserialize plan {plan_id}: {e}")
            return False
        
        # Display plan preview
        print("\n" + "="*70)
        print(f"REPLAY PLAN {plan_id}")
        print("="*70)
        print(plan_graph.to_display_tree())
        print()
        
        # Require explicit human approval BEFORE replay starts
        print("⚠️  REPLAY REQUIRES EXPLICIT APPROVAL")
        print("This will re-execute the plan step-by-step using the existing execution loop.")
        print()
        approval = input("Start replay? (yes/no): ").strip().lower()
        
        if approval != "yes":
            logger.info(f"[REPLAY] Replay of plan {plan_id} cancelled by user")
            print("❌ Replay cancelled")
            return False
        
        logger.info(f"[REPLAY] Starting replay of plan {plan_id}")
        print(f"\n🔁 Starting replay of plan {plan_id}...")
        print("="*70 + "\n")
        
        # Create new plan entry for replay execution
        # This ensures replay has its own execution timestamps and audit trail
        replay_plan_id = self.plan_logger.log_plan(plan_graph, approval_required=True)
        self.plan_logger.update_approval(
            replay_plan_id,
            approved=True,
            actor="local_user",
            timestamp=datetime.now().isoformat()
        )
        self.plan_logger.mark_execution_started(replay_plan_id, datetime.now().isoformat())
        
        # Execute steps sequentially
        success = True
        for step in plan_graph.get_execution_order():
            step_success = self.replay_step(step, replay_plan_id)
            
            if not step_success:
                # Step failed or was aborted
                success = False
                break
        
        # Mark replay execution as completed
        final_status = "completed" if success else "cancelled"
        self.plan_logger.mark_execution_completed(
            replay_plan_id,
            datetime.now().isoformat(),
            final_status
        )
        
        if success:
            logger.info(f"[REPLAY] Replay of plan {plan_id} completed successfully")
            print("\n" + "="*70)
            print("✅ REPLAY COMPLETED SUCCESSFULLY")
            print("="*70)
        else:
            logger.warning(f"[REPLAY] Replay of plan {plan_id} was aborted or failed")
            print("\n" + "="*70)
            print("❌ REPLAY ABORTED OR FAILED")
            print("="*70)
        
        return success
    
    def replay_step(self, step: PlanStep, replay_plan_id: int) -> bool:
        """
        Replay a single step with approval gates.
        
        Phase-7A: Executes one step from replayed plan. Reuses Phase-6A approval logic.
        
        Args:
            step: PlanStep to execute
            replay_plan_id: Plan ID for the current replay session
            
        Returns:
            True if step executed successfully, False if skipped/rejected/failed
            
        Behavior:
            - Actions: Execute using controller, verify with critic
            - Observations: Execute using critic only
            - Approval gates: Prompt user (approve/skip/reject) if step.requires_approval
            - Policy enforcement: Same as normal execution
        """
        print(f"\n{'='*70}")
        print(f"Step {step.step_id}: {step.item.action_type if step.is_action else step.item.observation_type}")
        print(f"Intent: {step.intent}")
        print(f"Expected: {step.expected_outcome}")
        print("="*70)
        
        # Check if step requires approval (Phase-6A logic)
        if step.requires_approval:
            print(f"\n⚠️  Step {step.step_id} requires approval")
            print(f"Type: {step.item.action_type if step.is_action else step.item.observation_type}")
            print(f"Intent: {step.intent}")
            print()
            
            while True:
                user_input = input("Approve this step? (approve/skip/reject): ").strip().lower()
                
                if user_input in ["approve", "a"]:
                    decision = "approved"
                    break
                elif user_input in ["skip", "s"]:
                    decision = "skipped"
                    break
                elif user_input in ["reject", "r"]:
                    decision = "rejected"
                    break
                else:
                    print("❌ Invalid choice. Please enter: approve, skip, or reject")
            
            # Log decision
            self.step_approval_logger.log_step_decision(
                replay_plan_id,
                step.step_id,
                decision,
                timestamp=datetime.now().isoformat(),
                reason=f"Replay step approval for {step.item.action_type if step.is_action else step.item.observation_type}"
            )
            
            if decision == "rejected":
                logger.warning(f"[REPLAY] Step {step.step_id} rejected by user - aborting replay")
                print(f"❌ Step {step.step_id} rejected - aborting replay")
                return False
            
            if decision == "skipped":
                logger.info(f"[REPLAY] Step {step.step_id} skipped by user")
                print(f"⏭️  Step {step.step_id} skipped")
                return True  # Continue to next step
            
            # decision == "approved" - continue execution below
            logger.info(f"[REPLAY] Step {step.step_id} approved by user")
        
        # Execute step
        if step.is_action:
            # Action execution
            action = step.item
            
            # Enforce policy (same as normal execution)
            approved, reason = self.policy_engine.validate_action(action)
            
            if not approved:
                logger.warning(f"[REPLAY] Action denied by policy: {reason}")
                print(f"❌ Action denied by policy: {reason}")
                return False
            
            # Execute action
            try:
                self.controller.execute_action(action, plan_id=replay_plan_id)
                logger.info(f"[REPLAY] Step {step.step_id} action executed: {action.action_type}")
                
                # Verify if required
                if action.verify:
                    result = self.critic.verify_action(action)
                    
                    if result.verified:
                        logger.info(f"[REPLAY] Step {step.step_id} verified successfully (confidence={result.confidence:.2f})")
                        print(f"✅ Step {step.step_id} completed and verified")
                    else:
                        logger.warning(f"[REPLAY] Step {step.step_id} verification failed (confidence={result.confidence:.2f})")
                        print(f"⚠️  Step {step.step_id} completed but verification failed")
                        return False
                else:
                    print(f"✅ Step {step.step_id} completed (no verification)")
                
            except Exception as e:
                logger.error(f"[REPLAY] Step {step.step_id} execution failed: {e}")
                print(f"❌ Step {step.step_id} failed: {e}")
                return False
        
        else:
            # Observation execution
            observation = step.item
            
            try:
                result = self.critic.verify_observation(observation)
                
                if result.verified:
                    logger.info(f"[REPLAY] Step {step.step_id} observation verified (confidence={result.confidence:.2f})")
                    print(f"✅ Step {step.step_id} observation verified")
                else:
                    logger.warning(f"[REPLAY] Step {step.step_id} observation not verified (confidence={result.confidence:.2f})")
                    print(f"❌ Step {step.step_id} observation not verified")
                    return False
                    
            except Exception as e:
                logger.error(f"[REPLAY] Step {step.step_id} observation failed: {e}")
                print(f"❌ Step {step.step_id} failed: {e}")
                return False
        
        return True
