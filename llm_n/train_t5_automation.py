"""Fine-tune T5 model on automation dataset"""
import json
from transformers import T5Tokenizer, T5ForConditionalGeneration, Trainer, TrainingArguments
from datasets import Dataset
import torch

# Load automation data (using combined dataset for better performance)
print("Loading combined dataset...")
data = [json.loads(line) for line in open('combined_dataset.jsonl')]
print(f"OK Loaded {len(data)} examples (merged from llm + llm_n)")

# Format for T5
formatted_data = []
for item in data:
    formatted_data.append({
        'input': f"generate automation steps: {item['instruction']}",
        'output': item['output']
    })

# Create dataset
dataset = Dataset.from_list(formatted_data)
split = dataset.train_test_split(test_size=0.1)
train_dataset = split['train']
val_dataset = split['test']

print(f"OK Train: {len(train_dataset)}, Val: {len(val_dataset)}")

# Load T5 model
print("\nLoading T5 model...")
model_name = "t5-small"  # Or use your existing model: "../llm/fine_tuned_js_model/checkpoint-3"
tokenizer = T5Tokenizer.from_pretrained(model_name)
model = T5ForConditionalGeneration.from_pretrained(model_name)

# Tokenize function
def tokenize_function(examples):
    inputs = tokenizer(examples['input'], padding='max_length', truncation=True, max_length=128)
    labels = tokenizer(examples['output'], padding='max_length', truncation=True, max_length=256)
    inputs['labels'] = labels['input_ids']
    return inputs

print("Tokenizing...")
train_dataset = train_dataset.map(tokenize_function, batched=True)
val_dataset = val_dataset.map(tokenize_function, batched=True)

# Training arguments
training_args = TrainingArguments(
    output_dir='./models/t5_automation',
    num_train_epochs=10,
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,
    warmup_steps=50,
    learning_rate=3e-4,
    logging_steps=10,
    eval_strategy='epoch',
    save_strategy='epoch',
    load_best_model_at_end=True,
)

# Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
)

print("\n" + "="*80)
print("STARTING T5 FINE-TUNING")
print("="*80)
print(f"This will train T5 on {len(train_dataset)} automation examples")
print("Expected time: ~20-30 minutes on CPU")
print("="*80)

response = input("\nStart training? (y/n): ")
if response.lower() == 'y':
    trainer.train()
    
    # Save
    model.save_pretrained('./models/t5_automation/best')
    tokenizer.save_pretrained('./models/t5_automation/best')
    print("\nOK Model saved to: ./models/t5_automation/best")
    print("\nTest with: .\\venv\\Scripts\\python.exe test_t5_automation.py")
else:
    print("Training cancelled")
