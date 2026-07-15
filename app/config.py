import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Configuration
    API_TITLE: str = os.getenv("API_TITLE", "Book Dork Search API")
    API_VERSION: str = os.getenv("API_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # CORS Configuration
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

    # Search Configuration
    DDGS_TIMEOUT: int = int(os.getenv("DDGS_TIMEOUT", "10"))
    OPENLIBRARY_TIMEOUT: int = int(os.getenv("OPENLIBRARY_TIMEOUT", "8"))
    ARCHIVE_TIMEOUT: int = int(os.getenv("ARCHIVE_TIMEOUT", "8"))
    MAX_RESULTS_PER_SOURCE: int = int(os.getenv("MAX_RESULTS_PER_SOURCE", "10"))
    MAX_PREVIEW_RESULTS: int = int(os.getenv("MAX_PREVIEW_RESULTS", "5"))

    # Cache Configuration
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes
    CACHE_MAXSIZE: int = int(os.getenv("CACHE_MAXSIZE", "100"))

    # HTTP Configuration
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "10"))
    PREVIEW_TIMEOUT: int = int(os.getenv("PREVIEW_TIMEOUT", "5"))

    # File Types
    DEFAULT_FILETYPES: List[str] = os.getenv("DEFAULT_FILETYPES", "pdf,epub,mobi").split(",")

    # Keywords for content analysis
    BOOK_KEYWORDS: List[str] = os.getenv("BOOK_KEYWORDS", "book,livro,ebook,pdf,epub,mobi").split(",")

# Global config instance
config = Config()