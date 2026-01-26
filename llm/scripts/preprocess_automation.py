"""
Preprocess Automation Dataset
Convert instruction-output pairs to tokenized training data.
"""

import json
from pathlib import Path
from datasets import Dataset
from transformers import GPT2Tokenizer
from tqdm import tqdm

def load_jsonl(file_path):
    """Load JSONL file."""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line.strip()))
    return data

def create_training_text(instruction, output):
    """Format instruction and output for training."""
    # Format: Instruction: <instruction>\nSteps: <output>
    return f"Instruction: {instruction}\nSteps: {output}"

def preprocess_automation_dataset():
    """Preprocess automation dataset for training."""
    
    print("="*80)
    print("AUTOMATION DATASET PREPROCESSING")
    print("="*80)
    
    # Paths
    base_dir = Path(__file__).parent.parent
    dataset_path = base_dir / "automation_dataset.jsonl"
    output_dir = base_dir / "data" / "processed" / "automation"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 Loading dataset from: {dataset_path}")
    
    # Load data
    data = load_jsonl(dataset_path)
    print(f"✓ Loaded {len(data)} examples")
    
    # Create training texts
    print("\n📝 Creating training texts...")
    texts = []
    for item in tqdm(data):
        text = create_training_text(item['instruction'], item['output'])
        texts.append(text)
    
    # Show samples
    print("\n📊 Sample training texts:")
    print("-" * 80)
    for i, text in enumerate(texts[:3]):
        print(f"\nSample {i+1}:")
        print(text)
        print("-" * 80)
    
    # Split train/val (90/10)
    split_idx = int(len(texts) * 0.9)
    train_texts = texts[:split_idx]
    val_texts = texts[split_idx:]
    
    print(f"\n✓ Split: {len(train_texts)} train, {len(val_texts)} validation")
    
    # Load tokenizer
    print("\n🔤 Loading GPT-2 tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
    tokenizer.pad_token = tokenizer.eos_token
    
    # Tokenize function
    def tokenize_function(examples):
        # Add EOS token to end of each example
        texts_with_eos = [text + tokenizer.eos_token for text in examples['text']]
        
        return tokenizer(
            texts_with_eos,
            truncation=True,
            max_length=256,  # Shorter sequences for automation tasks
            padding='max_length',
            return_tensors=None
        )
    
    # Create datasets
    print("\n🔄 Tokenizing training data...")
    train_dataset = Dataset.from_dict({'text': train_texts})
    train_dataset = train_dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=['text'],
        desc="Tokenizing train"
    )
    
    print("🔄 Tokenizing validation data...")
    val_dataset = Dataset.from_dict({'text': val_texts})
    val_dataset = val_dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=['text'],
        desc="Tokenizing validation"
    )
    
    # Add labels (same as input_ids for language modeling)
    def add_labels(examples):
        examples['labels'] = examples['input_ids'].copy()
        return examples
    
    train_dataset = train_dataset.map(add_labels, batched=True)
    val_dataset = val_dataset.map(add_labels, batched=True)
    
    # Save datasets as DatasetDict (compatible with data_loader)
    print(f"\n💾 Saving processed datasets to: {output_dir}")
    
    from datasets import DatasetDict
    dataset_dict = DatasetDict({
        'train': train_dataset,
        'validation': val_dataset
    })
    dataset_dict.save_to_disk(output_dir)
    
    # Save metadata
    metadata = {
        'dataset_name': 'automation_steps',
        'num_train_samples': len(train_dataset),
        'num_val_samples': len(val_dataset),
        'vocab_size': tokenizer.vocab_size,
        'max_seq_len': 256,
        'tokenizer': 'gpt2'
    }
    
    with open(output_dir / 'metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("\n" + "="*80)
    print("PREPROCESSING COMPLETE!")
    print("="*80)
    print(f"✓ Training samples: {len(train_dataset)}")
    print(f"✓ Validation samples: {len(val_dataset)}")
    print(f"✓ Vocabulary size: {tokenizer.vocab_size}")
    print(f"✓ Max sequence length: 256")
    print(f"\n📂 Data saved in: {output_dir}")
    print("\n🚀 Ready to train! Run: python scripts/train_automation.py")

if __name__ == "__main__":
    preprocess_automation_dataset()
