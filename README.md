# Personal Budget Tracker

A Flask-based personal budget tracking application with PostgreSQL database integration.

## Setup Instructions

1. Clone the repository
```bash
git clone <your-repository-url>
cd <repository-name>
```

2. Create a virtual environment and activate it
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
- Copy `.env.example` to `.env`
- Update the `DATABASE_URL` and `SECRET_KEY` in `.env`

5. Create PostgreSQL database
- Create a new database named `budget_db`
- Update the `DATABASE_URL` in `.env` if needed

6. Initialize the database
```python
from app import db
db.create_all()
```

7. Run the application
```bash
python app.py
```

## Railway Deployment

1. Create a new project on Railway
2. Connect your GitHub repository
3. Add PostgreSQL plugin
4. Set environment variables in Railway dashboard
5. Deploy! 