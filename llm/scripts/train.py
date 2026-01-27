"""
Training Script
Train GPT model with mixed precision and gradient checkpointing.
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.cuda.amp import autocast, GradScaler
from pathlib import Path
import json
import time
from tqdm import tqdm

from model import GPTModel
from config import get_config
from data_loader import create_dataloaders
from visualize import TrainingVisualizer

class Trainer:
    """Handles model training with optimizations."""
    
    def __init__(self, model, config, train_loader, val_loader, device):
        """
        Initialize trainer.
        
        Args:
            model: GPT model
            config: Model configuration
            train_loader: Training data loader
            val_loader: Validation data loader
            device: Device to train on
        """
        self.model = model.to(device)
        self.config = config
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        
        # Setup optimizer (AdamW with weight decay)
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
            betas=(0.9, 0.95),  # GPT-3 style
            eps=1e-8
        )
        
        # Learning rate scheduler with warmup
        self.scheduler = self._get_lr_scheduler()
        
        # Mixed precision scaler
        self.scaler = GradScaler() if config.use_mixed_precision else None
        
        # Training state
        self.global_step = 0
        self.epoch = 0
        self.best_val_loss = float('inf')
        
        # Create save directory
        self.save_dir = Path(__file__).parent.parent / "models" / "checkpoints"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize visualizer
        self.visualizer = TrainingVisualizer(self.save_dir)
        
        print(f"\n✓ Trainer initialized")
        print(f"  Device: {device}")
        print(f"  Mixed precision: {config.use_mixed_precision}")
        print(f"  Gradient checkpointing: {config.use_gradient_checkpointing}")
        print(f"  Gradient accumulation steps: {config.gradient_accumulation_steps}")
    
    def _get_lr_scheduler(self):
        """Create learning rate scheduler with warmup."""
        from torch.optim.lr_scheduler import LambdaLR
        
        def lr_lambda(step):
            if step < self.config.warmup_steps:
                # Linear warmup
                return step / max(1, self.config.warmup_steps)
            else:
                # Cosine decay
                progress = (step - self.config.warmup_steps) / max(1, (
                    len(self.train_loader) * self.config.max_epochs - self.config.warmup_steps
                ))
                return 0.5 * (1.0 + torch.cos(torch.tensor(progress * 3.14159)))
        
        return LambdaLR(self.optimizer, lr_lambda)
    
    def train_epoch(self):
        """Train for one epoch."""
        self.model.train()
        total_loss = 0
        num_batches = 0
        
        progress_bar = tqdm(self.train_loader, desc=f"Epoch {self.epoch+1}")
        
        for batch_idx, batch in enumerate(progress_bar):
            # Move batch to device
            input_ids = batch['input_ids'].to(self.device)
            attention_mask = batch['attention_mask'].to(self.device)
            labels = batch['labels'].to(self.device)
            
            # Forward pass with mixed precision
            if self.config.use_mixed_precision:
                with autocast():
                    loss, _ = self.model(input_ids, attention_mask, labels)
                    loss = loss / self.config.gradient_accumulation_steps
            else:
                loss, _ = self.model(input_ids, attention_mask, labels)
                loss = loss / self.config.gradient_accumulation_steps
            
            # Backward pass
            if self.config.use_mixed_precision:
                self.scaler.scale(loss).backward()
            else:
                loss.backward()
            
            # Update weights (with gradient accumulation)
            if (batch_idx + 1) % self.config.gradient_accumulation_steps == 0:
                # Gradient clipping
                if self.config.use_mixed_precision:
                    self.scaler.unscale_(self.optimizer)
                
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config.max_grad_norm
                )
                
                # Optimizer step
                if self.config.use_mixed_precision:
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
                    self.optimizer.step()
                
                self.scheduler.step()
                self.optimizer.zero_grad()
                
                self.global_step += 1
            
            # Update metrics
            total_loss += loss.item() * self.config.gradient_accumulation_steps
            num_batches += 1
            
            # Update progress bar
            avg_loss = total_loss / num_batches
            current_lr = self.scheduler.get_last_lr()[0]
            progress_bar.set_postfix({
                'loss': f'{avg_loss:.4f}',
                'lr': f'{current_lr:.2e}',
                'step': self.global_step
            })
            
            # Logging
            if self.global_step % self.config.log_interval == 0:
                self._log_metrics(avg_loss)
                # Track for visualization
                self.visualizer.add_train_loss(self.global_step, avg_loss, current_lr)
            
            # Validation
            if self.global_step % self.config.eval_interval == 0:
                val_loss = self.validate()
                
                # Track validation loss
                self.visualizer.add_val_loss(self.global_step, val_loss)
                
                # Save if best
                if val_loss < self.best_val_loss:
                    self.best_val_loss = val_loss
                    self.save_checkpoint('best_model.pt')
                    print(f"✓ New best model! Validation loss: {val_loss:.4f}")
                
                # Save visualization
                self.visualizer.plot_losses()
                self.visualizer.save_history()
            
            # Save checkpoint
            if self.global_step % self.config.save_interval == 0:
                self.save_checkpoint(f'checkpoint_step_{self.global_step}.pt')
                print(f"✓ Checkpoint saved at step {self.global_step}")
        
        return total_loss / num_batches
    
    def validate(self):
        """Validate on validation set."""
        self.model.eval()
        total_loss = 0
        num_batches = 0
        
        print("\nValidating...")
        
        with torch.no_grad():
            for batch in tqdm(self.val_loader, desc="Validation"):
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                labels = batch['labels'].to(self.device)
                
                if self.config.use_mixed_precision:
                    with autocast():
                        loss, _ = self.model(input_ids, attention_mask, labels)
                else:
                    loss, _ = self.model(input_ids, attention_mask, labels)
                
                total_loss += loss.item()
                num_batches += 1
        
        avg_loss = total_loss / num_batches
        perplexity = torch.exp(torch.tensor(avg_loss))
        
        print(f"Validation Loss: {avg_loss:.4f} | Perplexity: {perplexity:.2f}")
        
        return avg_loss
    
    def _log_metrics(self, loss):
        """Log training metrics."""
        perplexity = torch.exp(torch.tensor(loss))
        lr = self.scheduler.get_last_lr()[0]
        
        print(f"\nStep {self.global_step} | Loss: {loss:.4f} | "
              f"Perplexity: {perplexity:.2f} | LR: {lr:.2e}")
    
    def save_checkpoint(self, filename):
        """Save model checkpoint."""
        checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'global_step': self.global_step,
            'epoch': self.epoch,
            'best_val_loss': self.best_val_loss,
            'config': self.config.__dict__
        }
        
        if self.scaler is not None:
            checkpoint['scaler_state_dict'] = self.scaler.state_dict()
        
        save_path = self.save_dir / filename
        torch.save(checkpoint, save_path)
        print(f"\n✓ Checkpoint saved: {save_path}")
    
    def load_checkpoint(self, checkpoint_path):
        """Load checkpoint to resume training."""
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
        
        self.global_step = checkpoint['global_step']
        self.epoch = checkpoint['epoch']
        self.best_val_loss = checkpoint['best_val_loss']
        self.current_epoch = self.epoch  # Set starting epoch
        
        if self.scaler is not None and 'scaler_state_dict' in checkpoint:
            self.scaler.load_state_dict(checkpoint['scaler_state_dict'])
        
        print(f"✓ Checkpoint loaded from: {checkpoint_path}")
        print(f"  Resuming from epoch: {self.epoch}")
        print(f"  Global step: {self.global_step}")
        print(f"  Best validation loss: {self.best_val_loss:.4f}")
    
    def train(self):
        """Main training loop."""
        print("\n" + "="*80)
        print("Starting Training")
        print("="*80)
        
        start_time = time.time()
        
        # Start from current_epoch (0 if fresh, or loaded epoch if resumed)
        start_epoch = getattr(self, 'current_epoch', 0)
        
        for epoch in range(start_epoch, self.config.max_epochs):
            self.epoch = epoch
            
            print(f"\n{'='*80}")
            print(f"Epoch {epoch + 1}/{self.config.max_epochs}")
            print(f"{'='*80}")
            
            train_loss = self.train_epoch()
            
            print(f"\nEpoch {epoch + 1} completed")
            print(f"  Average train loss: {train_loss:.4f}")
            
            # Save epoch checkpoint
            self.save_checkpoint(f'checkpoint_epoch_{epoch+1}.pt')
        
        total_time = time.time() - start_time
        
        # Final visualization
        print("\nGenerating final visualizations...")
        self.visualizer.plot_losses()
        self.visualizer.plot_perplexity()
        self.visualizer.save_history()
        self.visualizer.print_summary()
        
        print("\n" + "="*80)
        print("Training Complete!")
        print("="*80)
        print(f"Total time: {total_time/3600:.2f} hours")
        print(f"Best validation loss: {self.best_val_loss:.4f}")
        print(f"Checkpoints saved in: {self.save_dir}")
        print(f"Visualizations saved in: {self.save_dir}")

def main():
    """Main training function."""
    print("="*80)
    print("GPT MODEL TRAINING")
    print("="*80)
    
    # Get configuration
    print("\nModel size options:")
    print("1. Small (~40M parameters) - Fast training, good for testing")
    print("2. Medium (~124M parameters) - Recommended for most GPUs")
    print("3. Large (~200M parameters) - Requires powerful GPU")
    
    choice = input("\nEnter choice (1-3) or press Enter for Medium: ").strip()
    
    size_map = {'1': 'small', '2': 'medium', '3': 'large'}
    size = size_map.get(choice, 'medium')
    
    config = get_config(size)
    
    print(f"\n✓ Using {size.capitalize()} model configuration")
    
    # Setup device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"✓ Using device: {device}")
    
    if device.type == 'cpu':
        print("\n⚠ WARNING: Training on CPU will be very slow!")
        print("  Consider using GPU or reducing model size.")
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
    print(f"  Trainable parameters: {trainable_params:,}")
    
    # Create trainer
    trainer = Trainer(model, config, train_loader, val_loader, device)
    
    # Confirm start
    print("\nReady to start training!")
    confirm = input("Start training? (y/n): ").strip().lower()
    
    if confirm == 'y':
        trainer.train()
    else:
        print("Training cancelled.")

if __name__ == "__main__":
    main()
