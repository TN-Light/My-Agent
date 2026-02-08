"""
Market Display Engine — Extracted from ExecutionEngine.

Renders market scenarios (Continuation/Pullback/Failure) and multi-timeframe
price zones. Pure display logic — no state mutation or data fetching.
"""

import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class MarketDisplayEngine:
    """
    Renders market analysis display output to the ChatUI.
    
    Extracted from ExecutionEngine to reduce its size and isolate
    display concerns from business logic.
    """
    
    def __init__(self, chat_ui=None):
        self.chat_ui = chat_ui
    
    def _log(self, msg: str, level: str = "INFO"):
        """Output to chat UI if available."""
        if self.chat_ui:
            self.chat_ui.log(msg, level)
    
    def display_market_scenarios(
        self,
        monthly_data: Optional[Dict],
        weekly_data: Optional[Dict],
        daily_data: Optional[Dict],
        dominant_tf: str,
        alignment: str
    ):
        """
        Construct and display 3 market scenarios: Continuation, Pullback, Trend Failure.
        """
        if not self.chat_ui:
            return
        
        monthly_analysis = monthly_data["analysis"] if monthly_data else {}
        weekly_analysis = weekly_data["analysis"] if weekly_data else {}
        daily_analysis = daily_data["analysis"] if daily_data else {}
        
        monthly_trend = monthly_analysis.get("trend", "unknown").lower()
        weekly_trend = weekly_analysis.get("trend", "unknown").lower()
        daily_trend = daily_analysis.get("trend", "unknown").lower()
        
        monthly_support = monthly_analysis.get("support", [])
        monthly_resistance = monthly_analysis.get("resistance", [])
        weekly_support = weekly_analysis.get("support", [])
        weekly_resistance = weekly_analysis.get("resistance", [])
        daily_support = daily_analysis.get("support", [])
        daily_resistance = daily_analysis.get("resistance", [])
        
        self._log(f"\n{'─'*70}", "INFO")
        self._log("**📋 MARKET SCENARIOS**", "SUCCESS")
        self._log(f"{'─'*70}\n", "INFO")
        
        # SCENARIO A - Continuation
        self._log("**🟢 SCENARIO A — Continuation**", "SUCCESS")
        self._render_continuation(monthly_trend, dominant_tf,
                                  monthly_support, monthly_resistance,
                                  weekly_support, weekly_resistance)
        self._log("", "INFO")
        
        # SCENARIO B - Pullback
        self._log("**🟡 SCENARIO B — Pullback / Consolidation**", "WARNING")
        self._render_pullback(monthly_trend, daily_trend,
                              monthly_support, monthly_resistance,
                              weekly_support, weekly_resistance,
                              daily_support, daily_resistance)
        self._log("", "INFO")
        
        # SCENARIO C - Trend Failure
        self._log("**🔴 SCENARIO C — Trend Failure**", "ERROR")
        self._render_failure(monthly_trend,
                             monthly_support, monthly_resistance,
                             weekly_support, weekly_resistance)
    
    def _render_continuation(self, monthly_trend, dominant_tf,
                             monthly_support, monthly_resistance,
                             weekly_support, weekly_resistance):
        if monthly_trend == "bullish":
            self._log(f"  The **{dominant_tf} bullish trend** continues higher.", "INFO")
            self._log("  **Conditions to remain valid:**", "INFO")
            if monthly_support:
                self._log(f"    • Price holds above Monthly support (₹{monthly_support[0]})", "INFO")
            if weekly_support:
                self._log(f"    • Weekly support at ₹{weekly_support[0]} remains intact", "INFO")
            if monthly_resistance:
                self._log(f"    • Break above ₹{monthly_resistance[0]} confirms strength", "INFO")
        elif monthly_trend == "bearish":
            self._log(f"  The **{dominant_tf} bearish trend** continues lower.", "INFO")
            self._log("  **Conditions to remain valid:**", "INFO")
            if monthly_resistance:
                self._log(f"    • Price stays below Monthly resistance (₹{monthly_resistance[0]})", "INFO")
            if weekly_resistance:
                self._log(f"    • Weekly resistance at ₹{weekly_resistance[0]} holds", "INFO")
            if monthly_support:
                self._log(f"    • Break below ₹{monthly_support[0]} confirms weakness", "INFO")
        else:
            self._log("  Price continues consolidating in current range.", "INFO")
            self._log("  **Conditions to remain valid:**", "INFO")
            if monthly_support and monthly_resistance:
                self._log(f"    • Price stays between ₹{monthly_support[0]} - ₹{monthly_resistance[0]}", "INFO")
    
    def _render_pullback(self, monthly_trend, daily_trend,
                         monthly_support, monthly_resistance,
                         weekly_support, weekly_resistance,
                         daily_support, daily_resistance):
        if monthly_trend == "bullish":
            self._log("  Lower timeframe weakness triggers pullback within uptrend.", "INFO")
            self._log("  **Likely triggered by:**", "INFO")
            if daily_trend in ["bearish", "sideways"]:
                self._log(f"    • Daily showing {daily_trend} divergence", "INFO")
            else:
                self._log("    • Overbought conditions or profit-taking", "INFO")
            self._log("  **Pullback zones:**", "INFO")
            if weekly_support:
                self._log(f"    • Weekly support: ₹{weekly_support[0]}", "INFO")
            if monthly_support:
                self._log(f"    • Monthly support: ₹{monthly_support[0]}", "INFO")
        elif monthly_trend == "bearish":
            self._log("  Lower timeframe bounce triggers relief rally within downtrend.", "INFO")
            self._log("  **Likely triggered by:**", "INFO")
            if daily_trend in ["bullish", "sideways"]:
                self._log(f"    • Daily showing {daily_trend} divergence", "INFO")
            else:
                self._log("    • Oversold bounce or short covering", "INFO")
            self._log("  **Bounce zones:**", "INFO")
            if weekly_resistance:
                self._log(f"    • Weekly resistance: ₹{weekly_resistance[0]}", "INFO")
            if monthly_resistance:
                self._log(f"    • Monthly resistance: ₹{monthly_resistance[0]}", "INFO")
        else:
            self._log("  Temporary directional move within consolidation.", "INFO")
            if daily_support and daily_resistance:
                self._log(f"  **Range:** ₹{daily_support[0]} - ₹{daily_resistance[0]}", "INFO")
    
    def _render_failure(self, monthly_trend,
                        monthly_support, monthly_resistance,
                        weekly_support, weekly_resistance):
        if monthly_trend == "bullish":
            self._log("  **Bullish trend invalidated** if HTF structure breaks.", "INFO")
            self._log("  **Invalidation conditions:**", "ERROR")
            if monthly_support:
                self._log(f"    • Monthly support breakdown: Below ₹{monthly_support[0]}", "ERROR")
            if weekly_support:
                self._log(f"    • Weekly support lost: Below ₹{weekly_support[0]}", "ERROR")
            self._log("    • Structure shifts to lower-lows on Monthly chart", "ERROR")
        elif monthly_trend == "bearish":
            self._log("  **Bearish trend invalidated** if HTF structure breaks.", "INFO")
            self._log("  **Invalidation conditions:**", "ERROR")
            if monthly_resistance:
                self._log(f"    • Monthly resistance breakout: Above ₹{monthly_resistance[0]}", "ERROR")
            if weekly_resistance:
                self._log(f"    • Weekly resistance cleared: Above ₹{weekly_resistance[0]}", "ERROR")
            self._log("    • Structure shifts to higher-highs on Monthly chart", "ERROR")
        else:
            self._log("  Range breaks decisively in either direction.", "INFO")
            self._log("  **Breakout conditions:**", "ERROR")
            if monthly_resistance:
                self._log(f"    • Bullish: Above ₹{monthly_resistance[0]}", "ERROR")
            if monthly_support:
                self._log(f"    • Bearish: Below ₹{monthly_support[0]}", "ERROR")
    
    def display_price_zones(
        self,
        monthly_data: Optional[Dict],
        weekly_data: Optional[Dict],
        daily_data: Optional[Dict],
        monthly_trend: str
    ):
        """
        Identify and display key price zones with multi-timeframe confluence.
        """
        if not self.chat_ui:
            return
        
        monthly_analysis = monthly_data["analysis"] if monthly_data else {}
        weekly_analysis = weekly_data["analysis"] if weekly_data else {}
        daily_analysis = daily_data["analysis"] if daily_data else {}
        
        # Collect all levels with their timeframe origin
        all_levels = []
        
        level_sources = [
            (monthly_analysis.get("support", []), "support", "monthly", 3),
            (monthly_analysis.get("resistance", []), "resistance", "monthly", 3),
            (weekly_analysis.get("support", []), "support", "weekly", 2),
            (weekly_analysis.get("resistance", []), "resistance", "weekly", 2),
            (daily_analysis.get("support", []), "support", "daily", 1),
            (daily_analysis.get("resistance", []), "resistance", "daily", 1),
        ]
        
        for levels, level_type, tf, weight in level_sources:
            for level in levels:
                try:
                    all_levels.append({
                        "price": float(level),
                        "type": level_type,
                        "tf": tf,
                        "weight": weight
                    })
                except (ValueError, TypeError):
                    pass
        
        if not all_levels:
            return
        
        # Find confluence zones (levels within 3% of each other)
        zones = self._find_confluence_zones(all_levels)
        
        # Classify zones by importance
        major_zones, intermediate_zones, minor_zones = self._classify_zones(zones)
        
        # Display zones
        self._log(f"\n{'─'*70}", "INFO")
        self._log("**🎯 KEY PRICE ZONES (Multi-Timeframe Confluence)**", "SUCCESS")
        self._log(f"{'─'*70}\n", "INFO")
        
        if major_zones:
            self._render_major_zones(major_zones, monthly_trend)
        
        if intermediate_zones:
            self._render_intermediate_zones(intermediate_zones, monthly_trend)
        
        if minor_zones:
            self._render_minor_zones(minor_zones, monthly_trend)
    
    def _find_confluence_zones(self, all_levels):
        """Group nearby levels (within 3%) into confluence zones."""
        zones = []
        used = set()
        
        for i, level1 in enumerate(all_levels):
            if i in used:
                continue
            
            zone = {
                "center": level1["price"],
                "type": level1["type"],
                "timeframes": [level1["tf"]],
                "weight": level1["weight"],
                "levels": [level1["price"]]
            }
            used.add(i)
            
            for j, level2 in enumerate(all_levels):
                if j <= i or j in used:
                    continue
                
                price_diff_pct = abs(level1["price"] - level2["price"]) / level1["price"] * 100
                if price_diff_pct <= 3 and level1["type"] == level2["type"]:
                    zone["timeframes"].append(level2["tf"])
                    zone["weight"] += level2["weight"]
                    zone["levels"].append(level2["price"])
                    used.add(j)
            
            zones.append(zone)
        
        return zones
    
    def _classify_zones(self, zones):
        """Classify zones into major/intermediate/minor."""
        major, intermediate, minor = [], [], []
        
        for zone in zones:
            tf_count = len(zone["timeframes"])
            has_monthly = "monthly" in zone["timeframes"]
            has_weekly = "weekly" in zone["timeframes"]
            
            if (has_monthly and tf_count >= 2) or zone["weight"] >= 5:
                zone["classification"] = "Major HTF Zone"
                major.append(zone)
            elif (has_weekly and tf_count >= 2) or (has_weekly and zone["weight"] >= 3):
                zone["classification"] = "Intermediate Zone"
                intermediate.append(zone)
            else:
                zone["classification"] = "Minor LTF Zone"
                minor.append(zone)
        
        return major, intermediate, minor
    
    def _format_zone_range(self, zone):
        """Format a zone's price range."""
        if len(zone['levels']) > 1:
            return f"₹{min(zone['levels']):.0f} - ₹{max(zone['levels']):.0f}"
        return f"₹{zone['center']:.0f}"
    
    def _render_major_zones(self, zones, monthly_trend):
        self._log("**🔴 MAJOR HTF ZONES** (Scenario-changing levels)", "ERROR")
        for zone in sorted(zones, key=lambda x: x["center"], reverse=(monthly_trend == "bullish")):
            zone_range = self._format_zone_range(zone)
            tfs = ", ".join(set(zone["timeframes"]))
            zone_type = zone["type"].upper()
            
            self._log(f"  • {zone_range} ({zone_type})", "ERROR")
            self._log(f"    Confluence: {tfs}", "INFO")
            
            if zone["type"] == "support":
                if monthly_trend == "bullish":
                    self._log("    ⚠️ Break invalidates Scenario A (Continuation)", "WARNING")
                else:
                    self._log("    ✓ Bounce triggers Scenario B (Pullback)", "INFO")
            else:
                if monthly_trend == "bullish":
                    self._log("    ✓ Break confirms Scenario A (Continuation)", "INFO")
                else:
                    self._log("    ⚠️ Break invalidates Scenario A (Continuation)", "WARNING")
        
        self._log("", "INFO")
    
    def _render_intermediate_zones(self, zones, monthly_trend):
        self._log("**🟡 INTERMEDIATE ZONES** (Pullback/consolidation levels)", "WARNING")
        for zone in sorted(zones, key=lambda x: x["center"], reverse=(monthly_trend == "bullish"))[:3]:
            zone_range = self._format_zone_range(zone)
            tfs = ", ".join(set(zone["timeframes"]))
            zone_type = zone["type"].upper()
            
            self._log(f"  • {zone_range} ({zone_type}) - {tfs}", "WARNING")
            
            if zone["type"] == "support":
                self._log("    Likely Scenario B zone (retest before continuation)", "INFO")
            else:
                self._log("    Short-term resistance (may cause pause)", "INFO")
        
        self._log("", "INFO")
    
    def _render_minor_zones(self, zones, monthly_trend):
        self._log("**🟢 MINOR LTF ZONES** (Intraday levels)", "SUCCESS")
        for zone in sorted(zones, key=lambda x: x["center"], reverse=(monthly_trend == "bullish"))[:2]:
            zone_range = self._format_zone_range(zone)
            zone_type = zone["type"].upper()
            
            self._log(f"  • {zone_range} ({zone_type}) - Short-term only", "SUCCESS")
