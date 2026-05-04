from sqlalchemy import create_engine, text

from wm_prediction.config import DATABASE_URL


def get_engine():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Check your .env file.")

    return create_engine(DATABASE_URL)


def check_database_connection() -> bool:
    engine = get_engine()

    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return result.scalar() == 1