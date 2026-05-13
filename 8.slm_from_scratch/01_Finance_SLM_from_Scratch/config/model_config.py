"""
Model Configuration
"""


class ModelConfig:
    """GPT-2 model configuration."""

    # Architecture
    vocab_size = 50257          # GPT-2 vocabulary size
    context_length = 1024       # Maximum sequence length
    n_embd = 768                # Embedding dimension (hidden size)
    n_head = 12                 # Number of attention heads
    n_layer = 12                # Number of transformer blocks

    # Regularization
    dropout = 0.1               # Dropout rate
    bias = True                 # Use bias in linear layers

    # Initialization
    initializer_range = 0.02    # Weight initialization range

    def __repr__(self):
        return (
            f"ModelConfig(\n"
            f"  vocab_size={self.vocab_size},\n"
            f"  context_length={self.context_length},\n"
            f"  n_embd={self.n_embd},\n"
            f"  n_head={self.n_head},\n"
            f"  n_layer={self.n_layer},\n"
            f"  dropout={self.dropout}\n"
            f")"
        )

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'vocab_size': self.vocab_size,
            'context_length': self.context_length,
            'n_embd': self.n_embd,
            'n_head': self.n_head,
            'n_layer': self.n_layer,
            'dropout': self.dropout,
            'bias': self.bias,
            'initializer_range': self.initializer_range,
        }
