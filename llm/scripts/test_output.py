"""Quick test of generation"""
import torch
from generate import load_model

print("Loading model...")
model, tokenizer, config = load_model('models/checkpoints/test_model.pt')

print("\nTesting model output...")
input_ids = torch.tensor([[1, 2, 3]])
output = model(input_ids)

print(f"Output type: {type(output)}")
if isinstance(output, tuple):
    print(f"Tuple length: {len(output)}")
    print(f"First element shape: {output[0].shape}")
else:
    print(f"Tensor shape: {output.shape}")

print("\n✓ Test complete")
