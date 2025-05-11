from app import app, db, User, Account
from werkzeug.security import generate_password_hash

# Create tables
with app.app_context():
    print("Creating database tables...")
    db.drop_all()  # Drop all existing tables first
    db.create_all()
    
    # Create default user
    print("Creating default user...")
    user = User(
        username='rahulann',
        password_hash=generate_password_hash('annrahul2024')
    )
    db.session.add(user)
    db.session.commit()
    
    # Create default accounts
    print("Creating default accounts...")
    accounts = [
        "Current Account",
        "Savings Account",
        "Credit Card",
        "Investment Account",
        "Retirement Account",
        "Business Account",
        "Loan Account"
    ]
    
    for account_name in accounts:
        account = Account(
            name=account_name,
            user_id=user.id
        )
        db.session.add(account)
    
    db.session.commit()
    
    print("Database initialization complete!") 