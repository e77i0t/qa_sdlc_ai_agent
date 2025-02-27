# PRD Analysis Suite

A tool that uses AI to analyze Product Requirements Documents (PRDs) and automatically generate user stories, acceptance criteria, and test cases.

> **Presented at the [Test Automation Summit Denver](https://www.testingmind.com/event/test-automation-summit-denver/agenda/) as "PLUGGING INTO THE QA MATRIX: EMBRACING DIGITAL TRANSFORMATION WITH AI AGENTS" on Feb 26, 2025 by [Elliot Sequeira](https://www.linkedin.com/in/elliot-sequeira/)**

## 🚀 What This Tool Does

This application helps quality assurance teams and product managers:

- Extract requirements from PRD documents
- Generate user stories with acceptance criteria
- Create test cases from requirements
- Format test cases in Given-When-Then style
- Generate BDD (Behavior-Driven Development) test specifications

No coding experience is required to use this tool!

## 📋 Requirements

- Python 3.8 or newer
- Internet connection (for API access)
- OpenAI API key (for GPT-4 access)
- Git (for cloning the repository)

## 🛠️ Setup & Installation

### 1. Clone the Repository

First, clone the repository to your local machine:

```bash
git clone https://github.com/your-username/prd-analysis-suite.git
cd prd-analysis-suite
```

### 2. Create an Environment File

Create a file named `.env` in the project directory with your OpenAI API key:

```
OPENAI_API_KEY=your_api_key_here
```

Replace `your_api_key_here` with your actual OpenAI API key.

> 🔑 **Where to get an API key**: Visit [OpenAI's platform website](https://platform.openai.com/), create an account, and generate an API key.

### 3. Standard Python Installation

```bash
# Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run prd_analysis_suite/app.py
```

The application will be available at http://localhost:8501 in your web browser.

### Alternative: Docker Installation (Optional)

If you prefer using Docker:

1. **Install Docker** ([Docker Desktop](https://www.docker.com/products/docker-desktop/) for Windows/Mac or [Docker Engine](https://docs.docker.com/engine/install/) for Linux)

2. **Create and run the Docker container**

   ```bash
   # Create and run the Docker container
   docker run -it --name prd-analysis-suite \
     -p 8501:8501 \
     -v $(pwd):/app \
     python:3.10-slim \
     /bin/bash
   ```

   **For Windows Command Prompt** (cmd.exe), use:
   ```cmd
   docker run -it --name prd-analysis-suite -p 8501:8501 -v %cd%:/app python:3.10-slim /bin/bash
   ```

   **For Windows PowerShell**, use:
   ```powershell
   docker run -it --name prd-analysis-suite -p 8501:8501 -v ${PWD}:/app python:3.10-slim /bin/bash
   ```

3. **Inside the Docker container**, install dependencies and run the app:

   ```bash
   cd /app
   pip install -r requirements.txt
   streamlit run prd_analysis_suite/app.py
   ```

   For future use, restart the container with:
   ```bash
   docker start -i prd-analysis-suite
   ```

## 🎮 Using the Application

### Workflow

#### 1. Ingest PRD
- Click "📄 Ingest PRD" in the sidebar
- Select a sample PRD file from the dropdown menu (samples are located in the `input_prds` directory)
  > 💡 **Tip**: Start with one of the sample PRDs like `v1_PRD.html` or `v2_PRD.html` to learn how the system works
- Optional: Use PRD Optimization to reduce token usage
- Click "Process PRD"

#### 2. View Generated Requirements
- Click "📝 View Payloads & Responses"
- Select your processed PRD file
- Expand sections to view extracted requirements and acceptance criteria

#### 3. Generate Test Cases
- Click "📝 Expand User Stories & AC"
- Select your PRD file
- Click "Expand Stories & AC into Tests"
- View the generated test cases

#### 4. View All Test Cases
- From either the test generation or BDD page
- Click "View ALL Test Cases Generated"
- See all test cases across different versions
- Download test cases as CSV files

#### 5. Create BDD Specifications
- Click "🔄 Create GWT"
- Select your test cases file
- Click "Generate Given-When-Then Python Code"
- View the generated BDD specifications

## 🌟 Key Features

### PRD Optimization
Reduce token usage when sending to the AI:
- Basic optimization: Clean up HTML
- Strip all HTML: Extract just the text

### Test Case Generation
Automatically creates test cases from requirements in the format:
```
Given the application is launched,
   When the dashboard loads,
   Then the default set of stocks is displayed
```

### Multi-Version Support
- Process PRDs from different versions (V1, V2, etc.)
- View test cases across all versions

### Caching System
- All processed data is cached to save time and API calls
- Data persists between sessions

## 📁 Sample Files

The repository includes several sample PRDs in the `input_prds` directory:

- `v1_PRD.html` - Stock Market Dashboard Version 1
- `v2_PRD.html` - Stock Market Dashboard Version 2
- `v3_PRD.html` - Stock Market Dashboard Version 3

These sample files let you test the application without needing to create your own PRD documents. Each version builds upon the previous one with new features, making them ideal for demonstrating the multi-version test case tracking features.

## ❓ Troubleshooting

### Common Issues

#### Can't access the application
**Fix**: Make sure the application is running and check the port (typically 8501).

#### Error when processing PRD
```
OpenAI API error
```
**Fix**: Check your API key in the `.env` file, ensure you have sufficient credits, and verify your internet connection.

#### No test cases generated
**Fix**: Make sure your PRD document contains enough detail for the AI to extract requirements.

#### Docker-specific issues

If using Docker and encountering:
```
Error: port 8501 already in use
```
**Fix**: Change the port mapping in the docker run command (e.g., `-p 8502:8501`)

If encountering permission issues with Docker, you may need to run the container as the current user:
```bash
docker run -it --name prd-analysis-suite \
  -p 8501:8501 \
  -v $(pwd):/app \
  --user $(id -u):$(id -g) \
  python:3.10-slim \
  /bin/bash
```

### Getting Help

If you encounter problems:
- Check log messages in the terminal where Streamlit is running
- Look for error messages in the Streamlit interface
- If using Docker, check logs with `docker logs prd-analysis-suite`
- Contact the project maintainer at: [your-email@example.com]

---

Created by [Elliot Sequeira](https://www.linkedin.com/in/elliot-sequeira/)
