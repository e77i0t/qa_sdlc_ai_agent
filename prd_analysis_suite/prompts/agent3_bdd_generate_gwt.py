bdd_system_prompt ="""
    You are a test automation expert generating BDD feature
    files in Gherkin format."

"""

bdd_user_prompt = """
    Generate a BDD feature file in Gherkin format for the Stock Market
    Dashboard.
    Each scenario must include:
    - Scenario Name
    - TC_ID and Requirement_ID
    - Given, When, Then steps

    Here are the test cases and requirements:
    <INSERT TEST CASES & REQUIREMENTS JSON HERE>

    If the response is too long, return only part 1 and indicate how
    many parts exist.

"""
