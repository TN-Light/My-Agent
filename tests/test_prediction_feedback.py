"""
Phase-E: Tests for prediction feedback loop.
Tests PredictionStore, OutcomeResolver, and FeedbackReporter.
"""
import os
import sys
import sqlite3
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.prediction_feedback import PredictionStore, OutcomeResolver, FeedbackReporter


class TestPredictionStore(unittest.TestCase):
    """Test the prediction recording and retrieval store."""
    
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test_predictions.db")
        self.store = PredictionStore(db_path=self.db_path)
    
    def test_record_and_retrieve(self):
        """Record a prediction and retrieve it as pending."""
        pid = self.store.record_prediction(
            symbol="AAPL",
            verdict="STRONG",
            confidence="HIGH",
            trend_prediction="UP",
            alignment_state="FULL",
            active_scenario="CONTINUATION",
            price=185.50,
            support_levels=[180.0, 175.0],
            resistance_levels=[190.0, 195.0],
            htf_location="MID"
        )
        
        self.assertGreater(pid, 0)
        
        pending = self.store.get_pending_predictions()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["symbol"], "AAPL")
        self.assertEqual(pending[0]["verdict"], "STRONG")
        self.assertEqual(pending[0]["confidence"], "HIGH")
        self.assertAlmostEqual(pending[0]["price_at_prediction"], 185.50, places=2)
    
    def test_resolve_prediction(self):
        """Resolve a pending prediction with outcome data."""
        pid = self.store.record_prediction(
            symbol="TSLA",
            verdict="CAUTION",
            confidence="MEDIUM",
            trend_prediction="DOWN",
            price=250.0
        )
        
        self.store.resolve_prediction(
            prediction_id=pid,
            price_at_resolution=240.0,
            trend_actual="DOWN",
            verdict_correct=True,
            trend_correct=True,
            support_held=True,
            resistance_held=False,
            price_move_pct=-4.0,
            notes="Trend continued as predicted"
        )
        
        # Should no longer be pending
        pending = self.store.get_pending_predictions()
        self.assertEqual(len(pending), 0)
    
    def test_accuracy_stats(self):
        """Test accuracy statistics calculation."""
        # Record 3 predictions and resolve them
        for i, (sym, correct) in enumerate([("A", True), ("B", False), ("C", True)]):
            pid = self.store.record_prediction(
                symbol=sym, verdict="STRONG", confidence="HIGH",
                trend_prediction="UP", price=100.0 + i
            )
            self.store.resolve_prediction(
                prediction_id=pid,
                price_at_resolution=105.0,
                trend_actual="UP",
                verdict_correct=correct,
                trend_correct=True,
                support_held=True,
                resistance_held=True,
                price_move_pct=5.0
            )
        
        stats = self.store.get_accuracy_stats()
        self.assertEqual(stats["total_resolved"], 3)
        self.assertAlmostEqual(stats["verdict_accuracy_pct"], 66.7, places=0)
    
    def test_accuracy_by_verdict(self):
        """Test per-verdict accuracy breakdown."""
        # Record STRONG and AVOID predictions
        for verdict, correct in [("STRONG", True), ("STRONG", True), ("AVOID", False)]:
            pid = self.store.record_prediction(
                symbol="TEST", verdict=verdict, confidence="HIGH",
                trend_prediction="UP", price=100.0
            )
            self.store.resolve_prediction(
                prediction_id=pid,
                price_at_resolution=105.0,
                trend_actual="UP",
                verdict_correct=correct,
                trend_correct=True,
                support_held=True,
                resistance_held=True,
                price_move_pct=5.0
            )
        
        by_verdict = self.store.get_accuracy_by_verdict()
        self.assertIn("STRONG", by_verdict)
        self.assertEqual(by_verdict["STRONG"]["total"], 2)
        self.assertAlmostEqual(by_verdict["STRONG"]["verdict_accuracy_pct"], 100.0, places=0)
    
    def test_duplicate_prediction_replaces(self):
        """UNIQUE(symbol, timestamp) means same-second insert replaces."""
        pid1 = self.store.record_prediction(
            symbol="AAPL", verdict="STRONG", confidence="HIGH",
            trend_prediction="UP", price=100.0
        )
        # Slightly different timestamp will create a new record
        import time
        time.sleep(0.01)
        pid2 = self.store.record_prediction(
            symbol="AAPL", verdict="AVOID", confidence="LOW",
            trend_prediction="DOWN", price=99.0
        )
        self.assertNotEqual(pid1, pid2)


