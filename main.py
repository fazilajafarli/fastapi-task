import os
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database.config import SessionLocal
from database.models import User, Post
from auth.utils import hash_password, verify_password, create_access_token
from pydantic import BaseModel
import aiomcache
from auth.dependencies import get_current_user
from database.schemas import PostCreate 


# Load environment variables
SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")  
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Initialize FastAPI
app = FastAPI()

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Models for request validation
class UserSignup(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class PostCreate(BaseModel):
    text: str

# Root endpoint
@app.get("/")
def home():
    return {"message": "FastAPI App Running!"}

# Signup endpoint
@app.post("/signup")
def signup(user: UserSignup, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(email=user.email, hashed_password=hash_password(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully"}

# Login endpoint
@app.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if not existing_user or not verify_password(user.password, existing_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": existing_user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# AddPost endpoint
@app.post("/addpost")
def add_post(post: PostCreate, user_email: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(post.text.encode('utf-8')) > 1048576:  # Extra validation
        raise HTTPException(status_code=413, detail="Too large. Maximum allowed is 1MB.")
    new_post = Post(text=post.text, user_id=db.query(User).filter(User.email == user_email).first().id)
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return {"postID": new_post.id, "message": "Post created successfully"}

# GetPosts endpoint with caching
cache = aiomcache.Client("127.0.0.1", 11211)

@app.get("/getposts")
async def get_posts(user_email: str = Depends(get_current_user), db: Session = Depends(get_db)):
    cache_key = f"posts_{user_email}".encode()
    cached_data = await cache.get(cache_key)

    if cached_data:
        return {"posts": cached_data.decode()}  # Return cached data

    user = db.query(User).filter(User.email == user_email).first()
    posts = db.query(Post).filter(Post.user_id == user.id).all()
    posts_data = [{"id": p.id, "text": p.text} for p in posts]

    await cache.set(cache_key, str(posts_data).encode(), exptime=300)  # Cache for 5 minutes
    return {"posts": posts_data}

# DeletePost endpoint
@app.delete("/deletepost")
def delete_post(postID: int, user_email: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_email).first()
    post = db.query(Post).filter(Post.id == postID, Post.user_id == user.id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    db.delete(post)
    db.commit()
    return {"message": "Post deleted successfully"}