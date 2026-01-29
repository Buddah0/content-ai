from sqlalchemy import create_engine
from content_ai.api.db_models import Base

# Ensure we use the same DB file as other parts
engine = create_engine("sqlite:///content_ai.db")
print("Creating tables...")
Base.metadata.create_all(engine)
print("Tables created.")
