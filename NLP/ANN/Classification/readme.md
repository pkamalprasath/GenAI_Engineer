# 📈 Regression Model – Estimated Salary Prediction

This project builds and deploys an **Artificial Neural Network (ANN)** classifier to predict **Customer Churn** (Exited/Not Exited) based on banking customer data.

The solution includes:

- Full machine learning preprocessing  
- ANN model training (TensorFlow/Keras)  
- Saving encoders and scalers  
- A fully interactive **Streamlit app** for real-time churn prediction  

## 🚀 Project Overview

The goal of this project is to predict **whether a customer will churn (Exit)** based on personal, financial, and account-related features.

This includes:

- Data Loading & Cleaning  
- Encoding categorical features  
- Scaling numerical features  
- Building a deep learning classifier  
- Model evaluation  
- Saving the trained model  
- Deploying with Streamlit  
---

## 📂 Project Structure

Classification/
│── churn_model.h5 # Trained ANN classification model
│── scaler.pkl # StandardScaler used during training
│── label_encoder_gender.pkl # LabelEncoder for Gender
│── onehot_encoder_geo.pkl # OneHotEncoder for Geography
│── streamlit_churn_app.py # Streamlit web app
│── churn_training.ipynb # Notebook used for training the ANN
│── dataset.csv # Input dataset
│── requirements.txt # Dependencies
└── README.md # Project documentation

## 📊 Dataset Description

The dataset contains customer information commonly used in churn prediction tasks.

| Column | Description |
|--------|-------------|
| `CreditScore` | Customer credit score |
| `Geography` | Country (France, Germany, Spain) |
| `Gender` | Male/Female |
| `Age` | Customer age |
| `Tenure` | Years with the bank |
| `Balance` | Account balance |
| `NumOfProducts` | # of banking products used |
| `HasCrCard` | Credit card status (0/1) |
| `IsActiveMember` | Active customer (0/1) |
| `EstimatedSalary` | Annual salary |
| `Exited` | **Target variable** (1 = churned, 0 = retained) |

---

## 🧠 Model Architecture (ANN)

The neural network includes:

- Input layer  
- Two or more Dense (fully-connected) hidden layers  
- ReLU activation  
- Dropout (optional)  
- Sigmoid output for binary classification  

The model is trained using:

- **Binary Crossentropy loss**
- **Adam optimizer**
- **Accuracy** as the performance metric

---

## ⚙️ Preprocessing Steps

### 1. **Encoding**
- Label Encoding for `Gender`
- One-Hot Encoding for `Geography`

### 2. **Feature Scaling**
We use `StandardScaler` on numerical columns:

- CreditScore  
- Age  
- Tenure  
- Balance  
- NumOfProducts  
- EstimatedSalary  

The scaler is saved as:


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

classification_problem.ipynb

### Running the Streamlit App
Run the following command:
streamlit run streamlit_classification.py

### Example Prediction Output
Churn Probability: 0.78
The customer is likely to churn.
### Technologies Used

Python 3.10+
TensorFlow / Keras
scikit-learn
NumPy, Pandas
Streamlit
Pickle
