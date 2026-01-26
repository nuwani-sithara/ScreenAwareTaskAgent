"""
Model Summary and Analysis
Display model architecture, parameters, and memory requirements.
"""

import torch
from model import GPTModel
from config import get_config
from pathlib import Path

def count_parameters(model):
    """
    Count model parameters.
    
    Returns:
        total_params, trainable_params, tied_params
    """
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    # Count tied parameters (embeddings tied to output layer)
    tied_params = model.token_embedding.weight.numel()
    
    return total_params, trainable_params, tied_params

def get_model_size(model):
    """Calculate model size in MB."""
    param_size = 0
    for param in model.parameters():
        param_size += param.numel() * param.element_size()
    
    buffer_size = 0
    for buffer in model.buffers():
        buffer_size += buffer.numel() * buffer.element_size()
    
    size_mb = (param_size + buffer_size) / 1024**2
    return size_mb

def print_layer_summary(model):
    """Print detailed layer-wise parameter breakdown."""
    print("\n" + "="*80)
    print("Layer-wise Parameter Breakdown")
    print("="*80)
    
    total = 0
    
    # Embeddings
    token_emb_params = model.token_embedding.weight.numel()
    pos_emb_params = model.position_embedding.weight.numel()
    
    print(f"\nEmbedding Layers:")
    print(f"  Token Embeddings:    {token_emb_params:>15,} parameters")
    print(f"  Position Embeddings: {pos_emb_params:>15,} parameters")
    emb_total = token_emb_params + pos_emb_params
    print(f"  Subtotal:            {emb_total:>15,} parameters")
    total += emb_total
    
    # Transformer blocks
    print(f"\nTransformer Blocks ({model.num_layers} layers):")
    
    block = model.blocks[0]
    
    # Attention
    attn_params = sum(p.numel() for p in block.attention.parameters())
    print(f"  Multi-Head Attention (per layer): {attn_params:>12,} parameters")
    
    # FFN
    ffn_params = sum(p.numel() for p in block.ffn.parameters())
    print(f"  Feed-Forward (per layer):         {ffn_params:>12,} parameters")
    
    # Layer norm
    ln1_params = sum(p.numel() for p in block.norm1.parameters())
    ln2_params = sum(p.numel() for p in block.norm2.parameters())
    ln_params = ln1_params + ln2_params
    print(f"  Layer Norms (per layer):          {ln_params:>12,} parameters")
    
    block_params = attn_params + ffn_params + ln_params
    print(f"  Per Block Total:                  {block_params:>12,} parameters")
    
    all_blocks = block_params * model.num_layers
    print(f"  All Blocks Total:                 {all_blocks:>12,} parameters")
    total += all_blocks
    
    # Final layer norm
    final_ln_params = sum(p.numel() for p in model.norm.parameters())
    print(f"\nFinal Layer Norm:                   {final_ln_params:>12,} parameters")
    total += final_ln_params
    
    # LM head (tied with embeddings, so don't count)
    print(f"\nLM Head (tied with embeddings):     {token_emb_params:>12,} parameters (not counted)")
    
    print(f"\n{'='*80}")
    print(f"Total Parameters (excluding tied):  {total:>12,}")
    print(f"{'='*80}")

def estimate_memory(model, config, batch_size=8):
    """Estimate memory requirements for training."""
    print("\n" + "="*80)
    print("Memory Requirements (Estimates)")
    print("="*80)
    
    # Model parameters
    param_memory = get_model_size(model)
    print(f"\nModel Parameters:                   {param_memory:>10.2f} MB")
    
    # Optimizer states (Adam has 2 states per parameter)
    optimizer_memory = param_memory * 2
    print(f"Optimizer States (Adam):            {optimizer_memory:>10.2f} MB")
    
    # Gradients
    gradient_memory = param_memory
    print(f"Gradients:                          {gradient_memory:>10.2f} MB")
    
    # Activations (rough estimate)
    seq_len = config.max_seq_len
    hidden_dim = config.hidden_dim
    num_layers = config.num_layers
    
    # Per layer: attention, FFN intermediate, layer norms
    activation_per_layer = batch_size * seq_len * hidden_dim * 4  # bytes (float32)
    activation_per_layer += batch_size * seq_len * config.ffn_dim * 4  # FFN intermediate
    activation_total = activation_per_layer * num_layers / (1024**2)
    
    print(f"Activations (batch={batch_size}):   {activation_total:>10.2f} MB")
    
    # Mixed precision (FP16 saves ~50% on activations and gradients)
    if config.use_mixed_precision:
        activation_total *= 0.5
        gradient_memory *= 0.5
        print(f"  (with FP16 mixed precision:       {activation_total:>10.2f} MB)")
    
    # Gradient checkpointing saves activation memory
    if config.use_gradient_checkpointing:
        activation_total *= 0.3  # Approximate savings
        print(f"  (with gradient checkpointing:     {activation_total:>10.2f} MB)")
    
    total_memory = param_memory + optimizer_memory + gradient_memory + activation_total
    
    print(f"\n{'='*80}")
    print(f"Estimated Total:                    {total_memory:>10.2f} MB")
    print(f"                                    {total_memory/1024:>10.2f} GB")
    print(f"{'='*80}")
    
    print("\nNote: These are rough estimates. Actual memory usage may vary.")
    print("Consider:")
    print("  - Data loading and preprocessing overhead")
    print("  - PyTorch internal buffers and caching")
    print("  - Peak memory usage during backward pass")

