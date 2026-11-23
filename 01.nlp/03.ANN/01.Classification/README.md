# ANN classification: customer churn

A feed-forward network (Keras) that predicts whether a bank customer leaves (`Exited`), trained on `Churn_Modelling.csv`, with a Streamlit app for predictions.

## Files

| File | What it does |
|---|---|
| `01.classification_problem.ipynb` | Preprocessing (label-encodes `Gender`, one-hot encodes `Geography`, `StandardScaler`), trains Dense(64, ReLU) → Dense(32, ReLU) → Dense(1, sigmoid) with binary cross-entropy, Adam and early stopping (patience 5); saves the model and encoders |
| `02.prediction.ipynb` | Loads the saved model and encoders and scores one example |
| `03.streamlit_classification.py` | Streamlit app for churn prediction |
| `model.h5`, `scaler.pkl`, `label_encoder_gender.pkl`, `onehot_encoder_geo.pkl` | Saved model and preprocessing objects |
| `Churn_Modelling.csv` | Dataset |

## Run

```bash
pip install -r requirements.txt
streamlit run 03.streamlit_classification.py
```

**Source:** course labs from the Udemy course *Complete Generative AI Course With LangChain and Hugging Face* (completed 20 Jan 2026).
