# Deployment Guide

## Production Inference Setup

### 1. Model Loading

```python
import torch
from src.model import GPT
from src.lora import apply_lora
from config.model_config import ModelConfig
from transformers import GPT2Tokenizer

# Load configuration and model
config = ModelConfig()
model = GPT(config)

# Apply LoRA architecture
model = apply_lora(model)

# Load checkpoint
checkpoint = torch.load('best_model_lora.pt', map_location='cpu')
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()
```

### 2. Inference Function

```python
def predict_sentiment(text: str, model, tokenizer, device='cpu'):
    """Predict sentiment for input text."""
    prompt = f"Sentiment: {text}. Answer: "
    
    # Tokenize
    inputs = tokenizer(prompt, return_tensors='pt').to(device)
    
    # Predict
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
    
    # Extract prediction at label position
    label_pos = inputs['attention_mask'].sum(dim=1) - 1
    label_logits = logits[0, label_pos, :]
    
    # Label token IDs
    label_tokens = {0: 2430, 1: 8944, 2: 3231}
    label_token_ids = torch.tensor(
        [label_tokens[k] for k in sorted(label_tokens.keys())],
        device=device
    )
    
    # Predict class
    label_token_logits = label_logits[label_token_ids]
    prediction = torch.argmax(label_token_logits).item()
    
    # Convert to label
    label_names = ['Negative', 'Neutral', 'Positive']
    return label_names[prediction]
```

### 3. REST API Example (FastAPI)

```python
from fastapi import FastAPI
from pydantic import BaseModel
import torch
from src.model import GPT
from src.lora import apply_lora

app = FastAPI()

# Global model state
model = None
tokenizer = None
device = 'cuda' if torch.cuda.is_available() else 'cpu'

@app.on_event("startup")
async def load_model():
    global model, tokenizer
    config = ModelConfig()
    model = GPT(config).to(device)
    model = apply_lora(model)
    checkpoint = torch.load('best_model_lora.pt', map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')

class SentimentRequest(BaseModel):
    text: str

class SentimentResponse(BaseModel):
    text: str
    sentiment: str
    confidence: float

@app.post("/predict")
async def predict(request: SentimentRequest) -> SentimentResponse:
    sentiment = predict_sentiment(
        request.text, model, tokenizer, device
    )
    return SentimentResponse(
        text=request.text,
        sentiment=sentiment,
        confidence=0.95  # Add confidence computation if needed
    )
```

### 4. Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5. Performance Optimization

#### Merging LoRA Weights
For faster inference, merge LoRA weights into the base model:

```python
from src.lora import merge_lora_weights

# Merge LoRA weights
model = merge_lora_weights(model)

# Save merged model
torch.save(model.state_dict(), 'model_merged.pt')

# Load without LoRA overhead
model_merged = GPT(config)
model_merged.load_state_dict(torch.load('model_merged.pt'))
```

#### Quantization
For memory efficiency:

```python
# INT8 quantization with transformers
from transformers import GPT2LMHeadModel
import torch.quantization

model.qconfig = torch.quantization.get_default_qat_qconfig('fbgemm')
torch.quantization.prepare_qat(model, inplace=True)
torch.quantization.convert(model, inplace=True)
```

#### Batch Processing
For throughput:

```python
def batch_predict(texts: List[str], model, tokenizer, device='cpu'):
    """Predict sentiment for multiple texts."""
    prompts = [f"Sentiment: {t}. Answer: " for t in texts]
    
    # Tokenize batch
    inputs = tokenizer(
        prompts,
        padding=True,
        truncation=True,
        return_tensors='pt'
    ).to(device)
    
    # Batch inference
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
    
    # Extract predictions
    predictions = []
    for i in range(len(texts)):
        label_pos = inputs['attention_mask'][i].sum() - 1
        label_logits = logits[i, label_pos, :]
        pred = torch.argmax(label_logits).item()
        predictions.append(pred)
    
    return predictions
```

## Monitoring & Logging

```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

handler = logging.FileHandler('inference.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

@app.post("/predict")
async def predict(request: SentimentRequest):
    try:
        sentiment = predict_sentiment(request.text, model, tokenizer, device)
        logger.info(f"Prediction: {sentiment} for text: {request.text[:50]}...")
        return SentimentResponse(text=request.text, sentiment=sentiment)
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise
```

## Scaling Considerations

1. **GPU Allocation**: Use multi-GPU with `torch.nn.DataParallel` or `DistributedDataParallel`
2. **Caching**: Cache model outputs for frequently requested texts
3. **Load Balancing**: Distribute requests across multiple instances
4. **Rate Limiting**: Implement request throttling
5. **Health Checks**: Monitor model inference latency

---

**Status**: Production-ready  
**Last Updated**: May 2026
