from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from dotenv import load_dotenv
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io
import traceback

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
    posted_date = db.Column(db.Date, nullable=True)  # Changed to nullable
    posted_account = db.Column(db.String(100), nullable=True)  # Changed to nullable
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
            'posted_date': self.posted_date.strftime('%Y-%m-%d') if self.posted_date else None,
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

# Parse date with multiple possible formats
def parse_date(date_str):
    if not date_str or date_str.strip() == '':
        return None
        
    date_formats = [
        '%Y-%m-%d',   # 2023-01-15
        '%d/%m/%Y',   # 15/01/2023
        '%m/%d/%Y',   # 01/15/2023
        '%d-%m-%Y',   # 15-01-2023
        '%d-%b-%Y',   # 15-Jan-2023
        '%d %b %Y',   # 15 Jan 2023
        '%b %d, %Y',  # Jan 15, 2023
        '%d.%m.%Y',   # 15.01.2023
        '%Y/%m/%d'    # 2023/01/15
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    return None

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
    
    # Read and process CSV file
    try:
        # Process CSV file
        csv_content = file.read().decode('utf-8')
        csv_file = io.StringIO(csv_content)
        
        # Try to determine dialect
        sample = csv_file.read(1024)
        csv_file.seek(0)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        has_header = sniffer.has_header(sample)
        
        transactions = []
        
        if has_header:
            reader = csv.DictReader(csv_file, dialect=dialect)
            for row in reader:
                transactions.extend(process_row(row, uploaded_file.id, account_id))
        else:
            # If no header, fall back to default processing
            reader = csv.reader(csv_file, dialect=dialect)
            headers = next(reader, None)  # Skip first row
            for row in reader:
                row_dict = dict(zip(headers, row))
                transactions.extend(process_row(row_dict, uploaded_file.id, account_id))
        
        if transactions:
            db.session.add_all(transactions)
            db.session.commit()
        
        return jsonify({
            'message': 'File uploaded successfully', 
            'file_id': uploaded_file.id,
            'transactions_count': len(transactions)
        })
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error processing CSV: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({'error': f'Error processing CSV: {str(e)}'}), 500

def process_row(row, file_id, account_id):
    """Process a CSV row and return one or more Transaction objects"""
    transactions = []
    
    # Log the column names we received
    app.logger.info(f"CSV columns: {list(row.keys())}")
    
    try:
        # Attempt to normalize column names
        normalized_row = {}
        for key, value in row.items():
            if key:  # Skip empty keys
                normalized_key = key.lower().strip().replace(' ', '_')
                normalized_row[normalized_key] = value
        
        # Create a mapping for common column names
        date_fields = ['date', 'posted_date', 'transaction_date', 'posting_date']
        account_fields = ['account', 'posted_account', 'account_number']
        description_fields = ['description', 'transaction_description', 'details', 'narrative']
        debit_fields = ['debit', 'debit_amount', 'withdrawal', 'amount_out']
        credit_fields = ['credit', 'credit_amount', 'deposit', 'amount_in']
        balance_fields = ['balance', 'running_balance', 'current_balance']
        
        # Extract values using potential column names
        date_str = find_first_value(normalized_row, date_fields)
        account_name = find_first_value(normalized_row, account_fields)
        description = find_first_value(normalized_row, description_fields)
        
        debit_str = find_first_value(normalized_row, debit_fields)
        credit_str = find_first_value(normalized_row, credit_fields)
        balance_str = find_first_value(normalized_row, balance_fields)
        
        # Handle case where there's a single amount column with positive/negative values
        amount_str = find_first_value(normalized_row, ['amount', 'value', 'transaction_amount'])
        if amount_str and not (debit_str or credit_str):
            try:
                amount = float(amount_str.replace(',', ''))
                if amount < 0:
                    debit_str = str(abs(amount))
                    credit_str = '0'
                else:
                    credit_str = str(amount)
                    debit_str = '0'
            except (ValueError, TypeError):
                pass
        
        # Parse numerical values
        debit_amount = parse_float(debit_str)
        credit_amount = parse_float(credit_str)
        balance = parse_float(balance_str)
        
        # Create the transaction
        transaction = Transaction(
            posted_date=parse_date(date_str),
            posted_account=account_name,
            description1=description,
            description2=row.get('Description2', ''),
            description3=row.get('Description3', ''),
            debit_amount=debit_amount,
            credit_amount=credit_amount,
            balance=balance,
            transaction_type=row.get('Transaction Type', ''),
            file_id=file_id,
            account_id=account_id
        )
        transactions.append(transaction)
        
    except Exception as e:
        app.logger.error(f"Error processing row: {str(e)}")
        app.logger.error(f"Row data: {row}")
    
    return transactions

def find_first_value(row_dict, possible_keys):
    """Find the first non-empty value from a list of possible keys"""
    for key in possible_keys:
        for col in row_dict:
            if key in col.lower():
                value = row_dict[col]
                if value and value.strip():
                    return value
    return None

def parse_float(value_str):
    """Parse a string to float, handling various formats"""
    if not value_str or not isinstance(value_str, str):
        return 0.0
    
    # Remove currency symbols, commas, etc.
    clean_value = value_str.replace('$', '').replace('£', '').replace('€', '').replace(',', '')
    clean_value = clean_value.replace('(', '-').replace(')', '')
    
    try:
        return float(clean_value)
    except (ValueError, TypeError):
        return 0.0

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