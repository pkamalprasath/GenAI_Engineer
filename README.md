# GenAI Engineer Portfolio

Welcome to my GenAI (Generative AI) Engineering repository! This repository showcases various AI/ML projects and implementations.

## 📂 Repository Structure

### 1. **open_claw_slack_bot/** - AI-Powered Slack Bot Assistant
Complete production-ready Slack bot with advanced AI capabilities:
- **Agent System**: LangGraph-based agent with 15+ tools
- **RAG (Retrieval-Augmented Generation)**: ChromaDB vector store for semantic search
- **MCP Integrations**: Slack, GitHub, and Notion integrations
- **Memory Management**: Long-term and short-term memory systems
- **Production Features**: Comprehensive testing, logging, security

📖 [View Full Documentation](open_claw_slack_bot/README.md) | [Quick Start Guide](open_claw_slack_bot/QUICK_START.md)

### 2. **NLP/** - Natural Language Processing Projects

#### **NLP/ANN/Classification**
- Neural network classification with Keras
- Customer churn prediction model
- Streamlit web interface for predictions
- Label encoding and feature scaling

#### **NLP/ANN/Regression**
- Neural network regression models
- Advanced preprocessing pipelines
- Interactive Streamlit dashboard

#### **NLP/SimpleRNN**
- Simple RNN implementation for sequence prediction
- IMDB sentiment analysis
- Word embeddings and text classification

### 3. **basics/nlp/** - NLP Fundamentals

#### **Text Preprocessing**
- Tokenization with NLTK
- Stemming and Lemmatization
- Stop words removal
- Part-of-Speech tagging
- Named Entity Recognition (NER)

#### **Word Embeddings**
- Bag of Words (BoW)
- N-Grams
- TF-IDF vectorization
- Word2Vec implementation

---

## 🚀 Featured Project: Open Claw Slack Bot

The **open_claw_slack_bot** is the flagship project in this repository, featuring:

### Key Features
- **Conversational AI**: Powered by Anthropic's Claude 3.5 Sonnet
- **Multi-Channel Support**: Works across Slack channels with context awareness
- **Smart Memory**: Remembers conversations and user preferences
- **Task Automation**: Set reminders, create GitHub issues, manage Notion pages
- **Semantic Search**: Find relevant information from message history
- **Production Ready**: 11/11 tests passing, comprehensive error handling

### Tech Stack
- **Backend**: Python 3.11+, FastAPI
- **AI/ML**: LangGraph, Anthropic Claude, ChromaDB
- **Integrations**: Slack Bolt, FastMCP
- **Storage**: SQLite (dev), PostgreSQL (prod)
- **Testing**: pytest, 100% core coverage

### Quick Links
- [Architecture Documentation](open_claw_slack_bot/docs/architecture/ARCHITECTURE.md)
- [API Documentation](open_claw_slack_bot/docs/guides/GUIDE.md)
- [Testing Guide](open_claw_slack_bot/docs/guides/E2E_TESTING_GUIDE.md)
- [Security Practices](open_claw_slack_bot/docs/security/SECURITY.md)

---

## 📊 Skills Demonstrated

### Machine Learning & AI
- Deep Learning (ANNs, RNNs)
- Natural Language Processing
- Agent-based systems
- Vector databases and embeddings
- RAG (Retrieval-Augmented Generation)

### Software Engineering
- Production-grade Python development
- RESTful API design
- Microservices architecture
- Testing (unit, integration, E2E)
- CI/CD and deployment

### Tools & Frameworks
- **AI/ML**: TensorFlow, Keras, LangGraph, ChromaDB
- **NLP**: NLTK, spaCy, Transformers
- **Backend**: FastAPI, Slack Bolt, FastMCP
- **Testing**: pytest, unittest, mock
- **DevOps**: Git, Docker (planned)

---

## 🎓 Learning Journey

This repository represents my journey in GenAI engineering, covering:

1. **Fundamentals**: Text preprocessing, embeddings, basic NLP
2. **Deep Learning**: Neural networks for classification and regression
3. **Advanced AI**: Agent systems, RAG, production AI applications
4. **Best Practices**: Testing, documentation, security, scalability

---

## 🔧 Getting Started

### Open Claw Slack Bot
```bash
cd open_claw_slack_bot
pip install -r pyproject.toml
# Follow QUICK_START.md for setup
python src/main.py
```

### NLP Projects
```bash
cd NLP/ANN/Classification
pip install -r requirements.txt
streamlit run streamlit_classification.py
```

### Text Preprocessing Basics
```bash
cd basics/nlp/text_preprocessing
jupyter notebook
# Open any .ipynb file
```

---

## 📚 Documentation

Each project includes:
- **README**: Project overview and features
- **Requirements**: Dependencies and versions
- **Notebooks**: Interactive Jupyter notebooks for exploration
- **Code**: Well-documented source code

The **open_claw_slack_bot** includes extensive documentation:
- Complete architecture diagrams
- API reference guides
- Testing strategies
- Deployment guides
- Security best practices

---

## 🤝 Contributing

This is primarily a learning and portfolio repository. However, feedback and suggestions are welcome!

### For the Slack Bot Project
See [Contributing Guidelines](open_claw_slack_bot/README.md#contributing)

---

## 📧 Contact

**Kamal Prasath**
- GitHub: [@pkamalprasath](https://github.com/pkamalprasath)
- Email: pkamalprasath@gmail.com

---

## 📝 License

Individual projects may have different licenses. Please check each project directory for specific license information.

The **open_claw_slack_bot** is available under MIT License (see [LICENSE](open_claw_slack_bot/LICENSE) if added).

---

## ⭐ Highlights

### Production-Ready AI Bot
The **open_claw_slack_bot** demonstrates:
- Professional software architecture
- Comprehensive testing (11/11 passing)
- Security best practices
- Production-grade error handling
- Complete documentation

### Learning Portfolio
Projects progress from basics to advanced:
- Text preprocessing fundamentals ➔ Deep learning ➔ Production AI systems
- Theory ➔ Implementation ➔ Deployment
- Notebooks ➔ Scripts ➔ Full applications

---

**Last Updated**: 2026-02-18
**Status**: Active Development ✅

---

**Explore the projects and happy learning!** 🚀
