"""
Training Visualization
Plot training and validation loss curves.
"""

import matplotlib.pyplot as plt
import json
from pathlib import Path
import numpy as np

class TrainingVisualizer:
    """Handles visualization of training metrics."""
    
    def __init__(self, save_dir):
        """
        Initialize visualizer.
        
        Args:
            save_dir: Directory to save plots
        """
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # Training history
        self.train_losses = []
        self.val_losses = []
        self.train_steps = []
        self.val_steps = []
        self.learning_rates = []
        self.perplexities = []
        
    def add_train_loss(self, step, loss, lr):
        """Add training loss point."""
        self.train_losses.append(loss)
        self.train_steps.append(step)
        self.learning_rates.append(lr)
        self.perplexities.append(np.exp(loss))
    
    def add_val_loss(self, step, loss):
        """Add validation loss point."""
        self.val_losses.append(loss)
        self.val_steps.append(step)
    
    def plot_losses(self, show=False):
        """Plot training and validation losses."""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Training loss
        ax = axes[0, 0]
        if self.train_losses:
            ax.plot(self.train_steps, self.train_losses, label='Training Loss', alpha=0.7)
            ax.set_xlabel('Steps')
            ax.set_ylabel('Loss')
            ax.set_title('Training Loss Over Time')
            ax.grid(True, alpha=0.3)
            ax.legend()
        
        # Validation loss
        ax = axes[0, 1]
        if self.val_losses:
            ax.plot(self.val_steps, self.val_losses, 'o-', label='Validation Loss', color='orange')
            ax.set_xlabel('Steps')
            ax.set_ylabel('Loss')
            ax.set_title('Validation Loss Over Time')
            ax.grid(True, alpha=0.3)
            ax.legend()
        
        # Combined losses
        ax = axes[1, 0]
        if self.train_losses:
            ax.plot(self.train_steps, self.train_losses, label='Training', alpha=0.7)
        if self.val_losses:
            ax.plot(self.val_steps, self.val_losses, 'o-', label='Validation', color='orange')
        ax.set_xlabel('Steps')
        ax.set_ylabel('Loss')
        ax.set_title('Training vs Validation Loss')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Learning rate
        ax = axes[1, 1]
        if self.learning_rates:
            ax.plot(self.train_steps, self.learning_rates, color='green')
            ax.set_xlabel('Steps')
            ax.set_ylabel('Learning Rate')
            ax.set_title('Learning Rate Schedule')
            ax.grid(True, alpha=0.3)
            ax.set_yscale('log')
        
        plt.tight_layout()
        
        # Save
        save_path = self.save_dir / 'training_curves.png'
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"\n✓ Training curves saved to: {save_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    def plot_perplexity(self, show=False):
        """Plot perplexity curve."""
        if not self.perplexities:
            return
        
        plt.figure(figsize=(10, 6))
        plt.plot(self.train_steps, self.perplexities, alpha=0.7)
        plt.xlabel('Steps')
        plt.ylabel('Perplexity')
        plt.title('Training Perplexity Over Time')
        plt.grid(True, alpha=0.3)
        plt.yscale('log')
        
        # Save
        save_path = self.save_dir / 'perplexity_curve.png'
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✓ Perplexity curve saved to: {save_path}")
        
        if show:
            plt.show()
        else:
            plt.close()
    
    def save_history(self):
        """Save training history to JSON."""
        import torch
        
        # Convert tensors to Python types
        def to_python(val):
            if isinstance(val, torch.Tensor):
                return val.item() if val.numel() == 1 else val.tolist()
            elif isinstance(val, list):
                return [to_python(v) for v in val]
            return val
        
        history = {
            'train_steps': to_python(self.train_steps),
            'train_losses': to_python(self.train_losses),
            'val_steps': to_python(self.val_steps),
            'val_losses': to_python(self.val_losses),
            'learning_rates': to_python(self.learning_rates),
            'perplexities': to_python(self.perplexities)
        }
        
        save_path = self.save_dir / 'training_history.json'
        with open(save_path, 'w') as f:
            json.dump(history, f, indent=2)
        
        print(f"✓ Training history saved to: {save_path}")
    
    def load_history(self):
        """Load training history from JSON."""
        load_path = self.save_dir / 'training_history.json'
        
        if not load_path.exists():
            print("No training history found.")
            return
        
        with open(load_path, 'r') as f:
            history = json.load(f)
        
        self.train_steps = history.get('train_steps', [])
        self.train_losses = history.get('train_losses', [])
        self.val_steps = history.get('val_steps', [])
        self.val_losses = history.get('val_losses', [])
        self.learning_rates = history.get('learning_rates', [])
        self.perplexities = history.get('perplexities', [])
        
        print(f"✓ Training history loaded from: {load_path}")
    
    def print_summary(self):
        """Print training summary statistics."""
        print("\n" + "="*80)
        print("Training Summary")
        print("="*80)
        
        if self.train_losses:
            print(f"\nTraining Loss:")
            print(f"  Initial: {self.train_losses[0]:.4f}")
            print(f"  Final:   {self.train_losses[-1]:.4f}")
            print(f"  Best:    {min(self.train_losses):.4f}")
            print(f"  Improvement: {self.train_losses[0] - self.train_losses[-1]:.4f}")
        
        if self.val_losses:
            print(f"\nValidation Loss:")
            print(f"  Best: {min(self.val_losses):.4f}")
            best_idx = self.val_losses.index(min(self.val_losses))
            print(f"  Best at step: {self.val_steps[best_idx]}")
        
        if self.perplexities:
            print(f"\nPerplexity:")
            print(f"  Initial: {self.perplexities[0]:.2f}")
            print(f"  Final:   {self.perplexities[-1]:.2f}")
            print(f"  Best:    {min(self.perplexities):.2f}")
        
        print(f"\nTotal training steps: {len(self.train_steps)}")
        print(f"Total validation points: {len(self.val_steps)}")

def plot_from_history(history_path):
    """Load and plot training history from file."""
    visualizer = TrainingVisualizer(Path(history_path).parent)
    visualizer.load_history()
    visualizer.plot_losses(show=True)
    visualizer.plot_perplexity(show=True)
    visualizer.print_summary()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Plot from saved history
        plot_from_history(sys.argv[1])
    else:
        print("Usage: python visualize.py <path_to_training_history.json>")
        print("\nOr use within training script to track metrics automatically.")
