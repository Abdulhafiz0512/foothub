import sqlalchemy as db
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

# Database setup
Base = declarative_base()
engine = db.create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def init_db():
    """Initialize database tables"""
    from models import User, Submission, Image

    Base.metadata.create_all(engine)