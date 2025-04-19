from app import create_app, db
from app.models import User

app = create_app()

@app.cli.command("create-admin")
def create_admin():
    """Create an admin user"""
    username = input("Enter admin username: ")
    email = input("Enter admin email: ")
    password = input("Enter admin password: ")
    
    user = User(username=username, email=email, password=password, is_admin=True)
    db.session.add(user)
    db.session.commit()
    print(f"Admin user {username} created successfully!")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
