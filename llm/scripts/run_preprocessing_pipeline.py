"""
Complete Data Preprocessing Pipeline
Runs the full pipeline: download → preprocess → create loaders → test
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from preprocess_data import DataPreprocessor
from data_loader import create_dataloaders, test_dataloader

def run_full_pipeline(dataset_name="wikitext", batch_size=8, max_length=512):
    """
    Run the complete preprocessing pipeline.
    
    Args:
        dataset_name: Name of dataset ('wikitext' or 'tiny_shakespeare')
        batch_size: Batch size for data loaders
        max_length: Maximum sequence length
    """
    print("="*70)
    print("COMPLETE DATA PREPROCESSING PIPELINE")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Dataset: {dataset_name}")
    print(f"  Batch size: {batch_size}")
    print(f"  Max sequence length: {max_length}")
    print(f"  Train/Val split: 80/20")
    
    # Step 1: Initialize preprocessor
    print("\n" + "="*70)
    print("STEP 1: Initialize Preprocessor")
    print("="*70)
    
    dataset_config = None
    if dataset_name == "wikitext":
        dataset_config = "wikitext-103-raw-v1"
    
    preprocessor = DataPreprocessor(
        dataset_name=dataset_name,
        dataset_config=dataset_config,
        max_length=max_length
    )
    
    # Step 2: Load dataset
    print("\n" + "="*70)
    print("STEP 2: Load Dataset")
    print("="*70)
    preprocessor.load_dataset()
    
    # Step 3: Tokenize
    print("\n" + "="*70)
    print("STEP 3: Tokenize Data")
    print("="*70)
    preprocessor.preprocess_dataset()
    
    # Step 4: Create train/val split
    print("\n" + "="*70)
    print("STEP 4: Create Train/Validation Split")
    print("="*70)
    preprocessor.create_train_val_split(train_ratio=0.8)
    
    # Step 5: Show samples
    print("\n" + "="*70)
    print("STEP 5: Sample Tokenized Outputs")
    print("="*70)
    preprocessor.show_samples(num_samples=3)
    
    # Step 6: Save processed data
    print("\n" + "="*70)
    print("STEP 6: Save Processed Data")
    print("="*70)
    save_path = preprocessor.save_processed_data()
    
    # Step 7: Create data loaders
    print("\n" + "="*70)
    print("STEP 7: Create Data Loaders")
    print("="*70)
    train_loader, val_loader, metadata = create_dataloaders(
        data_path=save_path,
        batch_size=batch_size,
        num_workers=0,
        shuffle_train=True
    )
    
    # Step 8: Test data loaders
    print("\n" + "="*70)
    print("STEP 8: Test Data Loaders")
    print("="*70)
    test_dataloader(train_loader, val_loader, num_batches=2)
    
    # Final summary
    print("\n" + "="*70)
    print("PIPELINE COMPLETE!")
    print("="*70)
    print("\n✓ All steps completed successfully!")
    print("\nSummary:")
    print(f"  Dataset: {metadata['dataset_name']}")
    print(f"  Vocabulary size: {metadata['vocab_size']:,}")
    print(f"  Max sequence length: {metadata['max_length']}")
    print(f"  Training samples: {metadata['train_samples']:,}")
    print(f"  Validation samples: {metadata['val_samples']:,}")
    print(f"  Training batches: {len(train_loader):,}")
    print(f"  Validation batches: {len(val_loader):,}")
    print(f"  Batch size: {batch_size}")
    
    print("\nData is ready for training!")
    print(f"Processed data location: {save_path}")
    
    return train_loader, val_loader, metadata

def main():
    """Main function with user interaction."""
    print("\n" + "="*70)
    print("Language Model Data Preprocessing Pipeline")
    print("="*70)
    
    print("\nDataset options:")
    print("1. Tiny Shakespeare (~1MB) - Quick test, downloads fast")
    print("2. WikiText-103 (~500MB) - Recommended for real training")
    
    choice = input("\nEnter choice (1-2) or press Enter for Tiny Shakespeare: ").strip()
    
    if choice == "2":
        dataset_name = "wikitext"
        print("\n⚠ WikiText-103 is ~500MB. This may take a few minutes to download.")
    else:
        dataset_name = "tiny_shakespeare"
        print("\n✓ Using Tiny Shakespeare for quick testing.")
    
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return
    
    # Run pipeline
    run_full_pipeline(
        dataset_name=dataset_name,
        batch_size=8,
        max_length=512
    )

if __name__ == "__main__":
    main()
