import httpx
import asyncio
import re
import structlog
import time
from ddgs import DDGS
from urllib.parse import quote, urlparse, urlunparse
from typing import List, Dict, Any, Optional
from app.config import config

# Configure structured logging
logger = structlog.get_logger()

# Headers configuration
headers = {
    "User-Agent": getattr(config, 'USER_AGENT', "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
}

# Simple in-memory cache (in production, consider Redis)
_search_cache = {}
_search_cache_timestamps = {}

def _get_from_cache(key: str) -> Optional[Any]:
    """Get item from cache if not expired"""
    if not getattr(config, 'CACHE_ENABLED', True):
        return None

    if key in _search_cache:
        if time.time() - _search_cache_timestamps[key] < getattr(config, 'CACHE_TTL', 300):
            return _search_cache[key]
        else:
            # Remove expired entry
            del _search_cache[key]
            del _search_cache_timestamps[key]
    return None

def _save_to_cache(key: str, value: Any) -> None:
    """Save item to cache"""
    if not getattr(config, 'CACHE_ENABLED', True):
        return

    _search_cache[key] = value
    _search_cache_timestamps[key] = time.time()

    # Simple cleanup if cache gets too large
    max_size = getattr(config, 'CACHE_MAXSIZE', 100)
    if len(_search_cache) > max_size:
        # Remove oldest entry
        oldest_key = min(_search_cache_timestamps, key=_search_cache_timestamps.get)
        del _search_cache[oldest_key]
        del _search_cache_timestamps[oldest_key]

def extract_drive_info(url: str) -> Optional[Dict[str, str]]:
    """Extract Google Drive file/folder ID from URL"""
    patterns = [
        (r"/file/d/([^/]+)", "file"),
        (r"/drive/folders/([^/?]+)", "folder"),
        (r"id=([^&]+)", "file")
    ]

    for pattern, tipo in patterns:
        match = re.search(pattern, url)
        if match:
            return {
                "id": match.group(1),
                "type": tipo
            }
    return None

def fix_archive_url(url: str) -> str:
    """Fix archive.org URL encoding issues"""
    try:
        parsed = urlparse(url)

        # pega o caminho e corrige +
        path = parsed.path.replace("+", " ")

        # encode correto (preserva /)
        fixed_path = quote(path, safe="/")

        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            fixed_path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
    except Exception as e:
        logger.error("Fix archive error", error=str(e), url=url)
        return url

async def get_archive_files(identifier: str) -> List[Dict[str, str]]:
    """Fetch file list from Internet Archive metadata"""
    try:
        url = f"https://archive.org/metadata/{identifier}"

        async with httpx.AsyncClient(
            headers=headers,
            timeout=getattr(config, 'ARCHIVE_TIMEOUT', 8)
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        files = data.get("files", [])

        results = []
        for f in files:
            name = f.get("name", "")

            if name.endswith((".pdf", ".epub", ".mobi")):
                file_url = f"https://archive.org/download/{identifier}/{quote(name)}"

                results.append({
                    "name": name,
                    "url": file_url
                })

        return results

    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP error fetching archive files",
            identifier=identifier,
            status_code=e.response.status_code
        )
        return []
    except Exception as e:
        logger.error("File fetch error", identifier=identifier, error=str(e), exc_info=True)
        return []

def normalize_url(url: str) -> str:
    """Normalize URL by fixing archive.org encoding"""
    if "archive.org" in url:
        return fix_archive_url(url)
    return url

def detect_google_drive(url: str) -> Dict[str, Any]:
    """Detect and extract Google Drive information"""
    result = {
        "is_drive": False,
        "drive_type": None,
        "is_drive_folder": False,
        "is_drive_file": False,
        "drive_preview": None,
        "drive_download": None,
        "drive_folder": None
    }

    if "drive.google.com" in url:
        result["is_drive"] = True
        info = extract_drive_info(url)

        if info:
            file_id = info["id"]
            tipo = info["type"]

            result["drive_type"] = tipo
            result["is_drive_folder"] = (tipo == "folder")
            result["is_drive_file"] = (tipo == "file")

            if tipo == "file":
                result["drive_preview"] = f"https://drive.google.com/file/d/{file_id}/preview"
                result["drive_download"] = f"https://drive.google.com/uc?export=download&id={file_id}"
            elif tipo == "folder":
                result["drive_folder"] = f"https://drive.google.com/drive/folders/{file_id}"

    return result

def analyze_content_type(result: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze content to determine if it's a book/pdf/etc."""
    url = (result.get("url") or "").lower()
    title = (result.get("title") or "").lower()

    # Check if it's a book-related result
    book_keywords = getattr(config, 'BOOK_KEYWORDS', ["book", "livro", "ebook", "pdf", "epub", "mobi"])
    is_book = any(
        keyword in title or keyword in url
        for keyword in book_keywords
    )

    # Check file types
    is_pdf = url.endswith(".pdf") or ".pdf" in url
    is_epub = ".epub" in url
    is_mobi = ".mobi" in url

    return {
        "is_book": is_book,
        "is_pdf": is_pdf,
        "is_epub": is_epub,
        "is_mobi": is_mobi
    }

def analyze_result(r: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze and enrich a search result"""
    # Make a copy to avoid modifying original
    result = r.copy()

    # Normalize URL
    url = result.get("url", "")
    result["url"] = normalize_url(url)

    # Fix download URL if present
    if result.get("download"):
        result["download"] = normalize_url(result["download"])

    # Fix file URLs if present
    if result.get("files"):
        for f in result["files"]:
            if f.get("url"):
                f["url"] = normalize_url(f["url"])

    # Add Google Drive information
    result.update(detect_google_drive(result["url"]))

    # Add content analysis
    result.update(analyze_content_type(result))

    return result

async def ddg_search(query: str) -> List[Dict[str, Any]]:
    """Search using DuckDuckGo with multiple dork variations"""
    # Check cache first
    cache_key = f"ddg:{query}"
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        logger.debug("Returning cached DDG results", query=query)
        return cached_result

    try:
        def _ddg_sync(query: str) -> List[Dict[str, Any]]:
            results = []

            # Generate dork variations
            dorks = [
                query,
                f"{query} pdf",
                f"{query} epub",
                f"{query} filetype:pdf"
            ]

            with DDGS() as ddgs:
                for dork in dorks:
                    try:
                        for r in ddgs.text(dork, max_results=getattr(config, 'MAX_RESULTS_PER_SOURCE', 5)):
                            results.append({
                                "title": r.get("title"),
                                "url": r.get("href"),
                                "snippet": r.get("body"),
                                "source": "duckduckgo"
                            })
                    except Exception as e:
                        logger.warning(
                            "DDG search failed for dork",
                            dork=dork,
                            error=str(e)
                        )
                        continue

            return results

        # Run in thread to avoid blocking
        results = await asyncio.to_thread(_ddg_sync, query)

        # Cache results
        _save_to_cache(cache_key, results)

        logger.debug("DDG search completed", query=query, results_count=len(results))
        return results

    except Exception as e:
        logger.error("DDG search failed", query=query, error=str(e), exc_info=True)
        return []

async def openlibrary_search(query: str) -> List[Dict[str, Any]]:
    """Search OpenLibrary for book metadata"""
    # Check cache first
    cache_key = f"openlibrary:{query}"
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        logger.debug("Returning cached OpenLibrary results", query=query)
        return cached_result

    try:
        url = "https://openlibrary.org/search.json"

        async with httpx.AsyncClient(
            headers=headers,
            timeout=getattr(config, 'OPENLIBRARY_TIMEOUT', 8)
        ) as client:
            response = await client.get(url, params={"q": query})
            response.raise_for_status()
            data = response.json()

        results = []
        for doc in data.get("docs", [])[:getattr(config, 'MAX_RESULTS_PER_SOURCE', 10)]:
            if "key" in doc:
                results.append({
                    "title": doc.get("title"),
                    "url": f"https://openlibrary.org{doc['key']}",
                    "author": (doc.get("author_name") or [None])[0],
                    "year": doc.get("first_publish_year"),
                    "source": "openlibrary"
                })

        # Cache results
        _save_to_cache(cache_key, results)

        logger.debug("OpenLibrary search completed", query=query, results_count=len(results))
        return results

    except httpx.HTTPStatusError as e:
        logger.error(
            "OpenLibrary HTTP error",
            query=query,
            status_code=e.response.status_code
        )
        return []
    except Exception as e:
        logger.error("OpenLibrary search failed", query=query, error=str(e), exc_info=True)
        return []

async def archive_search(query: str) -> List[Dict[str, Any]]:
    """Search Internet Archive for books in PDF/EPUB format"""
    # Check cache first
    cache_key = f"archive:{query}"
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        logger.debug("Returning cached Archive results", query=query)
        return cached_result

    try:
        url = "https://archive.org/advancedsearch.php"

        params = [
            ("q", f'({query}) AND mediatype:texts AND (format:pdf OR format:epub)'),
            ("fl[]", "identifier"),
            ("fl[]", "title"),
            ("fl[]", "creator"),
            ("fl[]", "year"),
            ("rows", str(getattr(config, 'MAX_RESULTS_PER_SOURCE', 10) * 2)),  # Get more to account for filtering
            ("output", "json")
        ]

        async with httpx.AsyncClient(
            headers=headers,
            timeout=getattr(config, 'ARCHIVE_TIMEOUT', 8)
        ) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        results = []
        docs = data.get("response", {}).get("docs", [])

        # Process documents in parallel for file fetching
        tasks = [
            get_archive_files(d.get("identifier"))
            for d in docs[:getattr(config, 'MAX_RESULTS_PER_SOURCE', 10)]
            if d.get("identifier") and d.get("title")
        ]

        files_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, (d, files_list) in enumerate(zip(docs[:getattr(config, 'MAX_RESULTS_PER_SOURCE', 10)], files_lists)):
            if not isinstance(d, dict) or not isinstance(files_list, list):
                continue

            identifier = d.get("identifier")
            title = d.get("title")

            if not identifier or not title:
                continue

            # Get the best file (first PDF/EPUB/MOBI found)
            download = None
            for f in files_list:
                if isinstance(f, dict) and f.get("url", "").endswith((".pdf", ".epub", ".mobi")):
                    download = f["url"]
                    break

            # If no direct file found, use first file if available
            if not download and files_list and isinstance(files_list[0], dict):
                download = files_list[0].get("url")

            result = {
                "title": title,
                "url": f"https://archive.org/details/{identifier}",
                "collection": f"https://archive.org/download/{identifier}",
                "download": download,
                "files": files_list[:5] if isinstance(files_list, list) else [],
                "author": d.get("creator"),
                "year": d.get("year"),
                "source": "archive"
            }

            results.append(result)

        # Cache results
        _save_to_cache(cache_key, results)

        logger.debug("Archive search completed", query=query, results_count=len(results))
        return results

    except httpx.HTTPStatusError as e:
        logger.error(
            "Archive HTTP error",
            query=query,
            status_code=e.response.status_code
        )
        return []
    except Exception as e:
        logger.error("Archive search failed", query=query, error=str(e), exc_info=True)
        return []

async def fetch_preview(url: str) -> Dict[str, Optional[str]]:
    """Fetch preview information (title, description) from a URL"""
    try:
        timeout = httpx.Timeout(getattr(config, 'PREVIEW_TIMEOUT', 3.0))
        async with httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            follow_redirects=True
        ) as client:
            response = await client.get(url)

            # Avoid downloading large files (PDFs, binaries)
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return {}

            html = response.text[:3000]  # Limit to first 3000 chars

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        desc_match = re.search(
            r'<meta name="description" content="(.*?)"',
            html,
            re.IGNORECASE
        )

        return {
            "preview_title": title_match.group(1).strip() if title_match else None,
            "preview_desc": desc_match.group(1).strip() if desc_match else None
        }

    except httpx.ReadTimeout:
        # timeout is normal, don't clutter logs
        return {}
    except Exception as e:
        logger.error("Preview error", url=url, error=str(e), exc_info=True)
        return {}

async def search(query: str) -> Dict[str, Any]:
    """Main search function that aggregates results from all sources"""
    # Check cache first
    cache_key = f"search:{query}"
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        logger.debug("Returning cached search results", query=query)
        return cached_result

    try:
        # Execute searches in parallel
        ddg_task = ddg_search(query)
        openlib_task = openlibrary_search(query)
        archive_task = archive_search(query)

        ddg, openlib, archive = await asyncio.gather(
            ddg_task,
            openlib_task,
            archive_task,
            return_exceptions=True
        )

        # Handle exceptions gracefully
        ddg = ddg if isinstance(ddg, list) else []
        openlib = openlib if isinstance(openlib, list) else []
        archive = archive if isinstance(archive, list) else []

        # Log any errors that occurred
        if isinstance(ddg, Exception):
            logger.error("DDG search task failed", error=str(ddg))
        if isinstance(openlib, Exception):
            logger.error("OpenLibrary search task failed", error=str(openlib))
        if isinstance(archive, Exception):
            logger.error("Archive search task failed", error=str(archive))

        # Limit results from each source
        max_per_source = getattr(config, 'MAX_RESULTS_PER_SOURCE', 10)
        merged = ddg[:max_per_source] + openlib[:max_per_source] + archive[:max_per_source]

        # Remove duplicates
        seen = set()
        unique = []
        for r in merged:
            url = (r.get("url") or "").strip()
            if url and url not in seen:
                seen.add(url)
                unique.append(r)

        # Analyze results
        analyzed = [analyze_result(r) for r in unique]

        # Get preview targets (non-binary, non-drive, non-archive direct download)
        max_preview = getattr(config, 'MAX_PREVIEW_RESULTS', 5)
        preview_targets = [
            r for r in analyzed
            if r.get("url")
            and not r.get("is_pdf")
            and "drive.google.com" not in r.get("url", "")
            and "archive.org/download" not in r.get("url", "")
        ][:max_preview]

        # Fetch previews in parallel
        if preview_targets:
            preview_tasks = [fetch_preview(r["url"]) for r in preview_targets]
            previews = await asyncio.gather(*preview_tasks, return_exceptions=True)

            # Apply previews to results
            for r, p in zip(preview_targets, previews):
                if isinstance(p, dict):
                    r.update(p)
                elif isinstance(p, Exception):
                    logger.error("Preview task failed", url=r.get("url"), error=str(p))

        # Prepare final response
        result = {
            "query": query,
            "total": len(analyzed),
            "results": analyzed
        }

        # Cache results
        _save_to_cache(cache_key, result)

        logger.info(
            "Search completed",
            query=query,
            total_results=len(analyzed),
            ddg_results=len(ddg),
            openlib_results=len(openlib),
            archive_results=len(archive)
        )

        return result

    except Exception as e:
        logger.error("Search failed", query=query, error=str(e), exc_info=True)
        # Return empty result rather than crashing
        return {
            "query": query,
            "total": 0,
            "results": []
        }