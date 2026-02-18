# 📈 Regression Model – Estimated Salary Prediction

This project demonstrates how to build, train, and deploy a **regression machine learning model** to predict continuous values—in this case, **Estimated Salary**—using demographic and customer-related features.

A Streamlit web application is included to allow users to enter inputs interactively and receive real-time predictions.

---

## 🚀 Project Overview

This project covers the complete machine learning workflow:

- Loading and exploring the dataset  
- Preparing data for regression  
- Encoding categorical variables  
- Scaling numerical features  
- Training a regression model using TensorFlow/Keras  
- Saving the trained model and preprocessing objects  
- Building an interactive Streamlit app for deployment  

---

## 📂 Project Structure

project-folder/
│── regression_model.h5 # Trained TensorFlow model
│── scaler.pkl # StandardScaler used during training
│── label_encoder_gender.pkl # Saved label encoder for Gender
│── onehot_encoder_geo.pkl # Saved OneHotEncoder for Geography
│── streamlit_app.py # Streamlit UI for predictions
│── train_model.ipynb # Notebook for training the model
│── dataset.csv # Input dataset
│── requirements.txt # Project dependencies
└── README.md # Project documentation


---

## 📊 Dataset Description

The dataset includes the following features:

| Feature | Type | Description |
|--------|------|-------------|
| `CreditScore` | Numeric | Customer credit score |
| `Gender` | Categorical | Male / Female |
| `Age` | Numeric | Customer age |
| `Tenure` | Numeric | Years stayed with bank |
| `Balance` | Numeric | Account balance |
| `NumOfProducts` | Numeric | Number of active products |
| `HasCrCard` | Binary | Credit card status |
| `IsActiveMember` | Binary | Customer activity |
| `Geography` | Categorical | Country of residence |
| `EstimatedSalary` | Numeric | **Target variable to be predicted** |

---

## ⚙️ Installation

### 1. Clone the repository
```bash
git clone (https://github.com/pkamalprasath/GenAI_Engineer/)
cd GenAI_Engineer

### 2. Create a virtual environment (Optional)
python -m venv venv
source venv/bin/activate    # macOS / Linux
venv\Scripts\activate       # Windows

### 3. Install dependencies
pip install -r requirements.txt

## Model Training Pipeline

The regression pipeline includes:
Reading and exploring the dataset
Preprocessing
Label Encoding (Gender)
One-Hot Encoding (Geography)
Standardizing numerical features
Train/Test split
Model development
TensorFlow/Keras Sequential model
Model saving
model.save('regression_model.h5')
Save encoders and scaler using pickle
To reproduce the model training, open:

Regression_problem.ipynb

### Running the Streamlit App
Run the following command:
streamlit run streamlit_regression.py

This will open a local URL (e.g., http://localhost:8501 ) where you can:
Select Geography and Gender
Enter numeric values
Predict Estimated Salary in real-time

### Technologies Used

Python 3.10+
TensorFlow / Keras
scikit-learn
NumPy, Pandas
Streamlit
Pickle
