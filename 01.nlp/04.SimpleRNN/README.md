# SimpleRNN: IMDB sentiment

Course notebooks building a simple recurrent network for movie-review sentiment with Keras.

| File | What it does |
|---|---|
| `01.SimpleRNN.ipynb` | Loads the Keras IMDB dataset (10,000-word vocabulary, reviews padded to 500 tokens), trains Embedding(128) → SimpleRNN(128) → Dense(sigmoid) with early stopping, saves `simple_rnn_imdb.h5` |
| `02.embedding.ipynb` | Word-embedding basics with Keras |
| `03.Prediction.ipynb` | Loads the saved model and scores new reviews |
| `04.main.py` | Streamlit app: paste a review, get a sentiment prediction |

```bash
pip install -r requirements.txt
streamlit run 04.main.py
```

**Source:** course labs from the Udemy course *Complete Generative AI Course With LangChain and Hugging Face* (completed 20 Jan 2026).
