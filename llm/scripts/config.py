"""
Model Configuration
Defines model hyperparameters and training configuration.
"""

from dataclasses import dataclass

@dataclass
class ModelConfig:
    """GPT model configuration."""
    
    # Model architecture
    vocab_size: int = 50257  # GPT-2 tokenizer vocab size
    max_seq_len: int = 512
    hidden_dim: int = 768
    num_layers: int = 12
    num_heads: int = 12
    ffn_dim: int = 3072  # 4 * hidden_dim
    dropout: float = 0.1
    
    # Training
    batch_size: int = 8
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    max_epochs: int = 3  # Changed to 2-3 epochs
    warmup_steps: int = 500
    max_grad_norm: float = 1.0
    
    # Optimization
    use_mixed_precision: bool = True
    use_gradient_checkpointing: bool = True
    gradient_accumulation_steps: int = 4
    
    # Logging
    log_interval: int = 50  # More frequent logging
    eval_interval: int = 500  # More frequent validation
    save_interval: int = 500  # Checkpoint every 500 steps
    
    def __post_init__(self):
        """Validate configuration."""
        assert self.hidden_dim % self.num_heads == 0, \
            "hidden_dim must be divisible by num_heads"
        assert self.ffn_dim == 4 * self.hidden_dim, \
            "ffn_dim should be 4 * hidden_dim for standard GPT architecture"

@dataclass
class SmallModelConfig(ModelConfig):
    """Smaller model for testing (fewer parameters)."""
    hidden_dim: int = 384
    num_layers: int = 6
    num_heads: int = 6
    ffn_dim: int = 1536

@dataclass
class MediumModelConfig(ModelConfig):
    """Medium model (~100-150M parameters)."""
    hidden_dim: int = 768
    num_layers: int = 12
    num_heads: int = 12
    ffn_dim: int = 3072

@dataclass
class LargeModelConfig(ModelConfig):
    """Larger model (~200M parameters)."""
    hidden_dim: int = 1024
    num_layers: int = 12
    num_heads: int = 16
    ffn_dim: int = 4096

def get_config(size='medium'):
    """
    Get model configuration by size.
    
    Args:
        size: 'small', 'medium', or 'large'
        
    Returns:
        ModelConfig instance
    """
    configs = {
        'small': SmallModelConfig(),
        'medium': MediumModelConfig(),
        'large': LargeModelConfig()
    }
    
    return configs.get(size, MediumModelConfig())
