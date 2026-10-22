
import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv(
    "MONGODB_DATABASE",
    "classroom_simulation",
)

_client: MongoClient | None = None


def get_mongodb_client() -> MongoClient:
    """Create and reuse the MongoDB client."""
    global _client

    if _client is None:
        if not MONGODB_URI:
            raise RuntimeError(
                "MONGODB_URI is missing. Configure it in the project .env file."
            )

        _client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=10000,
        )

    return _client


def get_mongodb_database():
    """Return the configured application database."""
    return get_mongodb_client()[MONGODB_DATABASE]


def check_mongodb_connection() -> dict[str, str]:
    """Ping MongoDB and return a safe status message."""
    try:
        get_mongodb_client().admin.command("ping")
        return {"status": "connected"}
    except (PyMongoError, RuntimeError):
        return {"status": "disconnected"}


def close_mongodb_connection() -> None:
    """Close the client when the application shuts down."""
    global _client

    if _client is not None:
        _client.close()
        _client = None
