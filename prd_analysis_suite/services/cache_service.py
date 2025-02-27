import pickle
import logging
import re
import glob
from pathlib import Path
from typing import Union, Any, List, Optional
from config import CACHE_DIR

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# File & Cache Helpers
# ----------------------------------------------------------------------
def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename with unsafe characters replaced by underscores
    """
    # Replace periods and other unsafe characters with underscores and convert to lowercase
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", filename)
    return sanitized.lower()  # Always use lowercase for consistency

def extract_version_from_filename(filename: str) -> str:
    """
    Extract version number from filename.

    Args:
        filename: Filename to extract version from

    Returns:
        Extracted version string (e.g., "v10")
    """
    # e.g., V10_PRD.html, v9_prd_something, etc.
    pattern = re.compile(r'[Vv]([0-9]+)', re.IGNORECASE)
    match = pattern.search(filename)
    if match:
        return f"v{match.group(1)}"  # Return lowercase 'v' for consistency
    else:
        return "v??"  # fallback if not found

def get_cache_path(filename: str) -> Path:
    """
    Get cache file path based on filename.

    Args:
        filename: Base filename

    Returns:
        Path to the cache file
    """
    sanitized = sanitize_filename(filename)
    return CACHE_DIR / f"{sanitized}.pkl"

def list_all_cache_files() -> List[Path]:
    """List all pickle files in the cache directory."""
    return list(CACHE_DIR.glob("*.pkl"))

def debug_cache_contents():
    """Debug helper to log all cache files."""
    files = list_all_cache_files()
    logger.info(f"Cache directory contains {len(files)} files:")
    for f in files:
        logger.info(f"  - {f.name}")
    return files

def find_cached_file_by_version(filename: str) -> Optional[Path]:
    """
    Try to find a cached file by version number or filename pattern.

    Args:
        filename: Filename or version identifier

    Returns:
        Path to the cached file if found, None otherwise
    """
    logger.info(f"Looking for cached file matching: {filename}")

    # First try exact match (with sanitization)
    sanitized = sanitize_filename(filename)
    exact_path = CACHE_DIR / f"{sanitized}.pkl"
    if exact_path.exists():
        logger.info(f"Found exact match: {exact_path}")
        return exact_path

    # Next, try a version match
    version = extract_version_from_filename(filename)
    if version == "v??":
        logger.info("No version found in filename")
    else:
        logger.info(f"Extracted version: {version}")

    # Remove suffix that might have been added (like _v1)
    base_filename = sanitized
    if version != "v??":
        base_filename = re.sub(f"_{version}$", "", sanitized)

    # Try multiple filename patterns - all lowercase
    possible_patterns = [
        f"{base_filename}.pkl",                 # Direct sanitized name
        f"{base_filename}_{version}.pkl",       # With version suffix
        f"{version}_{base_filename}.pkl",       # With version prefix
    ]

    # Add filename without file extension if it contains one
    if "." in filename:
        name_without_ext = filename.split(".")[0]
        possible_patterns.append(f"{sanitize_filename(name_without_ext)}.pkl")

    # Debug all files in cache
    all_files = debug_cache_contents()

    # Try each pattern
    for pattern in possible_patterns:
        path = CACHE_DIR / pattern
        if path.exists():
            logger.info(f"Found match with pattern '{pattern}': {path}")
            return path

    # As a fallback, look for any file containing the version string
    if version != "v??":
        version_lower = version.lower()
        for file_path in all_files:
            if version_lower in file_path.stem.lower():
                logger.info(f"Found version match: {file_path}")
                return file_path

    logger.info(f"No cached file found for '{filename}'")
    return None

def get_cached_analysis(filename: str) -> Union[Any, None]:
    """
    Retrieve cached analysis if it exists.

    Args:
        filename: Name of the cached file or version identifier

    Returns:
        Cached object if exists, None otherwise
    """
    # Try to find the cached file
    cache_path = find_cached_file_by_version(filename)

    if cache_path and cache_path.exists():
        try:
            with open(cache_path, 'rb') as f:
                logger.info(f"Loading cache from: {cache_path}")
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Error loading cache from {cache_path}: {e}")

    return None

def cache_analysis(filename: str, analysis_obj: Any):
    """
    Cache the analysis results or raw content including raw OpenAI response.

    Args:
        filename: Name to use for the cache file
        analysis_obj: Object to cache
    """
    sanitized = sanitize_filename(filename)
    cache_path = CACHE_DIR / f"{sanitized}.pkl"
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(analysis_obj, f)
            logger.info(f"Saved cache to: {cache_path}")
    except Exception as e:
        logger.error(f"Error saving cache to {cache_path}: {e}")

def get_cached_files(prd_files_only=False, stories_ac_only=False) -> List[str]:
    """
    Retrieve cached files with optional filtering.

    Args:
        prd_files_only: If True, only return PRD files
        stories_ac_only: If True, only return stories/AC files

    Returns:
        Sorted list of cached file stems
    """
    if prd_files_only:
        return sorted([f.stem for f in CACHE_DIR.glob("*prd*.pkl")])  # lowercase pattern
    elif stories_ac_only:
        return sorted([f.stem for f in CACHE_DIR.glob("*tc*.pkl")])   # lowercase pattern
    else:
        return sorted([f.stem for f in CACHE_DIR.glob("*.pkl")])