"""
Quick Training Script
Run a small training session to test the pipeline.
"""

import torch
from pathlib import Path

from model import GPTModel
from config import ModelConfig
from data_loader import create_dataloaders
from train import Trainer

def quick_train():
    """Run a quick training session for testing."""
    print("="*80)
    print("QUICK TRAINING SESSION")
    print("="*80)
    print("\nThis will train a small model for a few steps to test the pipeline.")
    
    # Custom config for quick training
    config = ModelConfig(
        # Small model
        vocab_size=50257,
        max_seq_len=512,
        hidden_dim=384,
        num_layers=6,
        num_heads=6,
        ffn_dim=1536,
        
        # Quick training settings
        batch_size=4,
        learning_rate=3e-4,
        max_epochs=1,  # Just 1 epoch for testing
        warmup_steps=50,
        
        # Frequent logging/saving
        log_interval=10,
        eval_interval=100,
        save_interval=100,
        
        # Optimizations
        use_mixed_precision=True,
        use_gradient_checkpointing=True,
        gradient_accumulation_steps=2
    )
    
    print("\nConfiguration:")
    print(f"  Model size: Small (30M parameters)")
    print(f"  Batch size: {config.batch_size}")
    print(f"  Epochs: {config.max_epochs}")
    print(f"  Mixed precision: {config.use_mixed_precision}")
    print(f"  Gradient checkpointing: {config.use_gradient_checkpointing}")
    
    # Setup device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\nDevice: {device}")
    
    if device.type == 'cpu':
        print("\n⚠ Training on CPU - this will be slow!")
        config.use_mixed_precision = False
    
    # Load data
    data_dir = Path(__file__).parent.parent / "data" / "processed" / "wikitext"
    
    if not data_dir.exists():
        print("\n✗ Processed data not found!")
        print("Please run: python scripts/run_preprocessing_pipeline.py")
        return
    
    print("\nLoading data...")
    train_loader, val_loader, metadata = create_dataloaders(
        data_path=data_dir,
        batch_size=config.batch_size,
        num_workers=0
    )
    
    # Create model
    print("\nInitializing model...")
    model = GPTModel(
        vocab_size=config.vocab_size,
        max_seq_len=config.max_seq_len,
        hidden_dim=config.hidden_dim,
        num_layers=config.num_layers,
        num_heads=config.num_heads,
        ffn_dim=config.ffn_dim,
        dropout=config.dropout,
        use_gradient_checkpointing=config.use_gradient_checkpointing
    )
    
    total_params, trainable_params = model.count_parameters()
    print(f"✓ Model created")
    print(f"  Total parameters: {total_params:,}")
    
    # Create trainer
    trainer = Trainer(model, config, train_loader, val_loader, device)
    
    # Start training
    print("\n" + "="*80)
    print("Starting Quick Training...")
    print("="*80)
    print("\nThis will:")
    print("  - Train for 1 epoch")
    print("  - Log metrics every 10 steps")
    print("  - Validate every 100 steps")
    print("  - Save checkpoints every 100 steps")
    print("  - Generate loss curves")
    
    confirm = input("\nStart? (y/n): ").strip().lower()
    
    if confirm == 'y':
        trainer.train()
        
        print("\n" + "="*80)
        print("Quick Training Complete!")
        print("="*80)
        print(f"\nCheck the results:")
        print(f"  Checkpoints: {trainer.save_dir}")
        print(f"  Loss curves: {trainer.save_dir / 'training_curves.png'}")
        print(f"  Training history: {trainer.save_dir / 'training_history.json'}")
    else:
        print("Cancelled.")

if __name__ == "__main__":
    quick_train()
