"""
LoRA (Low-Rank Adaptation) Implementation
"""
import torch
import torch.nn as nn
from typing import Optional


class LoRALinear(nn.Module):
    """Linear layer with LoRA adaptation."""

    def __init__(
        self,
        original_module: nn.Linear,
        rank: int = 8,
        alpha: float = 16.0,
    ):
        """
        Initialize LoRA linear layer.

        Args:
            original_module: Original nn.Linear layer to adapt
            rank: LoRA rank (r in LoRA paper)
            alpha: Scaling factor (typically 2 * rank)
        """
        super().__init__()
        self.original_module = original_module
        self.rank = rank
        self.alpha = alpha

        in_features = original_module.in_features
        out_features = original_module.out_features

        # LoRA matrices: ΔW = BA (low-rank decomposition)
        self.lora_A = nn.Parameter(
            torch.randn(in_features, rank) * (1 / (rank ** 0.5))
        )
        self.lora_B = nn.Parameter(torch.zeros(out_features, rank))

    def forward(self, x):
        """Apply original linear + LoRA adaptation."""
        # Original forward
        original_out = self.original_module(x)

        # LoRA forward: x @ A @ B.T * (alpha / rank)
        scaling = self.alpha / self.rank
        lora_out = (x @ self.lora_A @ self.lora_B.t()) * scaling

        return original_out + lora_out

    def merge(self):
        """Merge LoRA weights into original module (for inference)."""
        scaling = self.alpha / self.rank
        with torch.no_grad():
            delta_w = (self.lora_A @ self.lora_B.t()) * scaling
            self.original_module.weight.data += delta_w.t()
        return self.original_module


class LoRALayer(nn.Module):
    """LoRA adaptation for attention layers."""

    def __init__(
        self,
        attention_layer: nn.Module,
        rank: int = 8,
        alpha: float = 16.0,
        target_modules: Optional[list] = None,
    ):
        """
        Apply LoRA to attention layer.

        Args:
            attention_layer: Attention module to adapt
            rank: LoRA rank
            alpha: Scaling factor
            target_modules: List of module names to apply LoRA to
                          e.g., ['q_proj', 'v_proj']
        """
        super().__init__()
        self.attention_layer = attention_layer
        self.rank = rank
        self.alpha = alpha
        self.target_modules = target_modules or ['q_proj', 'v_proj']

        # Store original modules
        self.lora_modules = {}

    def apply_lora(self):
        """Apply LoRA to target modules."""
        for module_name in self.target_modules:
            if hasattr(self.attention_layer, module_name):
                original_module = getattr(self.attention_layer, module_name)
                if isinstance(original_module, nn.Linear):
                    # Create LoRA version
                    lora_module = LoRALinear(
                        original_module,
                        rank=self.rank,
                        alpha=self.alpha,
                    )
                    # Replace
                    setattr(self.attention_layer, module_name, lora_module)
                    self.lora_modules[module_name] = lora_module

    def forward(self, x, attention_mask=None):
        """Forward pass through attention with LoRA."""
        return self.attention_layer(x, attention_mask)


def apply_lora(
    model: nn.Module,
    rank: int = 8,
    alpha: Optional[float] = None,
    target_modules: Optional[list] = None,
) -> nn.Module:
    """
    Apply LoRA to all attention layers in model.

    Args:
        model: Model to adapt
        rank: LoRA rank
        alpha: Scaling factor (default: 2 * rank)
        target_modules: Modules to apply LoRA to (e.g., ['q_proj', 'v_proj'])

    Returns:
        Model with LoRA applied
    """
    if alpha is None:
        alpha = 2 * rank

    if target_modules is None:
        target_modules = ['q_proj', 'v_proj']

    lora_modules = {}

    # Find and adapt attention layers
    for name, module in model.named_modules():
        # Look for attention modules
        if 'attn' in name.lower() or 'attention' in name.lower():
            for target_module_name in target_modules:
                if hasattr(module, target_module_name):
                    original_linear = getattr(module, target_module_name)
                    if isinstance(original_linear, nn.Linear):
                        # Create LoRA version
                        lora_linear = LoRALinear(
                            original_linear,
                            rank=rank,
                            alpha=alpha,
                        )
                        # Replace
                        setattr(module, target_module_name, lora_linear)

                        # Track for reference
                        full_name = f"{name}.{target_module_name}"
                        lora_modules[full_name] = lora_linear

    print(f"LoRA applied to {len(lora_modules)} modules")
    for name in lora_modules:
        print(f"  - {name}")

    # Store reference to LoRA modules on model
    model.lora_modules = lora_modules

    return model


def get_lora_params(model: nn.Module):
    """Get all LoRA parameters for optimization."""
    lora_params = []
    for module in model.modules():
        if isinstance(module, LoRALinear):
            lora_params.extend([module.lora_A, module.lora_B])
    return lora_params


def get_lora_state_dict(model: nn.Module) -> dict:
    """Extract only LoRA state dict (for efficient checkpointing)."""
    state_dict = {}
    for name, param in model.named_parameters():
        if 'lora' in name:
            state_dict[name] = param.data
    return state_dict


def merge_lora_weights(model: nn.Module) -> nn.Module:
    """Merge LoRA weights into original weights (for inference)."""
    for module in model.modules():
        if isinstance(module, LoRALinear):
            with torch.no_grad():
                scaling = module.alpha / module.rank
                delta_w = (module.lora_A @ module.lora_B.t()) * scaling
                module.original_module.weight.data += delta_w.t()

                # Remove LoRA parameters
                del module.lora_A
                del module.lora_B

    return model


def count_lora_params(model: nn.Module) -> int:
    """Count total LoRA parameters."""
    total = 0
    for module in model.modules():
        if isinstance(module, LoRALinear):
            total += module.lora_A.numel() + module.lora_B.numel()
    return total


def count_total_params(model: nn.Module) -> int:
    """Count total model parameters."""
    return sum(p.numel() for p in model.parameters())
