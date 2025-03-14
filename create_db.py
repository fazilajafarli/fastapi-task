from database.config import engine, Base
from database.models import User, Post

print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("Tables created successfully!")