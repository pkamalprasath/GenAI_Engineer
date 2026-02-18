import streamlit as st
import numpy as np
import tensorflow as tf
from sklearn.preprocessing import StandardScaler, LabelEncoder, OneHotEncoder
import pandas as pd
import pickle
from pathlib import Path

# Get the directory where this script lives
BASE_DIR = Path(__file__).resolve().parent

# Load the trained model
model_path = BASE_DIR / "regression_model.h5"
model = tf.keras.models.load_model(model_path)

# Load the encoders and scaler
label_encoder_gender_path = BASE_DIR / "label_encoder_gender.pkl"
onehot_encoder_geo_path = BASE_DIR / "onehot_encoder_geo.pkl"
scaler_path = BASE_DIR / "scaler.pkl"

# Load the encoders and scaler
with open(label_encoder_gender_path,'rb') as file:
    label_encoder_gender=pickle.load(file)

with open(onehot_encoder_geo_path,'rb') as file:
    onehot_encoder_geo=pickle.load(file) 

with open(scaler_path,'rb') as file:
    scaler=pickle.load(file)


## streamlit app
st.title('Estimated Salary Prediction')

# User input
geography = st.selectbox('Geography', onehot_encoder_geo.categories_[0])
gender = st.selectbox('Gender',label_encoder_gender.classes_)
age = st.slider('Age', 18, 92)
balance = st.number_input('Balance')
credit_score = st.number_input('Credit Score')
exited = st.selectbox('Exited',[0,1])
tenure = st.slider('Tenure', 0, 10)
num_of_products = st.slider('Number of Products', 1, 4)
has_cr_card = st.selectbox('Has Credit Card', [0, 1])
is_active_member = st.selectbox('Is Active Member', [0, 1])

# Prepare the input data
input_data = pd.DataFrame({
    'CreditScore': [credit_score],
    'Gender': [label_encoder_gender.transform([gender])[0]],
    'Age': [age],
    'Tenure': [tenure],
    'Balance': [balance],
    'NumOfProducts': [num_of_products],
    'HasCrCard': [has_cr_card],
    'IsActiveMember': [is_active_member],
    'Exited': [exited]
})
# The OneHotEncoder expects a 2D array, so we wrap the selected geography inside [[ ]].
# This converts a category like "France" into a one-hot vector such as [1, 0, 0].
# .toarray() ensures we get a dense NumPy array instead of a sparse matrix.

# One-hot encode 'Geography'
geo_encoded = onehot_encoder_geo.transform([[geography]]).toarray()

# Convert the encoded array into a DataFrame with proper column names.
# get_feature_names_out(['Geography']) generates columns like:
# ['Geography_France', 'Geography_Germany', 'Geography_Spain'] 

geo_encoded_df = pd.DataFrame(geo_encoded, columns=onehot_encoder_geo.get_feature_names_out(['Geography']))

# -------------------------------
# 2. Combine encoded geography with other input features
# -------------------------------
# input_data contains all the numerical and label-encoded features.
# geo_encoded_df contains the one-hot encoded geography columns.
# We merge them side-by-side (axis=1).
# reset_index(drop=True) ensures indexes align correctly (both start at 0).

input_data = pd.concat([input_data.reset_index(drop=True), geo_encoded_df], axis=1)

# -------------------------------
# 3. Scale the combined input data
# -------------------------------
# The StandardScaler applies the SAME scaling used during model training.
# This ensures the values (age, balance, salary, etc.) match the distribution
# the neural network was trained on, avoiding distorted predictions.
# Scale the input data

input_data_scaled = scaler.transform(input_data)

# -------------------------------
# 4. Make prediction using the trained model
# -------------------------------
# The neural network expects the scaled input features.
# model.predict() returns a NumPy array of predictions.
# For a single row of input, the output looks like: [[value]]
# So we extract the first element using prediction[0][0]

prediction = model.predict(input_data_scaled)
prediction_salary = prediction[0][0]

# -------------------------------
# 5. Display the prediction in Streamlit
# -------------------------------
# We format the value to two decimal places.
# The message can be customized depending on how you want to present the result.
st.write(f'Predicted Estimated Salary: ${prediction_salary:.2f}')

