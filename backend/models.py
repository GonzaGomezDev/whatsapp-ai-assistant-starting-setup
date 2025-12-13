from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path='.env.development')  # Load environment variables from a .env file (optional)

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

url = URL.create(
    drivername=os.getenv("DB_DRIVER", "postgresql+psycopg2"),
    username=db_user,
    password=db_password,
    host=db_host,
    port=int(db_port) if db_port else None,
    database=db_name,
)

# Ensure UTF-8 client encoding for psycopg2. Useful for spanish characters on Windows.
engine = create_engine(url, connect_args={"options": "-c client_encoding=UTF8"}, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    _from = Column(String(50), nullable=False)
    _to = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(String(50), nullable=False)
    message_type = Column(String(20), nullable=False)

try:
    Base.metadata.create_all(bind=engine)
except UnicodeDecodeError as e:
    # Provide actionable guidance for common Windows encoding pitfalls
    raise RuntimeError(
        "UnicodeDecodeError while connecting to the database."
    ) from e