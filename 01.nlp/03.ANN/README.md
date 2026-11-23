# ANN: feed-forward networks on tabular data

Two course projects on the same bank-customer dataset (`Churn_Modelling.csv`), each with a Keras model and a Streamlit app.

| Project | Task | Model |
|---|---|---|
| [01. Classification](./01.Classification/) | Predict customer churn (binary) | Dense 64 → 32 → 1, sigmoid output |
| [02. Regression](./02.Regression/) | Predict estimated salary | Dense 64 → 32 → 1, linear output |

Both cover label and one-hot encoding, feature scaling with `StandardScaler`, early stopping, saving the model (`.h5`) and encoders (`.pkl`), and a Streamlit front end.

**Source:** course labs from the Udemy course *Complete Generative AI Course With LangChain and Hugging Face* (completed 20 Jan 2026).

## Stack

TensorFlow/Keras, scikit-learn, pandas, Streamlit.
