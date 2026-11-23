"""
GPT-2 Model Implementation
"""
import torch
import torch.nn as nn
from typing import Optional, Tuple


class GPT(nn.Module):
    """GPT-2 style decoder-only transformer for language modeling."""

    def __init__(self, config):
        """
        Initialize GPT model.

        Args:
            config: ModelConfig object with model parameters
        """
        super().__init__()
        self.config = config

        # Token embedding
        self.token_embedding = nn.Embedding(config.vocab_size, config.n_embd)

        # Positional embedding
        self.positional_embedding = nn.Embedding(config.context_length, config.n_embd)

        # Transformer blocks
        self.transformer_blocks = nn.ModuleList([
            TransformerBlock(config) for _ in range(config.n_layer)
        ])

        # Layer norm
        self.ln_f = nn.LayerNorm(config.n_embd)

        # Output projection (language model head)
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size)

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize model weights."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.normal_(module.weight, mean=0.0, std=0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> "ModelOutput":
        """
        Forward pass through the model.

        Args:
            input_ids: Token IDs (batch_size, seq_len)
            attention_mask: Attention mask (batch_size, seq_len)

        Returns:
            ModelOutput with logits and loss
        """
        batch_size, seq_len = input_ids.shape
        device = input_ids.device

        # Token embeddings
        x = self.token_embedding(input_ids)  # (batch, seq, n_embd)

        # Add positional embeddings
        pos_ids = torch.arange(seq_len, device=device).unsqueeze(0)
        x = x + self.positional_embedding(pos_ids)

        # Apply dropout
        x = nn.functional.dropout(x, p=self.config.dropout, training=self.training)

        # Transformer blocks
        for block in self.transformer_blocks:
            x = block(x, attention_mask)

        # Final layer norm
        x = self.ln_f(x)

        # Output projection
        logits = self.lm_head(x)  # (batch, seq, vocab_size)

        return ModelOutput(logits=logits)

    @classmethod
    def from_pretrained(cls, model_name: str, config):
        """Load pretrained model weights."""
        # Placeholder: Load from HuggingFace or checkpoint
        raise NotImplementedError("Use transformers library for pretrained models")

    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: Optional[int] = None,
    ) -> torch.Tensor:
        """Generate text from input tokens."""
        for _ in range(max_new_tokens):
            # Get logits for last token
            logits = self.forward(input_ids).logits
            logits = logits[:, -1, :] / temperature

            # Top-k filtering
            if top_k is not None:
                indices_to_remove = logits < torch.topk(logits, top_k)[0][..., -1, None]
                logits[indices_to_remove] = float('-inf')

            # Sample next token
            probs = torch.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Append to sequence
            input_ids = torch.cat([input_ids, next_token], dim=1)

        return input_ids


class TransformerBlock(nn.Module):
    """Single transformer block with attention and feed-forward."""

    def __init__(self, config):
        super().__init__()
        self.ln1 = nn.LayerNorm(config.n_embd)
        self.attn = MultiHeadAttention(config)
        self.ln2 = nn.LayerNorm(config.n_embd)
        self.mlp = FeedForward(config)

    def forward(self, x, attention_mask=None):
        """Apply transformer block."""
        x = x + self.attn(self.ln1(x), attention_mask)
        x = x + self.mlp(self.ln2(x))
        return x


class MultiHeadAttention(nn.Module):
    """Multi-head self-attention."""

    def __init__(self, config):
        super().__init__()
        assert config.n_embd % config.n_head == 0

        self.n_head = config.n_head
        self.n_embd = config.n_embd
        self.head_dim = config.n_embd // config.n_head

        self.q_proj = nn.Linear(config.n_embd, config.n_embd)
        self.k_proj = nn.Linear(config.n_embd, config.n_embd)
        self.v_proj = nn.Linear(config.n_embd, config.n_embd)
        self.o_proj = nn.Linear(config.n_embd, config.n_embd)

        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x, attention_mask=None):
        """Apply multi-head attention."""
        batch_size, seq_len, _ = x.shape

        # Project to Q, K, V
        q = self.q_proj(x).view(batch_size, seq_len, self.n_head, self.head_dim)
        k = self.k_proj(x).view(batch_size, seq_len, self.n_head, self.head_dim)
        v = self.v_proj(x).view(batch_size, seq_len, self.n_head, self.head_dim)

        # Transpose for attention computation
        q = q.transpose(1, 2)  # (batch, n_head, seq_len, head_dim)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        # Compute attention scores
        scores = torch.matmul(q, k.transpose(-2, -1)) / (self.head_dim ** 0.5)

        # Apply causal mask (prevent attending to future tokens)
        if attention_mask is None:
            causal_mask = torch.triu(
                torch.ones(seq_len, seq_len, device=x.device) * float('-inf'),
                diagonal=1
            )
            scores = scores + causal_mask

        # Apply softmax
        attn_weights = torch.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        # Apply attention to values
        context = torch.matmul(attn_weights, v)

        # Reshape back
        context = context.transpose(1, 2).contiguous()
        context = context.view(batch_size, seq_len, self.n_embd)

        # Final projection
        output = self.o_proj(context)

        return output


class FeedForward(nn.Module):
    """Feed-forward network."""

    def __init__(self, config):
        super().__init__()
        self.fc1 = nn.Linear(config.n_embd, 4 * config.n_embd)
        self.fc2 = nn.Linear(4 * config.n_embd, config.n_embd)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        x = self.fc1(x)
        x = torch.nn.functional.gelu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        return x


class ModelOutput:
    """Output container for model predictions."""

    def __init__(self, logits):
        self.logits = logits
