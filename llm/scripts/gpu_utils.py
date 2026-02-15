"""
GPU Optimization Utilities
Monitor and optimize GPU usage during training.
"""

import torch
import psutil
import time
from pathlib import Path

def get_gpu_memory():
    """Get current GPU memory usage."""
    if not torch.cuda.is_available():
        return None
    
    allocated = torch.cuda.memory_allocated() / 1024**3  # GB
    reserved = torch.cuda.memory_reserved() / 1024**3  # GB
    max_allocated = torch.cuda.max_memory_allocated() / 1024**3  # GB
    
    return {
        'allocated': allocated,
        'reserved': reserved,
        'max_allocated': max_allocated
    }

def print_gpu_memory():
    """Print GPU memory usage."""
    mem = get_gpu_memory()
    
    if mem is None:
        print("No GPU available")
        return
    
    print(f"\nGPU Memory Usage:")
    print(f"  Allocated:     {mem['allocated']:.2f} GB")
    print(f"  Reserved:      {mem['reserved']:.2f} GB")
    print(f"  Peak Allocated: {mem['max_allocated']:.2f} GB")

def optimize_memory():
    """Clear GPU cache and optimize memory."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        print("✓ GPU cache cleared")

def get_system_stats():
    """Get system resource usage."""
    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    ram_percent = ram.percent
    ram_used = ram.used / 1024**3  # GB
    ram_total = ram.total / 1024**3  # GB
    
    stats = {
        'cpu_percent': cpu_percent,
        'ram_percent': ram_percent,
        'ram_used': ram_used,
        'ram_total': ram_total
    }
    
    return stats

def print_system_stats():
    """Print system resource usage."""
    stats = get_system_stats()
    
    print(f"\nSystem Resources:")
    print(f"  CPU Usage:  {stats['cpu_percent']:.1f}%")
    print(f"  RAM Usage:  {stats['ram_used']:.2f} GB / {stats['ram_total']:.2f} GB ({stats['ram_percent']:.1f}%)")
    
    if torch.cuda.is_available():
        print(f"  GPU:        {torch.cuda.get_device_name(0)}")
        print(f"  GPU Count:  {torch.cuda.device_count()}")

def benchmark_forward_pass(model, batch_size=8, seq_len=512, num_iterations=10):
    """Benchmark model forward pass."""
    if not torch.cuda.is_available():
        device = torch.device('cpu')
        print("Running benchmark on CPU (will be slow)")
    else:
        device = torch.device('cuda')
        print(f"Running benchmark on {torch.cuda.get_device_name(0)}")
    
    model = model.to(device)
    model.eval()
    
    # Create dummy batch
    input_ids = torch.randint(0, model.vocab_size, (batch_size, seq_len), device=device)
    attention_mask = torch.ones(batch_size, seq_len, device=device)
    labels = input_ids.clone()
    
    # Warmup
    print("Warming up...")
    for _ in range(3):
        with torch.no_grad():
            _ = model(input_ids, attention_mask, labels)
    
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    
    # Benchmark
    print(f"Running {num_iterations} iterations...")
    start_time = time.time()
    
    for _ in range(num_iterations):
        with torch.no_grad():
            loss, _ = model(input_ids, attention_mask, labels)
        
        if torch.cuda.is_available():
            torch.cuda.synchronize()
    
    end_time = time.time()
    
    avg_time = (end_time - start_time) / num_iterations
    throughput = batch_size / avg_time
    
    print(f"\n✓ Benchmark Results:")
    print(f"  Batch size: {batch_size}")
    print(f"  Sequence length: {seq_len}")
    print(f"  Average time per batch: {avg_time*1000:.2f} ms")
    print(f"  Throughput: {throughput:.2f} samples/sec")
    
    if torch.cuda.is_available():
        print_gpu_memory()
    
    return avg_time, throughput

def suggest_batch_size(model, max_seq_len=512):
    """Suggest optimal batch size based on available GPU memory."""
    if not torch.cuda.is_available():
        print("No GPU available. Suggested batch size: 2-4 (CPU training)")
        return 2
    
    # Get total GPU memory
    total_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3  # GB
    
    print(f"\nGPU: {torch.cuda.get_device_name(0)}")
    print(f"Total GPU Memory: {total_memory:.2f} GB")
    
    # Estimate memory per sample
    # This is a rough estimate
    model_size = sum(p.numel() * p.element_size() for p in model.parameters()) / 1024**3
    
    # Rough estimates (in GB)
    optimizer_memory = model_size * 2  # Adam has 2 states
    gradient_memory = model_size
    activation_per_sample = max_seq_len * model.hidden_dim * 4 * model.num_layers / 1024**3
    
    # Leave 20% headroom
    available_memory = total_memory * 0.8 - model_size - optimizer_memory - gradient_memory
    
    suggested_batch_size = int(available_memory / activation_per_sample)
    suggested_batch_size = max(1, min(suggested_batch_size, 32))  # Clamp to 1-32
    
    print(f"\nMemory Breakdown:")
    print(f"  Model:      {model_size:.2f} GB")
    print(f"  Optimizer:  {optimizer_memory:.2f} GB")
    print(f"  Gradients:  {gradient_memory:.2f} GB")
    print(f"  Per sample: {activation_per_sample*1024:.0f} MB")
    print(f"\nSuggested batch size: {suggested_batch_size}")
    print(f"(This is a rough estimate - actual usage may vary)")
    
    return suggested_batch_size

def main():
    """Test GPU utilities."""
    print("="*80)
    print("GPU Optimization Utilities")
    print("="*80)
    
    print_system_stats()
    
    if torch.cuda.is_available():
        print_gpu_memory()
        
        # Test model
        from model import GPTModel
        from config import get_config
        
        config = get_config('small')
        model = GPTModel(
            vocab_size=config.vocab_size,
            max_seq_len=config.max_seq_len,
            hidden_dim=config.hidden_dim,
            num_layers=config.num_layers,
            num_heads=config.num_heads,
            ffn_dim=config.ffn_dim
        )
        
        print("\n" + "="*80)
        print("Batch Size Suggestion")
        print("="*80)
        suggested = suggest_batch_size(model, config.max_seq_len)
        
        print("\n" + "="*80)
        print("Forward Pass Benchmark")
        print("="*80)
        benchmark_forward_pass(model, batch_size=4, seq_len=128, num_iterations=10)
    else:
        print("\n⚠ No GPU available for benchmarking")

if __name__ == "__main__":
    main()