class TestOutcomeResolver(unittest.TestCase):
    """Test the outcome resolution logic."""
    
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test_predictions.db")
        self.store = PredictionStore(db_path=self.db_path)
        
        # Mock scenario resolution store
        self.mock_resolution_store = MagicMock()
        
        self.resolver = OutcomeResolver(
            prediction_store=self.store,
            scenario_resolution_store=self.mock_resolution_store
        )
    
    def test_score_verdict_strong_bullish(self):
        """STRONG verdict with bullish prediction → UP trend = correct."""
        result = self.resolver._score_verdict(
            verdict="STRONG",
            predicted_trend="bullish",
            price_move_pct=3.0,
            trend_correct=True
        )
        self.assertTrue(result)
    
    def test_score_verdict_strong_wrong(self):
        """STRONG verdict with bullish prediction → price crashed = incorrect."""
        result = self.resolver._score_verdict(
            verdict="STRONG",
            predicted_trend="bullish",
            price_move_pct=-5.0,
            trend_correct=False
        )
        self.assertFalse(result)
    
    def test_score_verdict_avoid_correct(self):
        """AVOID with small move = correct avoidance."""
        result = self.resolver._score_verdict(
            verdict="AVOID",
            predicted_trend="bullish",
            price_move_pct=0.5,
            trend_correct=False
        )
        self.assertTrue(result)
    
    def test_score_verdict_no_trade(self):
        """NO_TRADE is always correct (no position taken)."""
        result = self.resolver._score_verdict(
            verdict="NO_TRADE",
            predicted_trend="bullish",
            price_move_pct=-5.0,
            trend_correct=False
        )
        self.assertTrue(result)
    
    def test_determine_scenario(self):
        """Test scenario determination logic."""
        scenario = self.resolver._determine_scenario(
            pred_trend="bullish",
            actual_trend="bullish",
            price_move_pct=3.0,
            support_held=True
        )
        self.assertEqual(scenario, "A")  # Continuation
    
    def test_determine_scenario_failure(self):
        """Structure broken → Scenario C."""
        scenario = self.resolver._determine_scenario(
            pred_trend="bullish",
            actual_trend="bearish",
            price_move_pct=-5.0,
            support_held=False
        )
        self.assertEqual(scenario, "C")  # Failure


class TestFeedbackReporter(unittest.TestCase):
    """Test the feedback reporting system."""
    
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test_predictions.db")
        self.store = PredictionStore(db_path=self.db_path)
        self.reporter = FeedbackReporter(self.store)
    
    def test_empty_report(self):
        """Report with no data doesn't crash."""
        report = self.reporter.generate_report()
        self.assertIsInstance(report, str)
        self.assertTrue(len(report) > 0)
    
    def test_prompt_context_empty(self):
        """Prompt context with no data returns minimal string."""
        ctx = self.reporter.get_prompt_context()
        self.assertIsInstance(ctx, str)
    
    def test_report_with_data(self):
        """Report with resolved predictions shows accuracy."""
        for i in range(5):
            pid = self.store.record_prediction(
                symbol="TEST", verdict="STRONG", confidence="HIGH",
                trend_prediction="UP", price=100.0
            )
            self.store.resolve_prediction(
                prediction_id=pid,
                price_at_resolution=105.0,
                trend_actual="UP",
                verdict_correct=(i < 4),  # 4/5 correct
                trend_correct=True,
                support_held=True,
                resistance_held=True,
                price_move_pct=5.0
            )
        
        report = self.reporter.generate_report()
        self.assertIn("STRONG", report)
        self.assertIn("80", report)  # 80% accuracy
    
    def test_prompt_context_with_data(self):
        """Prompt context includes accuracy info for LLM."""
        pid = self.store.record_prediction(
            symbol="TEST", verdict="STRONG", confidence="HIGH",
            trend_prediction="UP", price=100.0
        )
        self.store.resolve_prediction(
            prediction_id=pid,
            price_at_resolution=105.0,
            trend_actual="UP",
            verdict_correct=True,
            trend_correct=True,
            support_held=True,
            resistance_held=True,
            price_move_pct=5.0
        )
        
        ctx = self.reporter.get_prompt_context()
        self.assertIn("accuracy", ctx.lower())


if __name__ == "__main__":
    unittest.main()
