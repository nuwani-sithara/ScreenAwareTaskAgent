"""
Dataset Download Script
Downloads and prepares text datasets for language model training.
"""

import os
from datasets import load_dataset
from pathlib import Path

def download_wikitext():
    """Download WikiText-103 dataset (~500MB, good for language modeling)."""
    print("="*70)
    print("Downloading WikiText-103 Dataset")
    print("="*70)
    print("Size: ~500MB")
    print("Contains: Wikipedia articles")
    print("Good for: Language model pre-training")
    print()
    
    # Download dataset
    print("Downloading dataset...")
    dataset = load_dataset("wikitext", "wikitext-103-raw-v1")
    
    print("\n✓ Dataset downloaded successfully!")
    print("\nDataset structure:")
    print(f"  Train split: {len(dataset['train'])} samples")
    print(f"  Validation split: {len(dataset['validation'])} samples")
    print(f"  Test split: {len(dataset['test'])} samples")
    
    # Show sample
    print("\nSample text (first 500 characters):")
    print("-"*70)
    sample_text = dataset['train'][0]['text'][:500]
    print(sample_text)
    print("-"*70)
    
    return dataset

def download_bookcorpus_sample():
    """Download a sample of books dataset."""
    print("="*70)
    print("Downloading BookCorpus Sample")
    print("="*70)
    
    # Note: Full BookCorpus is large, using smaller alternative
    print("Using OpenWebText instead (open source alternative)")
    print("Size: ~38GB (we'll use a subset)")
    
    dataset = load_dataset("openwebtext", split="train[:10000]")  # Small subset
    
    print("\n✓ Dataset sample downloaded!")
    print(f"  Samples: {len(dataset)}")
    
    return dataset

def download_tiny_shakespeare():
    """Download Tiny Shakespeare dataset (~1MB, good for quick testing)."""
    print("="*70)
    print("Downloading Tiny Shakespeare Dataset")
    print("="*70)
    print("Size: ~1MB")
    print("Contains: Complete works of Shakespeare")
    print("Good for: Quick testing and experimentation")
    print()
    
    dataset = load_dataset("tiny_shakespeare")
    
    print("\n✓ Dataset downloaded successfully!")
    print(f"  Train split: {len(dataset['train'])} samples")
    print(f"  Validation split: {len(dataset['validation'])} samples")
    print(f"  Test split: {len(dataset['test'])} samples")
    
    return dataset

def main():
    """Main download function."""
    print("\n" + "="*70)
    print("Dataset Download Options")
    print("="*70)
    print("\n1. WikiText-103 (Recommended, ~500MB)")
    print("   - Wikipedia articles, good quality")
    print("   - Standard benchmark for language models")
    print("\n2. Tiny Shakespeare (~1MB)")
    print("   - Quick download for testing")
    print("   - Shakespeare's complete works")
    print("\n3. OpenWebText Sample (~100MB)")
    print("   - Web text, diverse content")
    print("   - 10,000 documents subset")
    
    choice = input("\nEnter choice (1-3) or press Enter for WikiText-103: ").strip()
    
    if choice == "2":
        dataset = download_tiny_shakespeare()
    elif choice == "3":
        dataset = download_bookcorpus_sample()
    else:
        dataset = download_wikitext()
    
    # Save dataset info
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    info_file = data_dir / "dataset_info.txt"
    with open(info_file, "w", encoding="utf-8") as f:
        f.write(f"Dataset downloaded successfully\n")
        f.write(f"Type: {type(dataset)}\n")
        f.write(f"Splits: {list(dataset.keys()) if isinstance(dataset, dict) else 'single split'}\n")
    
    print(f"\n✓ Dataset info saved to: {info_file}")
    print("\nNext step: Run preprocessing script")
    print("  python scripts/preprocess_data.py")
    
    return dataset

if __name__ == "__main__":
    dataset = main()
