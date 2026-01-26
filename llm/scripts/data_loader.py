"""
Data Loader Module
Creates PyTorch data loaders for training and validation.
"""

import torch
from torch.utils.data import DataLoader, Dataset
from datasets import load_from_disk
from pathlib import Path
import json

class TextDataset(Dataset):
    """Custom Dataset wrapper for tokenized text data."""
    
    def __init__(self, tokenized_dataset):
        """
        Initialize dataset.
        
        Args:
            tokenized_dataset: Hugging Face dataset with tokenized texts
        """
        self.data = tokenized_dataset
        
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        """
        Get a single item from dataset.
        
        Returns:
            dict with input_ids, attention_mask, and labels as tensors
        """
        item = self.data[idx]
        
        return {
            'input_ids': torch.tensor(item['input_ids'], dtype=torch.long),
            'attention_mask': torch.tensor(item['attention_mask'], dtype=torch.long),
            'labels': torch.tensor(item['labels'], dtype=torch.long)
        }

def create_dataloaders(data_path, batch_size=8, num_workers=0, shuffle_train=True):
    """
    Create training and validation data loaders.
    
    Args:
        data_path: Path to processed dataset
        batch_size: Batch size for training
        num_workers: Number of workers for data loading
        shuffle_train: Whether to shuffle training data
        
    Returns:
        train_loader, val_loader, metadata
    """
    print("="*70)
    print("Creating Data Loaders")
    print("="*70)
    
    # Load processed dataset
    data_path = Path(data_path)
    print(f"\nLoading processed data from: {data_path}")
    
    tokenized_dataset = load_from_disk(str(data_path))
    
    # Load metadata
    metadata_path = data_path.parent / "metadata.json"
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    print(f"✓ Dataset loaded")
    print(f"  Training samples: {len(tokenized_dataset['train'])}")
    print(f"  Validation samples: {len(tokenized_dataset['validation'])}")
    
    # Create datasets
    train_dataset = TextDataset(tokenized_dataset['train'])
    val_dataset = TextDataset(tokenized_dataset['validation'])
    
    # Create data loaders
    print(f"\nCreating data loaders with batch_size={batch_size}...")
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=shuffle_train,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available()
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available()
    )
    
    print(f"✓ Data loaders created")
    print(f"  Training batches: {len(train_loader)}")
    print(f"  Validation batches: {len(val_loader)}")
    print(f"  Samples per batch: {batch_size}")
    
    return train_loader, val_loader, metadata

def test_dataloader(train_loader, val_loader, num_batches=2):
    """
    Test data loaders by fetching and displaying sample batches.
    
    Args:
        train_loader: Training data loader
        val_loader: Validation data loader
        num_batches: Number of batches to display
    """
    print("\n" + "="*70)
    print("Testing Data Loaders")
    print("="*70)
    
    # Test training loader
    print("\n--- Training Loader ---")
    for i, batch in enumerate(train_loader):
        if i >= num_batches:
            break
        
        print(f"\nBatch {i+1}:")
        print(f"  input_ids shape: {batch['input_ids'].shape}")
        print(f"  attention_mask shape: {batch['attention_mask'].shape}")
        print(f"  labels shape: {batch['labels'].shape}")
        
        # Show first sequence
        print(f"\n  First sequence (first 20 tokens):")
        print(f"    {batch['input_ids'][0][:20].tolist()}")
        
        # Statistics
        print(f"\n  Batch statistics:")
        print(f"    Total tokens: {batch['input_ids'].numel()}")
        print(f"    Active tokens (not padding): {batch['attention_mask'].sum().item()}")
        print(f"    Min token ID: {batch['input_ids'].min().item()}")
        print(f"    Max token ID: {batch['input_ids'].max().item()}")
    
    # Test validation loader
    print("\n--- Validation Loader ---")
    for i, batch in enumerate(val_loader):
        if i >= num_batches:
            break
        
        print(f"\nBatch {i+1}:")
        print(f"  input_ids shape: {batch['input_ids'].shape}")
        print(f"  attention_mask shape: {batch['attention_mask'].shape}")
        print(f"  labels shape: {batch['labels'].shape}")
    
    print("\n✓ Data loaders working correctly!")

def main():
    """Main function to test data loaders."""
    # Get data path
    data_dir = Path(__file__).parent.parent / "data" / "processed"
    
    # Check for processed datasets
    available_datasets = []
    for item in data_dir.iterdir():
        if item.is_dir() and (item / "dataset_info.json").exists():
            available_datasets.append(item.name)
    
    if not available_datasets:
        print("No processed datasets found!")
        print("Please run: python scripts/preprocess_data.py")
        return
    
    print(f"Available datasets: {available_datasets}")
    dataset_name = available_datasets[0]
    data_path = data_dir / dataset_name
    
    # Create data loaders
    train_loader, val_loader, metadata = create_dataloaders(
        data_path=data_path,
        batch_size=4,
        num_workers=0,
        shuffle_train=True
    )
    
    # Test loaders
    test_dataloader(train_loader, val_loader, num_batches=2)
    
    print("\n" + "="*70)
    print("Data Loading Pipeline Ready!")
    print("="*70)
    print(f"\nDataset: {metadata['dataset_name']}")
    print(f"Vocabulary size: {metadata['vocab_size']}")
    print(f"Max sequence length: {metadata['max_length']}")
    print(f"Training samples: {metadata['train_samples']}")
    print(f"Validation samples: {metadata['val_samples']}")

if __name__ == "__main__":
    main()
