"""
Test GUI Application
Test the GUI with a randomly initialized model (no training needed).
"""

import torch
from transformers import GPT2Tokenizer
from pathlib import Path
import sys

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from model import GPTModel
from config import get_config
from generate import TextGenerator

def create_test_model():
    """Create a randomly initialized model for GUI testing."""
    print("Creating test model (randomly initialized, not trained)...")
    
    # Use small config for testing
    config = get_config('small')
    
    # Create model
    model = GPTModel(
        vocab_size=config.vocab_size,
        max_seq_len=config.max_seq_len,
        hidden_dim=config.hidden_dim,
        num_layers=config.num_layers,
        num_heads=config.num_heads,
        ffn_dim=config.ffn_dim,
        dropout=config.dropout,
        use_gradient_checkpointing=False
    )
    
    # Load tokenizer
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
    tokenizer.pad_token = tokenizer.eos_token
    
    # Create test checkpoint
    checkpoint_dir = Path(__file__).parent.parent / "models" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    checkpoint_path = checkpoint_dir / "test_model.pt"
    
    checkpoint = {
        'model_state_dict': model.state_dict(),
        'config': config.__dict__,
        'epoch': 0,
        'global_step': 0,
        'best_val_loss': float('inf')
    }
    
    torch.save(checkpoint, checkpoint_path)
    
    print(f"✓ Test model saved to: {checkpoint_path}")
    print(f"  Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print("\nNOTE: This is a randomly initialized model (not trained).")
    print("      Generated text will be random/nonsensical.")
    print("      Use this only to test the GUI functionality.")
    print(f"\nYou can load this checkpoint in the GUI: {checkpoint_path}")
    
    return checkpoint_path

def test_generation():
    """Test text generation with the test model."""
    checkpoint_path = create_test_model()
    
    print("\n" + "="*80)
    print("Testing text generation...")
    print("="*80)
    
    from generate import load_model
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model, tokenizer, config = load_model(checkpoint_path, device)
    
    generator = TextGenerator(model, tokenizer, device)
    
    prompt = "Once upon a time"
    print(f"\nPrompt: {prompt}")
    print("\nGenerating (this will be random since model is not trained)...\n")
    
    # Generate with callback for real-time display
    def callback(text, token_id):
        print(f"\rTokens: {len(text.split())}", end='', flush=True)
    
    text = generator.generate(
        prompt,
        max_length=50,
        temperature=0.8,
        top_k=50,
        top_p=0.9,
        callback=callback
    )
    
    print("\n\n" + "="*80)
    print("Generated Text:")
    print("="*80)
    print(text)
    print("="*80)
    
    print("\n✓ Generation test complete!")
    print(f"\nTo test the GUI, run: python scripts\\gui_app.py")
    print(f"Then load checkpoint: {checkpoint_path}")

if __name__ == "__main__":
    test_generation()
