# Step 1: Import Libraries and Load the Model
import numpy as np
import tensorflow as tf
from tensorflow.keras.datasets import imdb
from tensorflow.keras.preprocessing import sequence
from tensorflow.keras.models import load_model 
import streamlit as st

# Load the IMDB dataset word index
word_index = imdb.get_word_index()
reverse_word_index = {value: key for key, value in word_index.items()}

# Load the pre-trained model with ReLU activation
model = load_model('simple_rnn_imdb.h5')


# Function to preprocess user input
def preprocess_text(text):
    # Convert text to lowercase words
    words = text.lower().split()
    
    # Change each word into its index number
    # If word not found → use index 2 (unknown)
    encoded_review = [word_index.get(word, 2) + 3 for word in words]
    
    # Pad the review so its length becomes 500 (same as training data)
    padded_review = sequence.pad_sequences([encoded_review], maxlen=500)
    return padded_review 

# Function to decode reviews
def decode_review(encoded_review):
    # Convert numbers back to words
    # (i - 3 because IMDB reserves first 3 indexes)
    return ' '.join([reverse_word_index.get(i - 3, '?') for i in encoded_review])


# Streamlit 
st.title('IMDB Movie Review Sentiment Analysis')
st.write('Enter the movie review to classify it as positive or negative')

#User input 
user_input=st.text_area('Movie Review')

if st.button('Classify'):
    
    preprocess_input=preprocess_text(user_input) 

#Make prediction 
    prediction=model.predict(preprocess_input) 
    sentiment='Positive' if prediction[0][0] > 0.5 else 'Negative'
    
    #Display the result 
    st.write(f'Sentiment: {sentiment}')
    prob=prediction[0][0]
    percent = round(prob * 100)
    st.write(f"Prediction: {percent}%")
else:
    st.write("Please enter a movie review.")
    



