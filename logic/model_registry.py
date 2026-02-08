"""
Model Registry — Phase-D: Model Quality Ceiling

Auto-detects available Ollama models and selects the best one for each role.
Eliminates the hardcoded model problem: if a user pulls a better model,
the agent automatically upgrades.

Roles:
  - TEXT_LLM: Synthesis/reasoning (JSON output) → prefers larger models
  - VISION_VLM: Chart pattern recognition → prefers vision-capable models

Safety:
  - Read-only model discovery
  - Never downloads/pulls models (user must pre-pull)
  - Graceful fallback to defaults
"""
import logging
import requests
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelProfile:
    """Configuration profile for a specific model."""
    name: str
    role: str                   # "text" or "vision"
    priority: int               # Higher = preferred (0-100)
    context_length: int         # Max context window
    num_predict: int            # Output token budget
    temperature: float          # Default temperature
    supports_json: bool         # Reliable for structured JSON output
    notes: str = ""


# ─── Model Preference Registry ──────────────────────────────────
# Priority: higher number = preferred when available
# These are the models the agent knows how to use well

TEXT_MODEL_PROFILES: List[ModelProfile] = [
    # Top tier — large reasoning models
    ModelProfile("deepseek-r1:14b", "text", 95, 32768, 3000, 0.1, True, "Excellent reasoning, great JSON"),
    ModelProfile("qwen2.5:14b", "text", 90, 32768, 3000, 0.1, True, "Strong reasoning, reliable JSON"),
    ModelProfile("qwen2.5:7b", "text", 85, 32768, 2500, 0.1, True, "Good reasoning, reliable JSON"),
    ModelProfile("llama3.1:8b", "text", 80, 8192, 2500, 0.1, True, "Solid all-rounder"),
    ModelProfile("mistral:7b", "text", 75, 8192, 2000, 0.1, True, "Good instruction following"),
    ModelProfile("gemma2:9b", "text", 73, 8192, 2500, 0.1, True, "Google's efficient model"),
    ModelProfile("phi3:14b", "text", 72, 4096, 2000, 0.1, True, "Microsoft reasoning model"),
    # Default tier — always available as fallback
    ModelProfile("llama3.2:3b", "text", 50, 4096, 2000, 0.1, False, "Default fallback — struggles with complex JSON"),
    ModelProfile("llama3.2:1b", "text", 30, 4096, 1500, 0.1, False, "Minimal — last resort"),
]

VISION_MODEL_PROFILES: List[ModelProfile] = [
    # Vision models — chart pattern recognition
    ModelProfile("llava:34b", "vision", 95, 4096, 2500, 0.1, False, "Best visual understanding"),
    ModelProfile("llava:13b", "vision", 85, 4096, 2000, 0.1, False, "Strong visual comprehension"),
    ModelProfile("llava-llama3:8b", "vision", 78, 4096, 2000, 0.1, False, "LLaVA with Llama3 base"),
    ModelProfile("llava:7b", "vision", 70, 4096, 2000, 0.1, False, "Default vision model"),
    ModelProfile("llava-phi3", "vision", 65, 4096, 1500, 0.1, False, "Lightweight vision"),
    ModelProfile("llama3.2-vision", "vision", 60, 4096, 2000, 0.1, False, "Llama vision variant"),
    ModelProfile("bakllava", "vision", 55, 4096, 1500, 0.1, False, "BakLLaVA variant"),
]


