# ANN regression: estimated salary

A feed-forward network (Keras) that predicts `EstimatedSalary` from the other customer fields in `Churn_Modelling.csv`, with a Streamlit app for predictions.

## Files

| File | What it does |
|---|---|
| `01.Regression_problem.ipynb` | Preprocessing (label-encodes `Gender`, one-hot encodes `Geography`, `StandardScaler`), trains Dense(64, ReLU) → Dense(32, ReLU) → Dense(1) with mean absolute error and early stopping (patience 5); saves `regression_model.h5` and the encoders |
| `02.prediction.ipynb` | A copy of the classification folder's prediction notebook (it loads the churn model, not the regression model) |
| `03.streamlit_regression.py` | Streamlit app for salary prediction |
| `regression_model.h5`, `scaler.pkl`, `label_encoder_gender.pkl`, `onehot_encoder_geo.pkl` | Saved model and preprocessing objects |
| `Churn_Modelling.csv` | Dataset (same file as in `01.Classification/`) |

## Run

```bash
pip install -r requirements.txt
streamlit run 03.streamlit_regression.py
```

**Source:** course labs from the Udemy course *Complete Generative AI Course With LangChain and Hugging Face* (completed 20 Jan 2026).
