"""
Perception Reconciler — Phase-16: Trust-Weighted DOM/VLM Fusion

Reconciles DOM (authoritative) and VLM (advisory) observations into
trust-weighted facts before LLM synthesis.

Problem solved:
  DOM says RSI = 71 (overbought) but VLM says "momentum healthy, no exhaustion"
  → Without reconciliation, LLM gets contradictory inputs and may hallucinate.
  → With reconciliation, each claim is scored, conflicts are flagged, and the
    LLM receives a single coherent evidence brief.

Architecture:
  DOM Data  ──┐
              ├──► PerceptionReconciler ──► ReconciliationReport ──► LLM Prompt
  VLM Text  ──┘

Trust Hierarchy (immutable):
  1. DOM numeric data  → confidence 0.95 (authoritative, machine-read)
  2. DOM text data     → confidence 0.85 (parsed from page elements)
  3. VLM patterns      → confidence 0.60 (visual pattern recognition)
  4. VLM price levels  → confidence 0.40 (reading small text from screenshots)
  5. VLM sentiment     → confidence 0.55 (subjective visual interpretation)

Safety:
  - Read-only, observation layer only
  - Never triggers trades
  - Flags all conflicts for transparency
"""
import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ClaimSource(Enum):
    """Source of a perception claim."""
    DOM_NUMERIC = "dom_numeric"      # Price, indicator values from DOM
    DOM_TEXT = "dom_text"            # Text parsed from page elements
    VLM_PATTERN = "vlm_pattern"      # Visual pattern recognition
    VLM_LEVEL = "vlm_level"          # Price levels read from chart
    VLM_SENTIMENT = "vlm_sentiment"  # Subjective visual interpretation
    INFERRED = "inferred"            # Derived from other claims


# Trust weights per source (higher = more trusted)
TRUST_WEIGHTS = {
    ClaimSource.DOM_NUMERIC: 0.95,
    ClaimSource.DOM_TEXT: 0.85,
    ClaimSource.VLM_PATTERN: 0.60,
    ClaimSource.VLM_LEVEL: 0.40,
    ClaimSource.VLM_SENTIMENT: 0.55,
    ClaimSource.INFERRED: 0.30,
}


class ConflictSeverity(Enum):
    """How serious a DOM/VLM conflict is."""
    NONE = "none"
    LOW = "low"          # Minor disagreement, doesn't affect direction
    MEDIUM = "medium"    # Disagreement on strength/condition
    HIGH = "high"        # Direct contradiction on direction/trend
    CRITICAL = "critical"  # One says bullish, other says bearish


@dataclass
class PerceptionClaim:
    """A single claim about the market from any source."""
    dimension: str          # "trend", "momentum", "rsi", "support", "resistance", "volume", "pattern"
    value: Any              # The claimed value
    source: ClaimSource     # Where it came from
    confidence: float       # Trust weight (from TRUST_WEIGHTS)
    raw_text: str = ""      # Original text fragment that produced this claim


@dataclass
class ConflictRecord:
    """A detected conflict between DOM and VLM claims."""
    dimension: str
    dom_claim: Optional[PerceptionClaim]
    vlm_claim: Optional[PerceptionClaim]
    severity: ConflictSeverity
    resolution: str         # Which source wins and why
    detail: str = ""        # Human-readable explanation


@dataclass
class ReconciliationReport:
    """Complete reconciliation output — replaces raw DOM+VLM for LLM prompt."""
    # Trust-weighted facts (winner of each dimension)
    facts: Dict[str, PerceptionClaim] = field(default_factory=dict)
    
    # All conflicts detected
    conflicts: List[ConflictRecord] = field(default_factory=list)
    
    # Overall perception confidence (0.0 - 1.0)
    overall_confidence: float = 0.0
    
    # Data completeness score (what % of dimensions have data)
    completeness: float = 0.0
    
    # Summary for LLM prompt injection
    evidence_brief: str = ""
    conflict_brief: str = ""
    
    def has_critical_conflicts(self) -> bool:
        return any(c.severity == ConflictSeverity.CRITICAL for c in self.conflicts)
    
    def has_high_conflicts(self) -> bool:
        return any(c.severity in (ConflictSeverity.HIGH, ConflictSeverity.CRITICAL) for c in self.conflicts)


