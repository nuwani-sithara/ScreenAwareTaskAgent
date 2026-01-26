"""
Data Preprocessing Script
Tokenizes text data using GPT-2 tokenizer and prepares it for training.
"""

import os
import json
import numpy as np
from pathlib import Path
from datasets import load_dataset
from transformers import GPT2Tokenizer
from tqdm import tqdm

class DataPreprocessor:
    """Handles data preprocessing and tokenization."""
    
    def __init__(self, dataset_name="wikitext", dataset_config="wikitext-103-raw-v1", 
                 max_length=512, cache_dir=None):
        """
        Initialize preprocessor.
        
        Args:
            dataset_name: Name of dataset to load
            dataset_config: Configuration of dataset
            max_length: Maximum sequence length for tokenization
            cache_dir: Directory to cache processed data
        """
        self.dataset_name = dataset_name
        self.dataset_config = dataset_config
        self.max_length = max_length
        self.cache_dir = cache_dir or Path(__file__).parent.parent / "data" / "processed"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize GPT-2 tokenizer
        print("Loading GPT-2 tokenizer...")
        self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
        # GPT-2 doesn't have a pad token by default, so we set it to eos_token
        self.tokenizer.pad_token = self.tokenizer.eos_token
        print(f"✓ Tokenizer loaded")
        print(f"  Vocabulary size: {len(self.tokenizer)}")
        print(f"  Max length: {self.max_length}")
        
    def load_dataset(self):
        """Load the dataset."""
        print(f"\nLoading dataset: {self.dataset_name}...")
        
        if self.dataset_name == "wikitext":
            self.dataset = load_dataset(self.dataset_name, self.dataset_config)
        elif self.dataset_name == "tiny_shakespeare":
            self.dataset = load_dataset(self.dataset_name)
        else:
            self.dataset = load_dataset(self.dataset_name)
        
        print("✓ Dataset loaded")
        print(f"  Train samples: {len(self.dataset['train'])}")
        if 'validation' in self.dataset:
            print(f"  Validation samples: {len(self.dataset['validation'])}")
        if 'test' in self.dataset:
            print(f"  Test samples: {len(self.dataset['test'])}")
        
        return self.dataset
    
    def tokenize_function(self, examples):
        """Tokenize a batch of examples."""
        # Tokenize the texts
        tokenized = self.tokenizer(
            examples['text'],
            truncation=True,
            max_length=self.max_length,
            padding='max_length',
            return_tensors=None  # Return lists, not tensors
        )
        
        # For causal language modeling, labels are the same as input_ids
        tokenized['labels'] = tokenized['input_ids'].copy()
        
        return tokenized
    
    def preprocess_dataset(self):
        """Preprocess and tokenize the entire dataset."""
        print("\n" + "="*70)
        print("Tokenizing Dataset")
        print("="*70)
        
        # Remove empty texts
        print("\nFiltering empty texts...")
        self.dataset = self.dataset.filter(
            lambda x: x['text'] is not None and len(x['text'].strip()) > 0
        )
        
        # Tokenize
        print("\nTokenizing texts...")
        self.tokenized_dataset = self.dataset.map(
            self.tokenize_function,
            batched=True,
            remove_columns=self.dataset['train'].column_names,
            desc="Tokenizing"
        )
        
        print("\n✓ Tokenization complete!")
        
        return self.tokenized_dataset
    
    def create_train_val_split(self, train_ratio=0.8):
        """
        Split training data into train/validation if no validation set exists.
        
        Args:
            train_ratio: Ratio of data to use for training (0.8 = 80%)
        """
        if 'validation' not in self.tokenized_dataset:
            print(f"\nCreating {train_ratio:.0%}/{1-train_ratio:.0%} train/validation split...")
            
            split_dataset = self.tokenized_dataset['train'].train_test_split(
                test_size=1-train_ratio,
                seed=42
            )
            
            self.tokenized_dataset['train'] = split_dataset['train']
            self.tokenized_dataset['validation'] = split_dataset['test']
            
            print(f"✓ Split created")
            print(f"  Training samples: {len(self.tokenized_dataset['train'])}")
            print(f"  Validation samples: {len(self.tokenized_dataset['validation'])}")
        else:
            print("\n✓ Using existing validation split")
        
        return self.tokenized_dataset
    
    def save_processed_data(self):
        """Save processed data to disk."""
        print("\n" + "="*70)
        print("Saving Processed Data")
        print("="*70)
        
        save_path = self.cache_dir / self.dataset_name
        
        print(f"\nSaving to: {save_path}")
        self.tokenized_dataset.save_to_disk(str(save_path))
        
        # Save tokenizer
        tokenizer_path = self.cache_dir / "tokenizer"
        self.tokenizer.save_pretrained(str(tokenizer_path))
        
        # Save metadata
        metadata = {
            'dataset_name': self.dataset_name,
            'dataset_config': self.dataset_config,
            'max_length': self.max_length,
            'vocab_size': len(self.tokenizer),
            'train_samples': len(self.tokenized_dataset['train']),
            'val_samples': len(self.tokenized_dataset.get('validation', [])),
            'splits': list(self.tokenized_dataset.keys())
        }
        
        metadata_path = self.cache_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✓ Data saved successfully!")
        print(f"  Dataset: {save_path}")
        print(f"  Tokenizer: {tokenizer_path}")
        print(f"  Metadata: {metadata_path}")
        
        return save_path
    
    def show_samples(self, num_samples=3):
        """Display sample tokenized outputs."""
        print("\n" + "="*70)
        print("Sample Tokenized Outputs")
        print("="*70)
        
        for i in range(min(num_samples, len(self.tokenized_dataset['train']))):
            print(f"\n--- Sample {i+1} ---")
            
            # Get tokenized sample
            sample = self.tokenized_dataset['train'][i]
            input_ids = sample['input_ids'][:50]  # Show first 50 tokens
            
            # Decode back to text
            decoded_text = self.tokenizer.decode(input_ids, skip_special_tokens=False)
            
            print(f"Token IDs (first 50): {input_ids}")
            print(f"\nDecoded text:")
            print(f"{decoded_text}")
            print(f"\nSequence length: {len(sample['input_ids'])}")
            print(f"Attention mask sum: {sum(sample['attention_mask'])}")

def main():
    """Main preprocessing pipeline."""
    print("="*70)
    print("Language Model Data Preprocessing Pipeline")
    print("="*70)
    
    # Choose dataset
    print("\nDataset options:")
    print("1. WikiText-103 (Recommended, ~500MB)")
    print("2. Tiny Shakespeare (~1MB, quick test)")
    
    choice = input("\nEnter choice (1-2) or press Enter for WikiText: ").strip()
    
    if choice == "2":
        dataset_name = "tiny_shakespeare"
        dataset_config = None
    else:
        dataset_name = "wikitext"
        dataset_config = "wikitext-103-raw-v1"
    
    # Initialize preprocessor
    preprocessor = DataPreprocessor(
        dataset_name=dataset_name,
        dataset_config=dataset_config,
        max_length=512
    )
    
    # Load and process
    preprocessor.load_dataset()
    preprocessor.preprocess_dataset()
    preprocessor.create_train_val_split(train_ratio=0.8)
    
    # Show samples
    preprocessor.show_samples(num_samples=3)
    
    # Save
    preprocessor.save_processed_data()
    
    print("\n" + "="*70)
    print("Preprocessing Complete!")
    print("="*70)
    print("\nNext steps:")
    print("1. Review the samples above to verify tokenization")
    print("2. Run data loader test: python scripts/test_dataloader.py")
    print("3. Start training with the processed data")

if __name__ == "__main__":
    main()
