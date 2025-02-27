import re
import logging
from typing import List, Set
from services.cache_service import get_cached_analysis, cache_analysis, get_cached_files
from config import CACHE_DIR

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Requirement ID Management Functions
# ----------------------------------------------------------------------
def ensure_requirement_ids():
    """
    Reads all cached PRD files (PRD_*.pkl), ensures each requirement ID
    follows the pattern: V##-REQ-###, where:
      - V## = version extracted from the file name (e.g., PRD_V10html => V10)
      - REQ-### is a global unique index (e.g., REQ-001, REQ-002, etc.)

    Updates the IDs if needed and overwrites the .pkl cache files.
    """
    prd_files = get_cached_files(prd_files_only=True)
    all_req_ids = set()  # global set of used IDs across all files

    for filename in prd_files:
        # 1) Extract version from filename, e.g. "PRD_V10html.pkl" -> "V10"
        version = extract_version_from_filename(filename)

        # 2) Load the analysis object from cache
        analysis_obj = get_cached_analysis(filename)
        if not analysis_obj or not hasattr(analysis_obj, "analysis"):
            logger.warning(f"No valid 'analysis' found for file: {filename}")
            continue

        # 3) Get the table of requirements from .analysis
        table_data = analysis_obj.analysis.get("table", [])
        if not isinstance(table_data, list):
            logger.warning(f"No valid 'table' list in analysis for: {filename}")
            continue

        # 4) For each requirement, ensure ID is valid and unique
        for row in table_data:
            if "ID" not in row:
                row["ID"] = generate_unique_req_id(version, all_req_ids)
            else:
                current_id = row["ID"]
                if is_valid_req_id(current_id, version) and current_id not in all_req_ids:
                    # If it's valid and not used, mark it used
                    all_req_ids.add(current_id)
                else:
                    # Otherwise, generate a new unique ID
                    row["ID"] = generate_unique_req_id(version, all_req_ids)

        # 5) Overwrite updated table in the analysis object
        analysis_obj.analysis["table"] = table_data

        # 6) Write the updated analysis back to the cache
        cache_analysis(filename, analysis_obj)

def extract_version_from_filename(filename: str) -> str:
    """
    Attempt to extract a version from file names in the new format, e.g. V10_PRD.html.
    Captures the numeric digits after 'V' or 'v' and before '_PRD'.
    Fallback is V?? if not found.

    Args:
        filename: Filename to extract version from

    Returns:
        Extracted version string
    """
    # e.g., V10_PRD.html, v9_prd_something, etc.
    pattern = re.compile(r'[Vv]([0-9]+)_[Pp][Rr][Dd]', re.IGNORECASE)
    match = pattern.search(filename)
    if match:
        return f"V{match.group(1)}"
    else:
        return "V??"  # fallback if not found

def is_valid_req_id(req_id: str, version: str) -> bool:
    """
    Checks if the requirement ID matches the pattern:
       <version>-REQ-<3digits>, e.g. V10-REQ-015

    Args:
        req_id: Requirement ID to check
        version: Version string to match

    Returns:
        True if valid, False otherwise
    """
    pattern = rf"^{version}-REQ-\\d{{3}}$"
    return re.match(pattern, req_id) is not None

def generate_unique_req_id(version: str, used_ids: Set[str]) -> str:
    """
    Generates the next available ID of the form V##-REQ-### that
    hasn't been used yet across all PRD files.

    Args:
        version: Version string to use
        used_ids: Set of already used IDs

    Returns:
        Newly generated unique ID
    """
    i = 1
    while True:
        candidate = f"{version}-REQ-{i:03d}"
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate
        i += 1

def get_used_ids_for_version(version: str) -> set:
    """
    Scans all PRD PKL files, collects all used IDs for the given version,
    and returns a set of those IDs.

    Args:
        version: Version string to match

    Returns:
        Set of used IDs
    """
    used_ids = set()
    for pkl_file in CACHE_DIR.glob("PRD_*.pkl"):
        with open(pkl_file, "rb") as f:
            analysis_obj = pickle.load(f)

        # We assume the 'analysis' dict has a 'table' with 'ID' fields
        if hasattr(analysis_obj, "analysis"):
            table_data = analysis_obj.analysis.get("table", [])
            for row in table_data:
                row_id = row.get("ID", "")
                # Check if row_id starts with the given version, e.g. "V2-REQ-xxx"
                if row_id.startswith(f"{version}-REQ-"):
                    used_ids.add(row_id)
    return used_ids

def store_used_ids_for_version(version: str, new_ids: List[str]):
    """
    A stub for if you want to do any additional logic whenever new IDs are assigned.
    For instance, you could store these in a central index file, or do nothing.

    Args:
        version: Version string
        new_ids: List of newly assigned IDs
    """
    # Example: You might track a separate index file if you want
    # Or do nothing if the IDs are already stored in each PRD.
    pass

def deduplicate_ids(version: str, candidate_ids: List[str]) -> List[str]:
    """
    Given a list of candidate IDs (e.g. user-provided or LLM-proposed),
    ensure they are unique for the version. If a candidate is invalid or used,
    generate a brand-new ID. Return the final list of assigned IDs.

    Args:
        version: Version string
        candidate_ids: List of candidate IDs

    Returns:
        List of assigned (deduplicated) IDs
    """
    # Retrieve all used IDs for the version from across PRDs
    used_ids = get_used_ids_for_version(version)

    assigned = []
    for cid in candidate_ids:
        if is_valid_req_id(cid, version) and cid not in used_ids:
            assigned.append(cid)
            used_ids.add(cid)
        else:
            new_id = generate_next_id(version, used_ids)
            assigned.append(new_id)
    return assigned

def generate_next_id(version: str, all_used: Set[str]) -> str:
    """
    Generates a brand-new ID of the form 'V2-REQ-00X', ensuring no duplicates.

    Args:
        version: Version string
        all_used: Set of already used IDs

    Returns:
        Newly generated unique ID
    """
    i = 1
    while True:
        candidate = f"{version}-REQ-{i:03d}"
        if candidate not in all_used:
            all_used.add(candidate)
            return candidate
        i += 1