class PerceptionReconciler:
    """
    Reconciles DOM and VLM observations into trust-weighted facts.
    
    Usage:
        reconciler = PerceptionReconciler()
        report = reconciler.reconcile(dom_data, vlm_text)
        # report.evidence_brief → inject into LLM prompt
        # report.conflict_brief → flag conflicts for LLM awareness
    """
    
    def __init__(self):
        logger.info("Phase-16: PerceptionReconciler initialized")
    
    def reconcile(self, dom_data: Dict[str, Any], vlm_text: Optional[str]) -> ReconciliationReport:
        """
        Main reconciliation pipeline.
        
        Args:
            dom_data: DOM-extracted chart data (authoritative)
            vlm_text: VLM free-text observation (advisory)
            
        Returns:
            ReconciliationReport with trust-weighted facts and conflicts
        """
        report = ReconciliationReport()
        
        # Step 1: Extract structured claims from DOM
        dom_claims = self._extract_dom_claims(dom_data)
        
        # Step 2: Extract structured claims from VLM text
        vlm_claims = self._extract_vlm_claims(vlm_text) if vlm_text else []
        
        # Step 3: Reconcile by dimension
        all_dimensions = set()
        
        dom_by_dim: Dict[str, List[PerceptionClaim]] = {}
        for claim in dom_claims:
            dom_by_dim.setdefault(claim.dimension, []).append(claim)
            all_dimensions.add(claim.dimension)
        
        vlm_by_dim: Dict[str, List[PerceptionClaim]] = {}
        for claim in vlm_claims:
            vlm_by_dim.setdefault(claim.dimension, []).append(claim)
            all_dimensions.add(claim.dimension)
        
        # Step 4: For each dimension, reconcile
        for dim in all_dimensions:
            dom_dim_claims = dom_by_dim.get(dim, [])
            vlm_dim_claims = vlm_by_dim.get(dim, [])
            
            if dom_dim_claims and vlm_dim_claims:
                # Both sources have claims → check for conflict
                conflict = self._detect_conflict(dim, dom_dim_claims, vlm_dim_claims, dom_data)
                if conflict:
                    report.conflicts.append(conflict)
                
                # DOM wins for numeric data, VLM wins for visual patterns
                if dim in ("trend", "structure", "candlestick_pattern", "chart_pattern"):
                    # Visual dimensions → VLM is primary, DOM supplements
                    winner = max(vlm_dim_claims, key=lambda c: c.confidence)
                else:
                    # Numeric dimensions → DOM is primary
                    winner = max(dom_dim_claims, key=lambda c: c.confidence)
                
                report.facts[dim] = winner
                
            elif dom_dim_claims:
                # Only DOM has data
                winner = max(dom_dim_claims, key=lambda c: c.confidence)
                report.facts[dim] = winner
                
            elif vlm_dim_claims:
                # Only VLM has data
                winner = max(vlm_dim_claims, key=lambda c: c.confidence)
                report.facts[dim] = winner
        
        # Step 5: Calculate overall confidence
        target_dimensions = {"trend", "momentum", "support", "resistance", "volume", "structure"}
        covered = sum(1 for d in target_dimensions if d in report.facts)
        report.completeness = covered / len(target_dimensions) if target_dimensions else 0
        
        if report.facts:
            avg_confidence = sum(c.confidence for c in report.facts.values()) / len(report.facts)
            # Penalize for critical/high conflicts
            conflict_penalty = sum(
                0.15 if c.severity == ConflictSeverity.CRITICAL else
                0.10 if c.severity == ConflictSeverity.HIGH else
                0.05 if c.severity == ConflictSeverity.MEDIUM else 0
                for c in report.conflicts
            )
            report.overall_confidence = max(0.1, min(1.0, avg_confidence - conflict_penalty))
        
        # Step 6: Generate LLM-ready briefs
        report.evidence_brief = self._generate_evidence_brief(report)
        report.conflict_brief = self._generate_conflict_brief(report)
        
        logger.info(
            f"Phase-16: Reconciliation complete — {len(report.facts)} facts, "
            f"{len(report.conflicts)} conflicts, confidence={report.overall_confidence:.2f}, "
            f"completeness={report.completeness:.0%}"
        )
        
        return report
    
    # ─── DOM Claim Extraction ─────────────────────────────────────
    
    def _extract_dom_claims(self, dom_data: Dict[str, Any]) -> List[PerceptionClaim]:
        """Extract structured claims from DOM data."""
        claims = []
        
        # Price (always available)
        price = dom_data.get("price")
        if price:
            claims.append(PerceptionClaim(
                dimension="price",
                value=self._to_float(price),
                source=ClaimSource.DOM_NUMERIC,
                confidence=TRUST_WEIGHTS[ClaimSource.DOM_NUMERIC],
                raw_text=f"Price from page title: {price}"
            ))
        
        # Change
        change = dom_data.get("change")
        if change:
            claims.append(PerceptionClaim(
                dimension="change",
                value=change,
                source=ClaimSource.DOM_TEXT,
                confidence=TRUST_WEIGHTS[ClaimSource.DOM_TEXT],
                raw_text=f"Change: {change}"
            ))
        
        # Indicators
        indicators = dom_data.get("indicators", {})
        for name, value in indicators.items():
            name_lower = name.lower()
            
            # RSI → momentum dimension
            if "rsi" in name_lower:
                rsi_val = self._to_float(value)
                if rsi_val is not None:
                    claims.append(PerceptionClaim(
                        dimension="rsi",
                        value=rsi_val,
                        source=ClaimSource.DOM_NUMERIC,
                        confidence=TRUST_WEIGHTS[ClaimSource.DOM_NUMERIC],
                        raw_text=f"{name}: {value}"
                    ))
                    # Derive momentum claim from RSI
                    if rsi_val > 70:
                        claims.append(PerceptionClaim(
                            dimension="momentum_condition",
                            value="exhausting",
                            source=ClaimSource.DOM_NUMERIC,
                            confidence=0.90,  # RSI is very reliable for this
                            raw_text=f"RSI={rsi_val} > 70 → overbought/exhausting"
                        ))
                    elif rsi_val < 30:
                        claims.append(PerceptionClaim(
                            dimension="momentum_condition",
                            value="improving",
                            source=ClaimSource.DOM_NUMERIC,
                            confidence=0.90,
                            raw_text=f"RSI={rsi_val} < 30 → oversold/improving"
                        ))
            
            # Moving averages → support/resistance
            elif any(ma in name_lower for ma in ("ema", "sma", "wma")):
                ma_val = self._to_float(value)
                price_val = self._to_float(price)
                if ma_val is not None and price_val is not None:
                    if ma_val < price_val:
                        claims.append(PerceptionClaim(
                            dimension="support",
                            value=ma_val,
                            source=ClaimSource.DOM_NUMERIC,
                            confidence=TRUST_WEIGHTS[ClaimSource.DOM_NUMERIC],
                            raw_text=f"{name}={value} (below price → dynamic support)"
                        ))
                    else:
                        claims.append(PerceptionClaim(
                            dimension="resistance",
                            value=ma_val,
                            source=ClaimSource.DOM_NUMERIC,
                            confidence=TRUST_WEIGHTS[ClaimSource.DOM_NUMERIC],
                            raw_text=f"{name}={value} (above price → dynamic resistance)"
                        ))
            
            # OHLC → support/resistance
            elif name_lower == "high":
                high_val = self._to_float(value)
                if high_val is not None:
                    claims.append(PerceptionClaim(
                        dimension="resistance",
                        value=high_val,
                        source=ClaimSource.DOM_NUMERIC,
                        confidence=TRUST_WEIGHTS[ClaimSource.DOM_NUMERIC],
                        raw_text=f"Current bar High={value}"
                    ))
            
            elif name_lower == "low":
                low_val = self._to_float(value)
                if low_val is not None:
                    claims.append(PerceptionClaim(
                        dimension="support",
                        value=low_val,
                        source=ClaimSource.DOM_NUMERIC,
                        confidence=TRUST_WEIGHTS[ClaimSource.DOM_NUMERIC],
                        raw_text=f"Current bar Low={value}"
                    ))
            
            # MACD
            elif "macd" in name_lower:
                macd_val = self._to_float(value)
                if macd_val is not None:
                    claims.append(PerceptionClaim(
                        dimension="macd",
                        value=macd_val,
                        source=ClaimSource.DOM_NUMERIC,
                        confidence=TRUST_WEIGHTS[ClaimSource.DOM_NUMERIC],
                        raw_text=f"MACD={value}"
                    ))
        
        # Volume
        volume = dom_data.get("volume")
        if volume:
            claims.append(PerceptionClaim(
                dimension="volume",
                value=volume,
                source=ClaimSource.DOM_NUMERIC,
                confidence=TRUST_WEIGHTS[ClaimSource.DOM_NUMERIC],
                raw_text=f"Volume from DOM: {volume}"
            ))
        
        return claims
    
    # ─── VLM Claim Extraction ─────────────────────────────────────
    
    def _extract_vlm_claims(self, vlm_text: str) -> List[PerceptionClaim]:
        """Extract structured claims from VLM free-text observation."""
        claims = []
        if not vlm_text:
            return claims
        
        text_lower = vlm_text.lower()
        
        # ── Trend direction ──
        trend = self._extract_vlm_trend(text_lower)
        if trend:
            claims.append(PerceptionClaim(
                dimension="trend",
                value=trend,
                source=ClaimSource.VLM_SENTIMENT,
                confidence=TRUST_WEIGHTS[ClaimSource.VLM_SENTIMENT],
                raw_text=self._find_context(vlm_text, trend)
            ))
        
        # ── Structure ──
        structure = self._extract_vlm_structure(text_lower)
        if structure:
            claims.append(PerceptionClaim(
                dimension="structure",
                value=structure,
                source=ClaimSource.VLM_PATTERN,
                confidence=TRUST_WEIGHTS[ClaimSource.VLM_PATTERN],
                raw_text=self._find_context(vlm_text, structure)
            ))
        
        # ── Momentum description ──
        momentum = self._extract_vlm_momentum(text_lower)
        if momentum:
            claims.append(PerceptionClaim(
                dimension="momentum",
                value=momentum,
                source=ClaimSource.VLM_SENTIMENT,
                confidence=TRUST_WEIGHTS[ClaimSource.VLM_SENTIMENT],
                raw_text=self._find_context(vlm_text, momentum)
            ))
        
        # ── Momentum condition from VLM ──
        mom_condition = self._extract_vlm_momentum_condition(text_lower)
        if mom_condition:
            claims.append(PerceptionClaim(
                dimension="momentum_condition",
                value=mom_condition,
                source=ClaimSource.VLM_SENTIMENT,
                confidence=TRUST_WEIGHTS[ClaimSource.VLM_SENTIMENT],
                raw_text=self._find_context(vlm_text, mom_condition)
            ))
        
        # ── Price levels (support/resistance) ──
        levels = self._extract_vlm_price_levels(vlm_text)
        price_val = None
        # Try to get price context for level classification
        price_match = re.search(r'current\s+price[:\s]*([\d,]+\.?\d*)', text_lower)
        if price_match:
            price_val = self._to_float(price_match.group(1))
        
        for level in levels:
            level_val = self._to_float(level)
            if level_val is not None:
                # Classify as support or resistance based on context
                dim = "support" if price_val and level_val < price_val else "resistance"
                claims.append(PerceptionClaim(
                    dimension=dim,
                    value=level_val,
                    source=ClaimSource.VLM_LEVEL,
                    confidence=TRUST_WEIGHTS[ClaimSource.VLM_LEVEL],
                    raw_text=f"VLM reported level: {level}"
                ))
        
        # ── Volume assessment ──
        vol = self._extract_vlm_volume(text_lower)
        if vol:
            claims.append(PerceptionClaim(
                dimension="volume_trend",
                value=vol,
                source=ClaimSource.VLM_SENTIMENT,
                confidence=TRUST_WEIGHTS[ClaimSource.VLM_SENTIMENT],
                raw_text=self._find_context(vlm_text, vol)
            ))
        
        # ── Candlestick patterns ──
        pattern = self._extract_vlm_candlestick(text_lower)
        if pattern:
            claims.append(PerceptionClaim(
                dimension="candlestick_pattern",
                value=pattern,
                source=ClaimSource.VLM_PATTERN,
                confidence=TRUST_WEIGHTS[ClaimSource.VLM_PATTERN],
                raw_text=self._find_context(vlm_text, pattern)
            ))
        
        # ── Chart pattern ──
        chart_pattern = self._extract_vlm_chart_pattern(text_lower)
        if chart_pattern:
            claims.append(PerceptionClaim(
                dimension="chart_pattern",
                value=chart_pattern,
                source=ClaimSource.VLM_PATTERN,
                confidence=TRUST_WEIGHTS[ClaimSource.VLM_PATTERN],
                raw_text=self._find_context(vlm_text, chart_pattern)
            ))
        
        return claims
    
    # ─── VLM Text Parsers ─────────────────────────────────────────
    
    def _extract_vlm_trend(self, text: str) -> Optional[str]:
        """Extract trend direction from VLM text."""
        # Strong signals first
        if any(w in text for w in ("strong uptrend", "clearly bullish", "strong bullish", "decisive upward")):
            return "bullish"
        if any(w in text for w in ("strong downtrend", "clearly bearish", "strong bearish", "decisive downward")):
            return "bearish"
        
        # Count directional keywords
        bull_keywords = ("bullish", "uptrend", "upward", "rising", "ascending", "higher highs", "higher lows")
        bear_keywords = ("bearish", "downtrend", "downward", "falling", "descending", "lower highs", "lower lows")
        side_keywords = ("sideways", "range-bound", "consolidat", "flat", "neutral", "choppy")
        
        bull_count = sum(1 for kw in bull_keywords if kw in text)
        bear_count = sum(1 for kw in bear_keywords if kw in text)
        side_count = sum(1 for kw in side_keywords if kw in text)
        
        max_count = max(bull_count, bear_count, side_count)
        if max_count == 0:
            return None
        
        if bull_count == max_count and bull_count > bear_count:
            return "bullish"
        elif bear_count == max_count and bear_count > bull_count:
            return "bearish"
        elif side_count == max_count:
            return "sideways"
        
        return None
    
    def _extract_vlm_structure(self, text: str) -> Optional[str]:
        """Extract price structure from VLM text."""
        if "higher high" in text and "higher low" in text:
            return "higher-highs"
        if "lower high" in text and "lower low" in text:
            return "lower-lows"
        if any(w in text for w in ("range-bound", "range bound", "trading range", "between support and resistance")):
            return "range-bound"
        if any(w in text for w in ("consolidat", "tight range", "narrowing", "coiling")):
            return "consolidation"
        return None
    
    def _extract_vlm_momentum(self, text: str) -> Optional[str]:
        """Extract momentum strength from VLM text."""
        if any(w in text for w in ("strong bullish momentum", "powerful upward", "aggressive buying")):
            return "strong bullish"
        if any(w in text for w in ("strong bearish momentum", "powerful downward", "aggressive selling")):
            return "strong bearish"
        if any(w in text for w in ("moderate bullish", "mild upward", "slight bullish")):
            return "moderate bullish"
        if any(w in text for w in ("moderate bearish", "mild downward", "slight bearish")):
            return "moderate bearish"
        if any(w in text for w in ("weak momentum", "no clear momentum", "neutral momentum", "low momentum")):
            return "neutral"
        return None
    
    def _extract_vlm_momentum_condition(self, text: str) -> Optional[str]:
        """Extract momentum condition from VLM text."""
        if any(w in text for w in ("overbought", "exhaustion", "exhausted", "overextended", "losing steam")):
            return "exhausting"
        if any(w in text for w in ("oversold", "bottoming", "capitulation", "washout")):
            return "improving"
        if any(w in text for w in ("accelerat", "expanding momentum", "increasing momentum", "building strength")):
            return "expanding"
        if any(w in text for w in ("decelerating", "fading", "weakening momentum", "momentum waning")):
            return "exhausting"
        return None
    
    def _extract_vlm_price_levels(self, text: str) -> List[str]:
        """Extract specific price levels mentioned in VLM text."""
        # Match patterns like "support at 1,400", "resistance near 1,500.50", "level of Rs 3,200"
        patterns = [
            r'(?:support|resistance|level|zone|area)\s*(?:at|near|around|of|:)\s*(?:Rs\.?\s*)?([\d,]+\.?\d*)',
            r'(?:Rs\.?\s*)([\d,]+\.?\d*)\s*(?:support|resistance|level|zone)',
            r'(?:bounced|reversed|rejected)\s*(?:at|from|near)\s*(?:Rs\.?\s*)?([\d,]+\.?\d*)',
            r'price\s*(?:of|at|near)\s*(?:Rs\.?\s*)?([\d,]+\.?\d*)',
        ]
        
        levels = set()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                cleaned = match.replace(",", "")
                if cleaned and self._to_float(cleaned) is not None:
                    val = self._to_float(cleaned)
                    # Filter obviously wrong levels (< 1 or > 1,000,000)
                    if val and 1 < val < 1_000_000:
                        levels.add(cleaned)
        
        return list(levels)
    
    def _extract_vlm_volume(self, text: str) -> Optional[str]:
        """Extract volume trend from VLM text."""
        if any(w in text for w in ("volume spike", "volume surge", "heavy volume", "abnormal volume", "volume climax")):
            return "spike"
        if any(w in text for w in ("increasing volume", "volume increase", "rising volume", "volume confirms", "volume expanding")):
            return "increasing"
        if any(w in text for w in ("decreasing volume", "volume decline", "falling volume", "low volume", "thin volume", "dry volume")):
            return "decreasing"
        if any(w in text for w in ("no volume", "volume absent", "volume not visible")):
            return "unavailable"
        return None
    
    def _extract_vlm_candlestick(self, text: str) -> Optional[str]:
        """Extract candlestick patterns from VLM text."""
        patterns = {
            "doji": ("doji",),
            "hammer": ("hammer",),
            "inverted hammer": ("inverted hammer",),
            "shooting star": ("shooting star",),
            "engulfing bullish": ("bullish engulfing",),
            "engulfing bearish": ("bearish engulfing",),
            "morning star": ("morning star",),
            "evening star": ("evening star",),
            "pin bar": ("pin bar",),
            "inside bar": ("inside bar",),
            "marubozu": ("marubozu",),
            "spinning top": ("spinning top",),
            "three white soldiers": ("three white soldiers",),
            "three black crows": ("three black crows",),
            "harami": ("harami",),
            "tweezer": ("tweezer",),
        }
        found = []
        for name, keywords in patterns.items():
            if any(kw in text for kw in keywords):
                found.append(name)
        
        return ", ".join(found) if found else None
    
    def _extract_vlm_chart_pattern(self, text: str) -> Optional[str]:
        """Extract chart patterns from VLM text."""
        patterns = {
            "ascending triangle": ("ascending triangle",),
            "descending triangle": ("descending triangle",),
            "symmetrical triangle": ("symmetrical triangle", "triangle"),
            "head and shoulders": ("head and shoulders", "head & shoulders"),
            "inverse head and shoulders": ("inverse head and shoulders", "inverse h&s"),
            "double top": ("double top",),
            "double bottom": ("double bottom",),
            "cup and handle": ("cup and handle", "cup & handle"),
            "flag": ("bull flag", "bear flag", "flag pattern"),
            "pennant": ("pennant",),
            "wedge": ("rising wedge", "falling wedge", "wedge"),
            "channel": ("ascending channel", "descending channel", "channel"),
            "broadening": ("broadening",),
        }
        found = []
        for name, keywords in patterns.items():
            if any(kw in text for kw in keywords):
                found.append(name)
        
        return ", ".join(found) if found else None
    
    # ─── Conflict Detection ───────────────────────────────────────
    
    def _detect_conflict(
        self,
        dimension: str,
        dom_claims: List[PerceptionClaim],
        vlm_claims: List[PerceptionClaim],
        dom_data: Dict[str, Any]
    ) -> Optional[ConflictRecord]:
        """Detect and classify conflicts between DOM and VLM claims."""
        
        # Get representative values
        dom_val = dom_claims[0].value if dom_claims else None
        vlm_val = vlm_claims[0].value if vlm_claims else None
        
        if dom_val is None or vlm_val is None:
            return None
        
        # ── Trend conflict ──
        if dimension == "trend":
            return self._check_trend_conflict(dom_claims, vlm_claims)
        
        # ── Momentum condition conflict (RSI vs VLM) ──
        if dimension == "momentum_condition":
            return self._check_momentum_conflict(dom_claims, vlm_claims, dom_data)
        
        # ── Support/Resistance level conflict ──
        if dimension in ("support", "resistance"):
            return self._check_level_conflict(dimension, dom_claims, vlm_claims)
        
        # ── Volume conflict ──
        if dimension == "volume_trend":
            return self._check_volume_conflict(dom_claims, vlm_claims)
        
        return None
    
    def _check_trend_conflict(
        self,
        dom_claims: List[PerceptionClaim],
        vlm_claims: List[PerceptionClaim]
    ) -> Optional[ConflictRecord]:
        """Check for trend direction conflict."""
        # DOM rarely has explicit trend — if it does (from change %), compare
        dom_trend = None
        for c in dom_claims:
            if c.dimension == "trend":
                dom_trend = str(c.value).lower()
        
        vlm_trend = None
        for c in vlm_claims:
            if c.dimension == "trend":
                vlm_trend = str(c.value).lower()
        
        if dom_trend and vlm_trend and dom_trend != vlm_trend:
            # Opposite directions = CRITICAL
            opposites = {("bullish", "bearish"), ("bearish", "bullish")}
            if (dom_trend, vlm_trend) in opposites:
                severity = ConflictSeverity.CRITICAL
            else:
                severity = ConflictSeverity.MEDIUM
            
            return ConflictRecord(
                dimension="trend",
                dom_claim=dom_claims[0],
                vlm_claim=vlm_claims[0],
                severity=severity,
                resolution=f"VLM trend '{vlm_trend}' preferred (visual pattern authority)",
                detail=f"DOM suggests '{dom_trend}' but VLM sees '{vlm_trend}'"
            )
        return None
    
    def _check_momentum_conflict(
        self,
        dom_claims: List[PerceptionClaim],
        vlm_claims: List[PerceptionClaim],
        dom_data: Dict[str, Any]
    ) -> Optional[ConflictRecord]:
        """Check for momentum/RSI vs VLM assessment conflict."""
        dom_condition = None
        vlm_condition = None
        
        for c in dom_claims:
            dom_condition = str(c.value).lower()
        for c in vlm_claims:
            vlm_condition = str(c.value).lower()
        
        if not dom_condition or not vlm_condition:
            return None
        
        # Classify as conflict when they directionally disagree
        exhausting_words = ("exhausting", "overbought", "overextended")
        improving_words = ("improving", "oversold", "bottoming")
        expanding_words = ("expanding", "accelerating")
        
        dom_is_exhausting = any(w in dom_condition for w in exhausting_words)
        vlm_is_expanding = any(w in vlm_condition for w in expanding_words)
        vlm_is_improving = any(w in vlm_condition for w in improving_words)
        
        dom_is_improving = any(w in dom_condition for w in improving_words)
        vlm_is_exhausting = any(w in vlm_condition for w in exhausting_words)
        
        if (dom_is_exhausting and vlm_is_expanding) or (dom_is_improving and vlm_is_exhausting):
            return ConflictRecord(
                dimension="momentum_condition",
                dom_claim=dom_claims[0],
                vlm_claim=vlm_claims[0],
                severity=ConflictSeverity.HIGH,
                resolution=f"DOM wins (RSI is numeric fact: {dom_claims[0].raw_text})",
                detail=f"DOM says '{dom_condition}' (from RSI/indicator) but VLM says '{vlm_condition}' (visual impression). "
                       f"DOM numeric data is authoritative for momentum condition."
            )
        
        return None
    
    def _check_level_conflict(
        self,
        dimension: str,
        dom_claims: List[PerceptionClaim],
        vlm_claims: List[PerceptionClaim]
    ) -> Optional[ConflictRecord]:
        """Check for support/resistance level disagreement."""
        dom_levels = [self._to_float(c.value) for c in dom_claims if self._to_float(c.value) is not None]
        vlm_levels = [self._to_float(c.value) for c in vlm_claims if self._to_float(c.value) is not None]
        
        if not dom_levels or not vlm_levels:
            return None
        
        # Check if levels are within 3% of each other (reasonable agreement)
        dom_avg = sum(dom_levels) / len(dom_levels)
        vlm_avg = sum(vlm_levels) / len(vlm_levels)
        
        if dom_avg == 0:
            return None
        
        pct_diff = abs(dom_avg - vlm_avg) / dom_avg * 100
        
        if pct_diff > 5:
            severity = ConflictSeverity.MEDIUM if pct_diff < 15 else ConflictSeverity.HIGH
            return ConflictRecord(
                dimension=dimension,
                dom_claim=dom_claims[0],
                vlm_claim=vlm_claims[0],
                severity=severity,
                resolution=f"DOM levels preferred (machine-read, {pct_diff:.1f}% divergence)",
                detail=f"DOM {dimension}: {dom_levels} vs VLM {dimension}: {vlm_levels} ({pct_diff:.1f}% apart)"
            )
        
        return None
    
    def _check_volume_conflict(
        self,
        dom_claims: List[PerceptionClaim],
        vlm_claims: List[PerceptionClaim]
    ) -> Optional[ConflictRecord]:
        """Check for volume assessment conflict."""
        # DOM has a raw number, VLM has a qualitative assessment
        # Direct conflict is rare — flag only if VLM says "spike" but DOM shows normal-range volume
        return None  # TODO: Implement when historical volume data is available for comparison
    
    # ─── Evidence Brief Generation ────────────────────────────────
    
    def _generate_evidence_brief(self, report: ReconciliationReport) -> str:
        """Generate structured evidence brief for LLM prompt injection."""
        lines = []
        lines.append("RECONCILED PERCEPTION (trust-weighted from DOM + VLM):")
        lines.append(f"Overall Confidence: {report.overall_confidence:.0%}")
        lines.append(f"Data Completeness: {report.completeness:.0%}")
        lines.append("")
        
        # Group facts by category
        direction_dims = ("trend", "structure")
        momentum_dims = ("momentum", "momentum_condition", "rsi", "macd")
        level_dims = ("support", "resistance")
        volume_dims = ("volume", "volume_trend")
        pattern_dims = ("candlestick_pattern", "chart_pattern")
        
        # Direction
        dir_facts = [(d, report.facts[d]) for d in direction_dims if d in report.facts]
        if dir_facts:
            lines.append("DIRECTION:")
            for dim, claim in dir_facts:
                trust = "HIGH" if claim.confidence >= 0.8 else "MEDIUM" if claim.confidence >= 0.5 else "LOW"
                lines.append(f"  - {dim}: {claim.value} [trust={trust}, source={claim.source.value}]")
        
        # Momentum
        mom_facts = [(d, report.facts[d]) for d in momentum_dims if d in report.facts]
        if mom_facts:
            lines.append("MOMENTUM:")
            for dim, claim in mom_facts:
                trust = "HIGH" if claim.confidence >= 0.8 else "MEDIUM" if claim.confidence >= 0.5 else "LOW"
                lines.append(f"  - {dim}: {claim.value} [trust={trust}, source={claim.source.value}]")
        
        # Levels
        support_facts = [report.facts[d] for d in ["support"] if d in report.facts]
        resist_facts = [report.facts[d] for d in ["resistance"] if d in report.facts]
        if support_facts or resist_facts:
            lines.append("KEY LEVELS:")
            # Collect all support claims from the reconciliation
            all_support = [f for f in report.facts.values() if f.dimension == "support"]
            all_resist = [f for f in report.facts.values() if f.dimension == "resistance"]
            for claim in all_support:
                trust = "HIGH" if claim.confidence >= 0.8 else "MEDIUM" if claim.confidence >= 0.5 else "LOW"
                lines.append(f"  - support: {claim.value} [trust={trust}, {claim.raw_text}]")
            for claim in all_resist:
                trust = "HIGH" if claim.confidence >= 0.8 else "MEDIUM" if claim.confidence >= 0.5 else "LOW"
                lines.append(f"  - resistance: {claim.value} [trust={trust}, {claim.raw_text}]")
        
        # Volume
        vol_facts = [(d, report.facts[d]) for d in volume_dims if d in report.facts]
        if vol_facts:
            lines.append("VOLUME:")
            for dim, claim in vol_facts:
                trust = "HIGH" if claim.confidence >= 0.8 else "MEDIUM" if claim.confidence >= 0.5 else "LOW"
                lines.append(f"  - {dim}: {claim.value} [trust={trust}, source={claim.source.value}]")
        
        # Patterns
        pat_facts = [(d, report.facts[d]) for d in pattern_dims if d in report.facts]
        if pat_facts:
            lines.append("PATTERNS:")
            for dim, claim in pat_facts:
                lines.append(f"  - {dim}: {claim.value} [trust=MEDIUM, source={claim.source.value}]")
        
        return "\n".join(lines)
    
    def _generate_conflict_brief(self, report: ReconciliationReport) -> str:
        """Generate conflict brief for LLM awareness."""
        if not report.conflicts:
            return "No conflicts detected between DOM and VLM observations."
        
        lines = []
        lines.append(f"CONFLICTS DETECTED ({len(report.conflicts)}):")
        
        for i, conflict in enumerate(report.conflicts, 1):
            sev_icon = {
                ConflictSeverity.CRITICAL: "!!",
                ConflictSeverity.HIGH: "!",
                ConflictSeverity.MEDIUM: "~",
                ConflictSeverity.LOW: ".",
            }.get(conflict.severity, "?")
            
            lines.append(f"  [{sev_icon}] {conflict.dimension}: {conflict.detail}")
            lines.append(f"      Resolution: {conflict.resolution}")
        
        lines.append("")
        lines.append("INSTRUCTION: Where conflicts exist, weight DOM numeric data higher than VLM visual impressions.")
        
        return "\n".join(lines)
    
    # ─── Utilities ────────────────────────────────────────────────
    
    def _to_float(self, value: Any) -> Optional[float]:
        """Safely convert a value to float."""
        if value is None:
            return None
        try:
            return float(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return None
    
    def _find_context(self, full_text: str, keyword: str, window: int = 80) -> str:
        """Find surrounding context for a keyword in text."""
        idx = full_text.lower().find(keyword.lower())
        if idx == -1:
            return keyword
        start = max(0, idx - window // 2)
        end = min(len(full_text), idx + len(keyword) + window // 2)
        return full_text[start:end].strip()
