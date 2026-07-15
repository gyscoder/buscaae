from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog
import os
from dotenv import load_dotenv
from app.dork_builder import build_dork
from app.models import SearchParams
from app.search_client import search

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Book Dork Search API",
    version="1.0.0",
    description="Open-source API for searching public book documents using advanced search operators"
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration - more secure than allowing all origins
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure properly in production
)

app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


@app.get("/")
async def root():
    return {"status": "online", "service": "Book Dork Search API"}


@app.post("/search")
@limiter.limit(f"{os.getenv('RATE_LIMIT_REQUESTS', '100')}/{os.getenv('RATE_LIMIT_WINDOW', '60')}seconds")
async def search_books(request: Request, params: SearchParams):
    """
    Search for books using advanced search operators (Google Dorks).

    Parameters:
    - title: Book title to search for
    - author: Author name
    - publisher: Publisher name
    - year: Publication year
    - filetypes: List of file types (pdf, epub, mobi)
    - site: Specific site to search (e.g., archive.org)
    - frase: Exact phrase to search for in text

    Returns:
    - Search results with metadata and preview information
    """
    try:
        logger.info("Search request received", params=params.dict())

        dork = build_dork(
            title=params.title,
            author=params.author,
            publisher=params.publisher,
            year=params.year,
            filetypes=params.filetypes,
            site=params.site,
            frase=params.frase
        )

        logger.debug("Generated dork", dork=dork)

        if not dork or dork.strip() == "books":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one search parameter must be provided"
            )

        data = await search(dork)

        logger.info(
            "Search completed",
            query=dork,
            results_count=data.get("total", 0),
            results_returned=len(data.get("results", []))
        )

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Search failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search operation failed"
        )