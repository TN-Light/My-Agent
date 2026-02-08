"""
Debug Reporter - Phase-6B Post-Execution Analysis

Read-only analysis and reporting tools for debugging completed plans.
Generates deterministic reports from database records.
"""

import logging
import sqlite3
import json
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class DebugReporter:
    """
    Post-execution debugging and analysis tools.
    
    Phase-6B: Read-only operations for timeline reconstruction,
    root cause analysis, and human-readable debug reports.
    
    Zero side effects - pure reporting only.
    """
    
    def __init__(self, plans_db_path: str = "db/plans.db", history_db_path: str = "db/history.db", obs_db_path: str = "db/observations.db"):
        """
        Initialize debug reporter with database connections.
        
        Args:
            plans_db_path: Path to plans database
            history_db_path: Path to action history database
            obs_db_path: Path to observations database
        """
        self.plans_db_path = plans_db_path
        self.history_db_path = history_db_path
        self.obs_db_path = obs_db_path
        
        self.plans_conn = sqlite3.connect(plans_db_path, check_same_thread=False)
        self.plans_conn.row_factory = sqlite3.Row
        
        self.history_conn = sqlite3.connect(history_db_path, check_same_thread=False)
        self.history_conn.row_factory = sqlite3.Row
        
        self.obs_conn = sqlite3.connect(obs_db_path, check_same_thread=False)
        self.obs_conn.row_factory = sqlite3.Row
        
        logger.info(f"DebugReporter initialized (read-only)")
    
    def build_timeline(self, plan_id: int) -> List[Dict]:
        """
        Reconstruct execution timeline for a plan.
        
        Phase-6B: Chronological sequence of all events related to a plan.
        Includes plan creation, approvals, step decisions, actions, observations.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            List of timeline events (chronologically ordered)
        """
        timeline = []
        
        # 1. Get plan creation
        cursor = self.plans_conn.cursor()
        cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
        plan_row = cursor.fetchone()
        
        if not plan_row:
            return []  # Plan not found
        
        plan = dict(plan_row)
        
        timeline.append({
            'timestamp': plan['created_at'],
            'event_type': 'plan_created',
            'details': {
                'instruction': plan['instruction'],
                'total_steps': plan['total_steps'],
                'approval_required': plan['approval_required']
            }
        })
        
        # 2. Get plan approval (if applicable)
        if plan['approval_status'] and plan['approval_status'] != 'not_required':
            timeline.append({
                'timestamp': plan['approval_timestamp'] or plan['created_at'],
                'event_type': 'plan_approval',
                'details': {
                    'decision': plan['approval_status'],
                    'actor': plan['approval_actor']
                }
            })
        
        # 3. Get execution start
        if plan['execution_started_at']:
            timeline.append({
                'timestamp': plan['execution_started_at'],
                'event_type': 'execution_started',
                'details': {}
            })
        
        # 4. Get step approvals
        try:
            cursor.execute("""
                SELECT * FROM plan_step_approvals
                WHERE plan_id = ?
                ORDER BY timestamp
            """, (plan_id,))
            
            for row in cursor.fetchall():
                step_approval = dict(row)
                timeline.append({
                    'timestamp': step_approval['timestamp'],
                    'event_type': 'step_approval',
                    'details': {
                        'step_id': step_approval['step_id'],
                        'decision': step_approval['decision'],
                        'reason': step_approval.get('reason')
                    }
                })
        except sqlite3.OperationalError:
            # Table doesn't exist (Phase-6A not enabled)
            pass
        
        # 5. Get actions
        history_cursor = self.history_conn.cursor()
        history_cursor.execute("""
            SELECT * FROM action_history
            WHERE plan_id = ?
            ORDER BY timestamp
        """, (plan_id,))
        
        for row in history_cursor.fetchall():
            action = dict(row)
            
            # Parse verification evidence if present
            evidence = None
            if action.get('verification_evidence'):
                try:
                    evidence = json.loads(action['verification_evidence'])
                except (json.JSONDecodeError, ValueError):
                    pass
            
            timeline.append({
                'timestamp': action['timestamp'],
                'event_type': 'action_executed',
                'details': {
                    'action_type': action['action_type'],
                    'target': action['target'],
                    'success': bool(action['success']),
                    'message': action['message'],
                    'error': action.get('error'),
                    'verification_evidence': evidence
                }
            })
        
        # 6. Get execution completion
        if plan['execution_completed_at']:
            timeline.append({
                'timestamp': plan['execution_completed_at'],
                'event_type': 'execution_completed',
                'details': {
                    'status': plan['execution_status']
                }
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return timeline
    
    def get_failure_root_cause(self, plan_id: int) -> Dict:
        """
        Analyze failed plan and identify root cause.
        
        Phase-6B: Deterministic analysis of failure point.
        No intelligence - just data extraction.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            Root cause analysis dict
        """
        # Get plan details
        cursor = self.plans_conn.cursor()
        cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
        plan_row = cursor.fetchone()
        
        if not plan_row:
            return {'error': 'Plan not found'}
        
        plan = dict(plan_row)
        
        # Check execution status
        if plan['execution_status'] not in ['failed', 'cancelled']:
            return {
                'plan_id': plan_id,
                'status': plan['execution_status'],
                'failure': False,
                'message': f"Plan {plan['execution_status']} - no failure detected"
            }
        
        # Cancelled plans
        if plan['execution_status'] == 'cancelled':
            # Check if plan-level rejection
            if plan['approval_status'] == 'rejected':
                return {
                    'plan_id': plan_id,
                    'status': 'cancelled',
                    'failure': True,
                    'root_cause': 'plan_rejected',
                    'message': 'User rejected plan during batch approval',
                    'timestamp': plan['approval_timestamp']
                }
            
            # Check for step-level rejection
            try:
                cursor.execute("""
                    SELECT * FROM plan_step_approvals
                    WHERE plan_id = ? AND decision = 'rejected'
                    ORDER BY timestamp
                    LIMIT 1
                """, (plan_id,))
                
                step_rejection = cursor.fetchone()
                if step_rejection:
                    step_rej = dict(step_rejection)
                    return {
                        'plan_id': plan_id,
                        'status': 'cancelled',
                        'failure': True,
                        'root_cause': 'step_rejected',
                        'message': f"User rejected step {step_rej['step_id']}",
                        'step_id': step_rej['step_id'],
                        'reason': step_rej.get('reason'),
                        'timestamp': step_rej['timestamp']
                    }
            except sqlite3.OperationalError:
                # Table doesn't exist (Phase-6A not enabled)
                pass
        
        # Failed plans - find first failed action
        history_cursor = self.history_conn.cursor()
        history_cursor.execute("""
            SELECT * FROM action_history
            WHERE plan_id = ? AND success = 0
            ORDER BY timestamp
            LIMIT 1
        """, (plan_id,))
        
        failed_action = history_cursor.fetchone()
        
        if failed_action:
            action = dict(failed_action)
            
            # Parse verification evidence if present
            evidence = None
            if action.get('verification_evidence'):
                try:
                    evidence = json.loads(action['verification_evidence'])
                except (json.JSONDecodeError, ValueError):
                    pass
            
            return {
                'plan_id': plan_id,
                'status': 'failed',
                'failure': True,
                'root_cause': 'action_failed',
                'message': f"Action failed: {action['action_type']}",
                'action_type': action['action_type'],
                'target': action['target'],
                'error': action.get('error'),
                'verification_evidence': evidence,
                'timestamp': action['timestamp']
            }
        
        # Unknown failure
        return {
            'plan_id': plan_id,
            'status': plan['execution_status'],
            'failure': True,
            'root_cause': 'unknown',
            'message': 'Plan marked as failed but no failed actions found'
        }
    
    def generate_debug_report(self, plan_id: int) -> str:
        """
        Generate human-readable debug report for a plan.
        
        Phase-6B: Comprehensive text report including timeline,
        failure analysis, and all relevant data.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            Formatted debug report (text)
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"DEBUG REPORT - PLAN {plan_id}")
        lines.append("=" * 80)
        lines.append("")
        
        # Get plan details
        cursor = self.plans_conn.cursor()
        cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
        plan_row = cursor.fetchone()
        
        if not plan_row:
            lines.append("ERROR: Plan not found")
            return "\n".join(lines)
        
        plan = dict(plan_row)
        
        # Plan Overview
        lines.append("PLAN OVERVIEW")
        lines.append("-" * 80)
        lines.append(f"Instruction: {plan['instruction']}")
        lines.append(f"Total Steps: {plan['total_steps']} ({plan['total_actions']} actions, {plan['total_observations']} observations)")
        lines.append(f"Created: {plan['created_at']}")
        lines.append(f"Execution Status: {plan['execution_status']}")
        lines.append(f"Approval Required: {plan['approval_required']}")
        if plan['approval_status']:
            lines.append(f"Approval Status: {plan['approval_status']}")
            if plan['approval_actor']:
                lines.append(f"Approved By: {plan['approval_actor']}")
        lines.append("")
        
        # Timeline
        lines.append("EXECUTION TIMELINE")
        lines.append("-" * 80)
        timeline = self.build_timeline(plan_id)
        
        for i, event in enumerate(timeline, 1):
            lines.append(f"{i}. [{event['timestamp']}] {event['event_type'].upper()}")
            
            details = event['details']
            if event['event_type'] == 'plan_created':
                lines.append(f"   Instruction: {details['instruction']}")
                lines.append(f"   Steps: {details['total_steps']}")
            
            elif event['event_type'] == 'plan_approval':
                lines.append(f"   Decision: {details['decision']}")
                lines.append(f"   Actor: {details['actor']}")
            
            elif event['event_type'] == 'step_approval':
                lines.append(f"   Step: {details['step_id']}")
                lines.append(f"   Decision: {details['decision']}")
                if details.get('reason'):
                    lines.append(f"   Reason: {details['reason']}")
            
            elif event['event_type'] == 'action_executed':
                status = "SUCCESS" if details['success'] else "FAILED"
                lines.append(f"   Action: {details['action_type']}")
                lines.append(f"   Target: {details['target']}")
                lines.append(f"   Status: {status}")
                lines.append(f"   Message: {details['message']}")
                if details.get('error'):
                    lines.append(f"   Error: {details['error']}")
                if details.get('verification_evidence'):
                    evidence = details['verification_evidence']
                    lines.append(f"   Verification Source: {evidence.get('source', 'unknown')}")
                    lines.append(f"   Confidence: {evidence.get('confidence', 0.0):.2f}")
            
            elif event['event_type'] == 'execution_completed':
                lines.append(f"   Final Status: {details['status']}")
            
            lines.append("")
        
        # Root Cause Analysis (if failed/cancelled)
        if plan['execution_status'] in ['failed', 'cancelled']:
            lines.append("ROOT CAUSE ANALYSIS")
            lines.append("-" * 80)
            root_cause = self.get_failure_root_cause(plan_id)
            
            lines.append(f"Status: {root_cause['status']}")
            lines.append(f"Root Cause: {root_cause['root_cause']}")
            lines.append(f"Message: {root_cause['message']}")
            
            if root_cause.get('action_type'):
                lines.append(f"Failed Action: {root_cause['action_type']}")
                lines.append(f"Target: {root_cause['target']}")
                lines.append(f"Error: {root_cause.get('error')}")
            
            if root_cause.get('step_id'):
                lines.append(f"Rejected Step: {root_cause['step_id']}")
                if root_cause.get('reason'):
                    lines.append(f"Reason: {root_cause['reason']}")
            
            lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 80)
        
        # Count actions
        history_cursor = self.history_conn.cursor()
        history_cursor.execute("""
            SELECT COUNT(*) as total, SUM(success) as successful
            FROM action_history
            WHERE plan_id = ?
        """, (plan_id,))
        
        counts = history_cursor.fetchone()
        if counts:
            total = counts['total']
            successful = counts['successful'] or 0
            lines.append(f"Actions Executed: {total}")
            lines.append(f"Actions Successful: {successful}")
            lines.append(f"Actions Failed: {total - successful}")
        
        # Count step approvals
        try:
            cursor.execute("""
                SELECT decision, COUNT(*) as count
                FROM plan_step_approvals
                WHERE plan_id = ?
                GROUP BY decision
            """, (plan_id,))
            
            approval_counts = {}
            for row in cursor.fetchall():
                approval_counts[row['decision']] = row['count']
            
            if approval_counts:
                lines.append("")
                lines.append("Step Approval Decisions:")
                for decision, count in approval_counts.items():
                    lines.append(f"  {decision}: {count}")
        except sqlite3.OperationalError:
            # Table doesn't exist (Phase-6A not enabled)
            pass
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def close(self):
        """Close database connections."""
        if self.plans_conn:
            self.plans_conn.close()
        if self.history_conn:
            self.history_conn.close()
        if self.obs_conn:
            self.obs_conn.close()
        logger.debug("DebugReporter connections closed")
