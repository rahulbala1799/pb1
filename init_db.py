from app import app, db, User
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
    
    print("Database initialization complete!") 