def main():
    """Display model summary for all configurations."""
    print("="*80)
    print("GPT MODEL ARCHITECTURE SUMMARY")
    print("="*80)
    
    configs = {
        'Small': get_config('small'),
        'Medium': get_config('medium'),
        'Large': get_config('large')
    }
    
    for name, config in configs.items():
        print(f"\n{'='*80}")
        print(f"{name} Model Configuration")
        print(f"{'='*80}")
        
        # Create model
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
        
        # Architecture
        print(f"\nArchitecture:")
        print(f"  Vocabulary Size:      {config.vocab_size:,}")
        print(f"  Max Sequence Length:  {config.max_seq_len}")
        print(f"  Hidden Dimension:     {config.hidden_dim}")
        print(f"  Number of Layers:     {config.num_layers}")
        print(f"  Attention Heads:      {config.num_heads}")
        print(f"  FFN Dimension:        {config.ffn_dim}")
        print(f"  Dropout:              {config.dropout}")
        
        # Parameters
        total, trainable, tied = count_parameters(model)
        print(f"\nParameters:")
        print(f"  Total:                {total:,}")
        print(f"  Trainable:            {trainable:,}")
        print(f"  Tied (not counted):   {tied:,}")
        print(f"  Unique:               {total - tied:,}")
        
        # Size
        size_mb = get_model_size(model)
        print(f"\nModel Size:")
        print(f"  {size_mb:.2f} MB ({size_mb/1024:.2f} GB)")
        
        # Layer breakdown for medium model
        if name == 'Medium':
            print_layer_summary(model)
            estimate_memory(model, config, batch_size=config.batch_size)
        
        print()
    
    # Test forward pass
    print("\n" + "="*80)
    print("Testing Forward Pass (Medium Model)")
    print("="*80)
    
    config = get_config('medium')
    model = GPTModel(
        vocab_size=config.vocab_size,
        max_seq_len=config.max_seq_len,
        hidden_dim=config.hidden_dim,
        num_layers=config.num_layers,
        num_heads=config.num_heads,
        ffn_dim=config.ffn_dim,
        dropout=config.dropout
    )
    
    # Create dummy input
    batch_size = 4
    seq_len = 128
    input_ids = torch.randint(0, config.vocab_size, (batch_size, seq_len))
    attention_mask = torch.ones(batch_size, seq_len)
    labels = input_ids.clone()
    
    print(f"\nInput shape: {input_ids.shape}")
    print(f"Attention mask shape: {attention_mask.shape}")
    print(f"Labels shape: {labels.shape}")
    
    # Forward pass
    model.eval()
    with torch.no_grad():
        loss, logits = model(input_ids, attention_mask, labels)
    
    print(f"\nOutput:")
    print(f"  Loss: {loss.item():.4f}")
    print(f"  Logits shape: {logits.shape}")
    print(f"  Expected: [batch_size={batch_size}, seq_len={seq_len}, vocab_size={config.vocab_size}]")
    
    print("\n✓ Forward pass successful!")
    
    print("\n" + "="*80)
    print("Model Ready for Training!")
    print("="*80)
    print("\nNext steps:")
    print("  1. Review the parameter counts above")
    print("  2. Check memory requirements for your GPU")
    print("  3. Run training: python scripts/train.py")

if __name__ == "__main__":
    main()
