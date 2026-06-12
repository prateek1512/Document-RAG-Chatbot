# app/database/connection.py
# Sets up the MySQL database connection using SQLAlchemy.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Read the database URL from the environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)

# Create a session factory (each call to Session() gives a new session)
Session = sessionmaker(bind=engine)


# Base class that all our models will inherit from
class Base(DeclarativeBase):
    pass