class ModelRegistry:
    """
    Auto-detects best available Ollama models for each role.
    
    Usage:
        registry = ModelRegistry("http://localhost:11434")
        text_model = registry.get_best_text_model()
        vision_model = registry.get_best_vision_model()
    """
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip('/')
        self._available_models: List[str] = []
        self._text_model: Optional[ModelProfile] = None
        self._vision_model: Optional[ModelProfile] = None
        self._discovered = False
    
    def discover(self) -> bool:
        """
        Query Ollama for available models and select best for each role.
        
        Returns:
            True if discovery succeeded
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()
            
            models = response.json().get("models", [])
            self._available_models = []
            self._model_sizes: Dict[str, int] = {}  # model_name → size in bytes
            
            for m in models:
                name = m.get("name", "")
                size = m.get("size", 0)
                self._available_models.append(name)
                self._model_sizes[name] = size
            
            logger.info(f"Phase-D: Discovered {len(models)} Ollama models: {[m.get('name') for m in models]}")
            
            # Select best text model
            self._text_model = self._select_best(TEXT_MODEL_PROFILES)
            
            # Select best vision model
            self._vision_model = self._select_best(VISION_MODEL_PROFILES)
            
            self._discovered = True
            
            if self._text_model:
                logger.info(f"Phase-D: Best text model: {self._text_model.name} (priority={self._text_model.priority})")
            if self._vision_model:
                logger.info(f"Phase-D: Best vision model: {self._vision_model.name} (priority={self._vision_model.priority})")
            
            return True
            
        except Exception as e:
            logger.error(f"Phase-D: Model discovery failed: {e}")
            return False
    
    def _select_best(self, profiles: List[ModelProfile]) -> Optional[ModelProfile]:
        """Select the highest-priority model that's actually available."""
        # Sort by priority descending
        sorted_profiles = sorted(profiles, key=lambda p: p.priority, reverse=True)
        
        for profile in sorted_profiles:
            if self._is_available(profile.name):
                return profile
        
        return None
    
    def _is_available(self, model_name: str) -> bool:
        """Check if a model is available in Ollama."""
        model_base = model_name.split(":")[0].lower()
        model_tag = model_name.split(":")[1].lower() if ":" in model_name else None
        
        for available in self._available_models:
            avail_base = available.split(":")[0].lower()
            avail_tag = available.split(":")[1].lower() if ":" in available else "latest"
            
            # Base names must match
            if model_base != avail_base:
                continue
            
            # If profile specifies a size tag (like "3b", "7b", "14b")
            if model_tag:
                # Exact tag match
                if model_tag == avail_tag:
                    return True
                # Size tag within available tag (e.g., "7b" in "7b-v1.6")
                if model_tag in avail_tag:
                    return True
                # Available is "latest" — match based on model file size
                if avail_tag == "latest":
                    # Estimate model size: check if the "latest" model size
                    # is in the right range for this profile's expected size
                    actual_size_gb = self._model_sizes.get(available, 0) / (1024**3)
                    expected_sizes = {
                        "1b": (0.5, 1.5), "3b": (1.5, 3.5), "7b": (3.5, 8.0),
                        "8b": (3.5, 8.0), "9b": (4.0, 9.0), "13b": (6.0, 15.0),
                        "14b": (7.0, 16.0), "34b": (17.0, 40.0),
                    }
                    tag_base = ''.join(c for c in model_tag if c.isdigit() or c == 'b')
                    if tag_base in expected_sizes:
                        lo, hi = expected_sizes[tag_base]
                        if lo <= actual_size_gb <= hi:
                            return True
                    # If we can't determine size, match smallest profile
                    # for this base name (conservative fallback)
                    elif actual_size_gb > 0:
                        return True  # At least the base model exists
                
                continue
            else:
                # No tag specified in profile — match any version
                return True
        
        return False
    
    def get_best_text_model(self) -> ModelProfile:
        """
        Get the best available text/reasoning model.
        
        Returns:
            ModelProfile for the best available model (falls back to llama3.2:3b)
        """
        if not self._discovered:
            self.discover()
        
        if self._text_model:
            return self._text_model
        
        # Absolute fallback
        logger.warning("Phase-D: No known text models found, falling back to llama3.2")
        return ModelProfile("llama3.2", "text", 50, 4096, 2000, 0.1, False, "Fallback")
    
    def get_best_vision_model(self) -> ModelProfile:
        """
        Get the best available vision model.
        
        Returns:
            ModelProfile for the best available model (falls back to llava:7b)
        """
        if not self._discovered:
            self.discover()
        
        if self._vision_model:
            return self._vision_model
        
        # Absolute fallback
        logger.warning("Phase-D: No known vision models found, falling back to llava:7b")
        return ModelProfile("llava:7b", "vision", 70, 4096, 2000, 0.1, False, "Fallback")
    
    def get_model_upgrade_suggestions(self) -> List[str]:
        """
        Suggest models the user could pull for better performance.
        
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        text = self.get_best_text_model()
        if text.priority < 80:
            suggestions.append(
                f"Text model: Currently using {text.name} (priority {text.priority}). "
                f"For better JSON reasoning, run: ollama pull qwen2.5:7b"
            )
        
        vision = self.get_best_vision_model()
        if vision.priority < 80:
            suggestions.append(
                f"Vision model: Currently using {vision.name} (priority {vision.priority}). "
                f"For better chart reading, run: ollama pull llava:13b"
            )
        
        return suggestions
    
    def get_status_summary(self) -> str:
        """Get a brief status string for display."""
        if not self._discovered:
            self.discover()
        
        text = self.get_best_text_model()
        vision = self.get_best_vision_model()
        
        text_quality = "STRONG" if text.priority >= 80 else "MODERATE" if text.priority >= 60 else "BASIC"
        vision_quality = "STRONG" if vision.priority >= 80 else "MODERATE" if vision.priority >= 60 else "BASIC"
        
        return (
            f"Text: {text.name} [{text_quality}] | "
            f"Vision: {vision.name} [{vision_quality}]"
        )
