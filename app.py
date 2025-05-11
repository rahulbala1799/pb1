from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from dotenv import load_dotenv
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://rahul@localhost:5432/budget_db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    accounts = db.relationship('Account', backref='owner', lazy=True)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    files = db.relationship('UploadedFile', backref='account', lazy=True)
    transactions = db.relationship('Transaction', backref='account', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='file', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    posted_date = db.Column(db.Date, nullable=False)
    posted_account = db.Column(db.String(100), nullable=False)
    description1 = db.Column(db.String(500))
    description2 = db.Column(db.String(500))
    description3 = db.Column(db.String(500))
    debit_amount = db.Column(db.Float)
    credit_amount = db.Column(db.Float)
    balance = db.Column(db.Float)
    transaction_type = db.Column(db.String(50))  # posted currency, local currency
    category = db.Column(db.String(100))
    file_id = db.Column(db.Integer, db.ForeignKey('uploaded_file.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'posted_date': self.posted_date.strftime('%Y-%m-%d'),
            'posted_account': self.posted_account,
            'description1': self.description1,
            'description2': self.description2,
            'description3': self.description3,
            'debit_amount': self.debit_amount,
            'credit_amount': self.credit_amount,
            'balance': self.balance,
            'transaction_type': self.transaction_type,
            'category': self.category,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@login_required
def index():
    accounts = Account.query.filter_by(user_id=session['user_id']).all()
    return render_template('index.html', accounts=accounts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'rahulann' and password == 'annrahul2024':
            user = User.query.filter_by(username=username).first()
            if not user:
                # Create user if doesn't exist
                user = User(
                    username=username,
                    password_hash=generate_password_hash(password)
                )
                db.session.add(user)
                db.session.commit()
            
            session['user_id'] = user.id
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/accounts', methods=['GET'])
@login_required
def get_accounts():
    accounts = Account.query.filter_by(user_id=session['user_id']).all()
    return jsonify([{'id': a.id, 'name': a.name} for a in accounts])

@app.route('/accounts', methods=['POST'])
@login_required
def create_account():
    name = request.form.get('name')
    if not name:
        return jsonify({'error': 'Account name is required'}), 400
    
    account = Account(name=name, user_id=session['user_id'])
    db.session.add(account)
    db.session.commit()
    
    return jsonify({'message': 'Account created successfully', 'account_id': account.id})

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    account_id = request.form.get('account_id')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Only CSV files are allowed'}), 400
    
    if not account_id:
        return jsonify({'error': 'Account ID is required'}), 400
    
    account = Account.query.filter_by(id=account_id, user_id=session['user_id']).first()
    if not account:
        return jsonify({'error': 'Invalid account ID'}), 400
    
    # Save file details to database
    uploaded_file = UploadedFile(
        filename=file.filename,
        account_id=account_id,
        user_id=session['user_id']
    )
    db.session.add(uploaded_file)
    db.session.commit()
    
    # Process CSV file
    csv_content = file.read().decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(csv_content))
    
    transactions = []
    for row in csv_reader:
        try:
            transaction = Transaction(
                posted_date=datetime.strptime(row.get('Posted Date', ''), '%Y-%m-%d'),
                posted_account=row.get('Posted Account', ''),
                description1=row.get('Transaction Description', ''),
                description2=row.get('Description2', ''),
                description3=row.get('Description3', ''),
                debit_amount=float(row.get('Debit Amount', 0) or 0),
                credit_amount=float(row.get('Credit Amount', 0) or 0),
                balance=float(row.get('Balance', 0) or 0),
                transaction_type=row.get('Transaction Type', ''),
                file_id=uploaded_file.id,
                account_id=account_id
            )
            transactions.append(transaction)
        except Exception as e:
            print(f"Error processing row: {e}")
    
    if transactions:
        db.session.add_all(transactions)
        db.session.commit()
    
    return jsonify({
        'message': 'File uploaded successfully', 
        'file_id': uploaded_file.id,
        'transactions_count': len(transactions)
    })

@app.route('/transactions', methods=['GET'])
@login_required
def get_transactions():
    account_id = request.args.get('account_id')
    if not account_id:
        return jsonify({'error': 'Account ID is required'}), 400
    
    account = Account.query.filter_by(id=account_id, user_id=session['user_id']).first()
    if not account:
        return jsonify({'error': 'Invalid account ID'}), 400
    
    transactions = Transaction.query.filter_by(account_id=account_id).order_by(Transaction.posted_date.desc()).limit(100).all()
    return jsonify([t.to_dict() for t in transactions])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create default user if not exists
        user = User.query.filter_by(username='rahulann').first()
        if not user:
            user = User(
                username='rahulann',
                password_hash=generate_password_hash('annrahul2024')
            )
            db.session.add(user)
            db.session.commit()
    app.run(debug=True) 