"""
validation_config.py - Configuration for the Step Validation System

Adjust these settings to customize validation behavior
"""

# ==============================================================================
# CONFIDENCE SCORING THRESHOLDS
# ==============================================================================

# Similarity thresholds for confidence levels
CONFIDENCE_THRESHOLDS = {
    "excellent": 0.8,      # 80%+ similarity → 95% confidence
    "good": 0.6,           # 60-80% similarity → 70% confidence
    "fair": 0.4,           # 40-60% similarity → 50% confidence
    "poor": 0.0,           # <40% similarity → 30% confidence
}

# Minimum similarity score to accept a RAG match
MIN_SIMILARITY_THRESHOLD = 0.25

# ==============================================================================
# FORMAT VALIDATION RULES
# ==============================================================================

# Minimum step action length (characters)
MIN_ACTION_LENGTH = 5

# Maximum number of steps to generate
MAX_STEPS = 20

# Required fields in each step
REQUIRED_STEP_FIELDS = ["step", "action", "description"]

# ==============================================================================
# DATASET CONFIGURATION
# ==============================================================================

# Dataset file paths (relative to llm/ directory)
DATASET_PATHS = {
    "general_software": "llm_dataset.jsonl",
    "game_2048": "rag_2048.jsonl",
}

# Expected dataset sizes (for validation purposes)
DATASET_SIZES = {
    "general_software": 79,
    "game_2048": 47,
}

# ==============================================================================
# CATEGORY-SPECIFIC VALIDATION RULES
# ==============================================================================

# Keywords to look for in 2048 game instructions
GAME_2048_KEYWORDS = {
    "required": ["focus", "game", "window"],
    "preferred": ["tile", "merge", "arrow", "swipe", "key"],
    "min_required_matches": 1,
}

# Keywords to look for in software development instructions
SOFTWARE_DEV_KEYWORDS = {
    "typical": ["create", "implement", "add", "set up", "button", "field", "input", "output"],
    "min_typical_matches": 0,  # Warning if less than this
}

# ==============================================================================
# SIMILARITY SCORING WEIGHTS
# ==============================================================================

# How to weight different similarity metrics
SIMILARITY_WEIGHTS = {
    "step_count": 0.4,      # 40% weight on matching step count
    "action_text": 0.6,     # 60% weight on action text similarity
}

# ==============================================================================
# VALIDATION LEVELS
# ==============================================================================

# Different validation levels for different use cases
VALIDATION_LEVELS = {
    "strict": {
        "min_confidence": 0.8,
        "allow_warnings": False,
        "allow_format_errors": False,
        "description": "Require high confidence and no issues"
    },
    "normal": {
        "min_confidence": 0.5,
        "allow_warnings": True,
        "allow_format_errors": False,
        "description": "Standard validation - warnings OK, no format errors"
    },
    "permissive": {
        "min_confidence": 0.3,
        "allow_warnings": True,
        "allow_format_errors": False,
        "description": "Allow low confidence but not format errors"
    },
    "debug": {
        "min_confidence": 0.0,
        "allow_warnings": True,
        "allow_format_errors": True,
        "description": "No restrictions - for debugging"
    }
}

# Default validation level
DEFAULT_VALIDATION_LEVEL = "normal"

# ==============================================================================
# RECOMMENDATION TEMPLATES
# ==============================================================================

RECOMMENDATIONS = {
    "valid_high_confidence": "✓ Steps are valid and ready for execution",
    "valid_medium_confidence": "⚠️ Steps are valid but confidence is moderate. Review before execution.",
    "valid_low_confidence": "⚠️ Steps are valid but similarity is low. Consider reviewing.",
    "invalid_issues": "✗ Steps have issues. Review and regenerate if needed.",
    "invalid_format": "✗ Steps have format errors. Fix structure before execution.",
    "no_dataset_match": "⚠️ No similar instruction in dataset. Steps are generic.",
}

# ==============================================================================
# LOGGING & REPORTING
# ==============================================================================

# Enable detailed logging
ENABLE_DETAILED_LOGGING = True

# Log file path
LOG_FILE = "validation.log"

# Maximum log file size (MB) before rotation
MAX_LOG_SIZE = 10

# Number of backup log files to keep
LOG_BACKUP_COUNT = 5

# ==============================================================================
# ADVANCED OPTIONS
# ==============================================================================

# Use TF-IDF for similarity (vs other methods)
USE_TFIDF_SIMILARITY = True

