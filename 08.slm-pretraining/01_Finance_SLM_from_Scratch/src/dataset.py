"""
Financial Sentiment Dataset Implementation
"""
import torch
from torch.utils.data import Dataset, DataLoader
from typing import Dict, List, Optional, Tuple
import numpy as np


class FinancialSentimentDataset(Dataset):
    """HuggingFace Financial Sentiment Dataset."""

    # Label to token mapping
    LABEL_TOKENS = {
        0: 2430,    # "negative"
        1: 8944,    # "neutral"
        2: 3231,    # "positive"
    }

    def __init__(
        self,
        texts: List[str],
        labels: List[int],
        tokenizer,
        max_length: int = 128,
        prompt_template: str = "Sentiment: {text}. Answer: ",
    ):
        """
        Initialize dataset.

        Args:
            texts: List of input texts
            labels: List of labels (0, 1, 2)
            tokenizer: Tokenizer instance
            max_length: Maximum sequence length
            prompt_template: Template for input text
        """
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.prompt_template = prompt_template

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx) -> Dict[str, torch.Tensor]:
        """Get single sample."""
        text = self.texts[idx]
        label = self.labels[idx]

        # Create prompt
        prompt_text = self.prompt_template.format(text=text)

        # Tokenize
        encoding = self.tokenizer(
            prompt_text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt',
        )

        input_ids = encoding['input_ids'].squeeze(0)
        attention_mask = encoding['attention_mask'].squeeze(0)

        # Calculate label position (after prompt, before padding)
        # This is where the model should predict the sentiment
        prompt_length = len(
            self.tokenizer(self.prompt_template.format(text=''), add_special_tokens=True)['input_ids']
        ) - 1
        label_position = min(prompt_length + len(
            self.tokenizer(text, add_special_tokens=False)['input_ids']
        ) - 1, self.max_length - 1)

        return {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'label': torch.tensor(label, dtype=torch.long),
            'label_position': torch.tensor(label_position, dtype=torch.long),
            'label_token': torch.tensor(self.LABEL_TOKENS[label], dtype=torch.long),
        }

    def collate_fn(self, batch):
        """Custom collate function."""
        input_ids = torch.stack([item['input_ids'] for item in batch])
        attention_mask = torch.stack([item['attention_mask'] for item in batch])
        labels = torch.stack([item['label'] for item in batch])
        label_positions = torch.stack([item['label_position'] for item in batch])
        label_tokens = torch.stack([item['label_token'] for item in batch])

        return {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'labels': labels,
            'label_positions': label_positions,
            'label_tokens': label_tokens,
        }


def prepare_dataset(
    dataset_dict: Dict,
    tokenizer,
    batch_size: int = 32,
    max_length: int = 128,
) -> Tuple[DataLoader, DataLoader]:
    """
    Prepare train and validation dataloaders.

    Args:
        dataset_dict: Dictionary with 'train' and 'validation' splits
        tokenizer: Tokenizer instance
        batch_size: Batch size
        max_length: Maximum sequence length

    Returns:
        Tuple of (train_loader, val_loader)
    """
    # Create datasets
    train_dataset = FinancialSentimentDataset(
        texts=dataset_dict['train']['text'],
        labels=dataset_dict['train']['label'],
        tokenizer=tokenizer,
        max_length=max_length,
    )

    val_dataset = FinancialSentimentDataset(
        texts=dataset_dict['validation']['text'],
        labels=dataset_dict['validation']['label'],
        tokenizer=tokenizer,
        max_length=max_length,
    )

    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=train_dataset.collate_fn,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=val_dataset.collate_fn,
    )

    return train_loader, val_loader


def load_hf_dataset(dataset_name: str = "zeroshot/twitter-financial-news-sentiment"):
    """Load HuggingFace dataset."""
    try:
        from datasets import load_dataset
        return load_dataset(dataset_name)
    except ImportError:
        raise ImportError("datasets library required. Install with: pip install datasets")
    except Exception as e:
        raise RuntimeError(f"Failed to load dataset {dataset_name}: {e}")
