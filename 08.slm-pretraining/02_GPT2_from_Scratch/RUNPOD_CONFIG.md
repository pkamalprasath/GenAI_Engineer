# RunPod GPU Configuration for GPT-2 Training

## GPU Selection Guide

### For This Model Size (GPT-2 124M params)

| GPU | VRAM | Cost/hr | Recommendation | Notes |
|-----|------|---------|-----------------|-------|
| **H100 SXM** | 80GB | $2.99 | ⭐ BEST | Modern arch, good price, plenty of headroom |
| RTX PRO 6000 | 96GB | $1.89 | ✅ BUDGET | Most VRAM, best value if cost-critical |
| H200 SXM | 141GB | $3.99 | ⚠️ OVERKILL | Too much VRAM for this model |
| B200 | 180GB | $5.49 | ❌ AVOID | Unnecessarily expensive |

---

## Memory Breakdown for GPT-2 (124M)

```
Model weights:        ~500 MB
Optimizer states:     ~1 GB (AdamW with momentum)
Activations (batch 64, seq 1024):  ~8-10 GB
Safety margin:        ~5 GB
─────────────────────────────
Total needed:        ~15 GB per GPU
Available (H100):     80 GB → Can safely run with batch=128+
```

---

## Training Parameter Optimization

### Single GPU Configuration (H100)
```python
# In train_gpt2.py, change:
total_batch_size = 131072  # 64 * 1024 * 2 (was 524K for 8 GPUs)
B = 64                     # micro batch size
T = 1024                   # sequence length
# grad_accum_steps will auto-calculate to 2
```

**Performance expectation:**
- ~200-300 tokens/sec on H100
- ~8-10 hours for 1 epoch (10B token dataset)

### Multi-GPU Configuration (2x H100)
```python
# Run with: torchrun --standalone --nproc_per_node=2 train_gpt2.py
total_batch_size = 262144  # Back to reasonable size for 2 GPUs
B = 64
T = 1024
# grad_accum_steps = 2
```

**Performance expectation:**
- ~400-600 tokens/sec across both GPUs
- ~4-5 hours for 1 epoch

---

## Recommended Training Script Updates

### 1. Add Memory-Efficient Settings (at startup)
```python
# After line 318 (torch.manual_seed)
torch.cuda.empty_cache()

# Optimizations for reduced memory
torch.set_float32_matmul_precision('high')  # Already in code
torch.backends.cudnn.enabled = True
torch.backends.cudnn.benchmark = True  # Auto-tune for this hardware
```

### 2. Optional: Add Gradient Checkpointing (saves ~30% memory)
In the `Block` class forward method, wrap with checkpointing:
```python
def forward(self, x):
    if self.training and self.gradient_checkpointing:
        x = x + checkpoint(self.attn, self.ln_1(x))
        x = x + checkpoint(self.mlp, self.ln_2(x))
    else:
        x = x + self.attn(self.ln_1(x))
        x = x + self.mlp(self.ln_2(x))
    return x
```

### 3. Monitor VRAM Usage (add this in training loop)
```python
if step % 100 == 0 and master_process and device.startswith('cuda'):
    reserved = torch.cuda.memory_reserved(device)
    allocated = torch.cuda.memory_allocated(device)
    print(f"  VRAM: {allocated/1e9:.2f}GB / {reserved/1e9:.2f}GB reserved")
```

---

## Launch Commands

### Single GPU
```bash
# On RunPod SSH terminal:
cd /path/to/project
python train_gpt2.py
```

### Multi-GPU (if you provision 2+ GPUs)
```bash
torchrun --standalone --nproc_per_node=2 train_gpt2.py
```

### With Custom Logging
```bash
# Redirect output to log file
python train_gpt2.py 2>&1 | tee training_runpod.log
```

---

## Expected Performance (H100)

```
Single H100:
├─ Peak throughput: 250-350 tokens/sec
├─ Per epoch (10B tokens): 8-10 hours
├─ Total training cost: $24-30 (1 epoch)
└─ Batch size: 64

2x H100:
├─ Peak throughput: 500-700 tokens/sec  (near-linear scaling)
├─ Per epoch: 4-5 hours
├─ Total training cost: $48-60 (1 epoch, both GPUs)
└─ Batch size: 64 per GPU
```

---

## Troubleshooting

### Out of Memory (OOM)?
```python
# Reduce batch size
B = 32  # instead of 64

# Or reduce sequence length
T = 512  # instead of 1024

# Or increase gradient accumulation
total_batch_size = 65536  # (will auto-calc grad_accum_steps)
```

### Slow training?
1. Check `tokens_per_sec` in output - should be >100
2. Verify GPU is being used: `nvidia-smi` shows GPU %
3. Try enabling TorchCompile (line 342) once debugging is done

### NCCL Issues (DDP failure)?
Add before `init_process_group`:
```python
os.environ['NCCL_DEBUG'] = 'INFO'
os.environ['NCCL_TIMEOUT'] = '1800'  # 30 min timeout
```

---

## Cost Analysis

| Setup | GPUs | Duration | Cost |
|-------|------|----------|------|
| Single H100 | 1 | 8-10h | $24-30 |
| 2x H100 | 2 | 4-5h | $48-60 |
| Single RTX6000 | 1 | 10-12h | $19-23 |
| 4x RTX6000 | 4 | 2-3h | $76-90 |

**Recommendation:** Start with single H100 → if speed is critical, scale to 2x H100