# Cache dataset embeddings for faster retrieval
CACHE_EMBEDDINGS = True

# Enable step regeneration suggestions
ENABLE_REGENERATION_SUGGESTIONS = True

# Compare with multiple top matches (not just best)
TOP_K_MATCHES = 1  # Set to 3-5 to compare with multiple examples

# ==============================================================================
# VALIDATION PERFORMANCE
# ==============================================================================

# Timeout for validation (seconds)
VALIDATION_TIMEOUT = 30

# Number of threads for parallel validation (if batch processing)
MAX_THREADS = 4

# ==============================================================================
# USAGE EXAMPLES
# ==============================================================================

"""
Using Validation Configuration:

1. STRICT VALIDATION (Production)
   - High confidence required
   - No warnings allowed
   - Best for automated execution

2. NORMAL VALIDATION (Default)
   - Balanced approach
   - Warnings OK
   - Good for interactive use

3. PERMISSIVE VALIDATION (Testing)
   - Low confidence OK
   - Warnings allowed
   - Good for development

4. DEBUG VALIDATION (Development)
   - Any confidence
   - All warnings shown
   - For troubleshooting

Example:
    from demo import StepValidator
    from validation_config import VALIDATION_LEVELS
    
    validator = StepValidator()
    result = validator.validate_steps(instruction, steps, category)
    
    level = VALIDATION_LEVELS["strict"]
    if result['confidence'] >= level['min_confidence']:
        execute_steps()
    else:
        review_steps()
"""

# ==============================================================================
# CUSTOM VALIDATORS
# ==============================================================================

# Add custom validation functions here
CUSTOM_VALIDATORS = {
    # Example: "custom_rule": custom_validation_function,
}

# ==============================================================================
# ENABLE/DISABLE FEATURES
# ==============================================================================

FEATURES = {
    "format_validation": True,
    "dataset_matching": True,
    "similarity_scoring": True,
    "confidence_calculation": True,
    "category_validation": True,
    "detailed_reporting": True,
    "warning_generation": True,
}

# ==============================================================================
# DEFAULT SETTINGS
# ==============================================================================

DEFAULT_CONFIG = {
    "validation_level": DEFAULT_VALIDATION_LEVEL,
    "enable_logging": ENABLE_DETAILED_LOGGING,
    "use_cache": CACHE_EMBEDDINGS,
    "timeout": VALIDATION_TIMEOUT,
}


def get_config(level="normal"):
    """Get validation configuration for a specific level"""
    return {
        "level": level,
        "settings": VALIDATION_LEVELS.get(level, VALIDATION_LEVELS["normal"]),
        "datasets": DATASET_PATHS,
        "thresholds": CONFIDENCE_THRESHOLDS,
        "features": FEATURES,
    }


def validate_config():
    """Validate that configuration is correct"""
    errors = []
    
    # Check thresholds are in order
    if not (CONFIDENCE_THRESHOLDS["poor"] < CONFIDENCE_THRESHOLDS["fair"] < 
            CONFIDENCE_THRESHOLDS["good"] < CONFIDENCE_THRESHOLDS["excellent"] <= 1.0):
        errors.append("Confidence thresholds not in ascending order")
    
    # Check validation levels are defined
    for level in VALIDATION_LEVELS:
        if "min_confidence" not in VALIDATION_LEVELS[level]:
            errors.append(f"Validation level '{level}' missing 'min_confidence'")
    
    # Check weights sum to 1
    weight_sum = sum(SIMILARITY_WEIGHTS.values())
    if abs(weight_sum - 1.0) > 0.01:
        errors.append(f"Similarity weights must sum to 1.0, got {weight_sum}")
    
    if errors:
        print("⚠️  Configuration Validation Errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("✓ Configuration is valid")
        return True


if __name__ == "__main__":
    # Validate configuration on import
    validate_config()
    
    # Print default configuration
    print("\n📋 DEFAULT CONFIGURATION:")
    print(f"Validation Level: {DEFAULT_VALIDATION_LEVEL}")
    print(f"Min Confidence: {VALIDATION_LEVELS[DEFAULT_VALIDATION_LEVEL]['min_confidence']:.1%}")
    print(f"Allow Warnings: {VALIDATION_LEVELS[DEFAULT_VALIDATION_LEVEL]['allow_warnings']}")
    print(f"\nDatasets:")
    for key, path in DATASET_PATHS.items():
        print(f"  {key}: {path}")
