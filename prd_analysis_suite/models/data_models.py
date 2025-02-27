import time
from pydantic import BaseModel, Field
from typing import List, Dict, Union, Optional

# ----------------------------------------------------------------------
# Pydantic Models
# ----------------------------------------------------------------------

class PRDAnalysis(BaseModel):
    """Model representing the PRD analysis result."""
    filename: str
    prompt: str
    analysis: dict
    raw_response: dict  # Storing full OpenAI response
    timestamp: float = Field(default_factory=time.time)
    elapsed_time: float = 0.0

class TestCase(BaseModel):
    """Model representing a GWT test case."""
    Given: str = Field(..., description="Precondition for the test case")
    When: str = Field(..., description="Action performed in the test case")
    Then: str = Field(..., description="Expected outcome of the test case")

class RequirementTestCases(BaseModel):
    """Model grouping test cases by type."""
    Functional: List[TestCase] = Field(default_factory=list, description="List of functional test cases")
    Performance: List[TestCase] = Field(default_factory=list, description="List of performance test cases")
    Security: List[TestCase] = Field(default_factory=list, description="List of security test cases")

class TestCases(BaseModel):
    """Model representing all test cases for multiple requirements."""
    TestCases: Dict[str, RequirementTestCases] = Field(..., description="Mapping of requirement IDs to test cases")
    Assumptions: Dict[str, str] = Field(..., description="Mapping of requirement IDs to assumptions")

class TestCaseDetail(BaseModel):
    """Detailed model for a single test case."""
    TC_ID: str
    Test_Type: str
    Test_Category: str
    Requirement_ID: str
    Scenario_Name: str
    Story_Category: str = Field(alias="Story Category", default="")
    Type: str
    Review_Notes: str = Field(alias="Review Notes", default="")
    Document_Name: str = Field(alias="Document Name", default="")
    Review_Date: str = Field(alias="Review Date", default="")
    Acceptance_Criteria: List[str] = Field(alias="Acceptance Criteria", default_factory=list)

class TestCasesData(BaseModel):
    """Base model for test case data."""
    table: List[TestCaseDetail] = Field(default_factory=list)
    original_prd_content: str = Field(default="")
    assumptions: Dict[str, str] = Field(default_factory=dict, alias="Assumptions")
    test_cases: Dict[str, Dict[str, List[Dict[str, str]]]] = Field(default_factory=dict, alias="TestCases")

class TestCasesResult(TestCasesData):
    """Model for test case generation results, including metadata."""
    filename: str = ""
    prompt: str = ""
    raw_response: dict = Field(default_factory=dict)
    timestamp: float = 0.0
    elapsed_time: float = 0.0

class NextIDRequest(BaseModel):
    """Request model for ID generation."""
    version: str = Field(..., description="The version string, e.g. 'V2'")
    candidate_ids: List[str] = Field(..., description="Proposed IDs to be checked for duplicates")

class NextIDResponse(BaseModel):
    """Response model for ID generation."""
    assigned_ids: List[str] = Field(..., description="The assigned IDs after deduplication/fixes")