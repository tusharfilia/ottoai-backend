# Transcript Analysis System

This document explains the architecture of the transcript analysis system and provides instructions for extending it with new analysis processes.

## 🏗️ System Architecture

The system follows a modular architecture with the following components:

```
app/services/transcript_analysis/
├── __init__.py               # Package definition, exports TranscriptAnalyzer
├── transcript_analyzer.py    # Main interface for all analysis operations
├── README.md                 # This documentation file
└── processes/                # Contains different analysis implementations
    ├── __init__.py           # Package definition
    ├── base_process.py       # Abstract base class all processes must implement
    └── v0_process.py         # Initial version of transcript analysis
```

### Key Components

1. **TranscriptAnalyzer** - The main interface that:
   - Manages available analysis process implementations
   - Handles transcript preprocessing
   - Handles database interactions
   - Delegates the actual analysis to the selected process

2. **BaseAnalysisProcess** - Abstract base class that defines the interface for all analysis processes:
   - `analyze()` method - Performs the actual analysis
   - `name` property - Returns the process name
   - `description` property - Provides a human-readable description

3. **V0AnalysisProcess** - The initial implementation that:
   - Analyzes the entire transcript in a single LLM call
   - Extracts all required information at once

## 🔄 Process Flow

1. **API Call** - Request comes in to `/audio/analyze-transcript/{call_id}` with optional `process_name`
2. **TranscriptAnalyzer** - Loads the specified process implementation
3. **Preprocessing** - Transcript data is cleaned and formatted
4. **Analysis** - The selected process analyzes the transcript
5. **Storage** - Results are stored in the `transcript_analyses` table
6. **Response** - Analysis results are returned to the client

## 🧩 Adding a New Analysis Process

To add a new analysis process (e.g., v1, v2), follow these steps:

### 1. Create a New Process File

Create a new file in the `processes` directory, e.g., `v1_process.py`:

```python
import json
import os
from typing import Dict, Any
import openai
from app.services.transcript_analysis.processes.base_process import BaseAnalysisProcess

class V1AnalysisProcess(BaseAnalysisProcess):
    """
    V1 transcript analysis process.
    
    Description of what makes this version different...
    """
    
    def __init__(self):
        """Initialize the V1AnalysisProcess."""
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    @property
    def name(self) -> str:
        return "v1"
    
    @property
    def description(self) -> str:
        return "V1 process that [describe improvements]"
    
    def analyze(self, transcript_data: Dict[Any, Any], call_metadata: Dict[Any, Any]) -> Dict[Any, Any]:
        """
        Implement your analysis logic here.
        
        Must return a dictionary with the expected structure.
        """
        # Your implementation...
        
        # Ensure the result has the expected structure
        self._validate_response(result)
        
        return result
        
    def _validate_response(self, result: Dict[Any, Any]) -> None:
        """
        Validate that the response has the expected structure.
        Add default sections if they're missing.
        """
        expected_sections = [
            "greeting", "customer_decision", "quoted_price", 
            "company_mentions", "farewell"
        ]
        
        for section in expected_sections:
            if section not in result:
                result[section] = {}
```

### 2. Register the New Process

Update the `transcript_analyzer.py` file to register your new process:

```python
from app.services.transcript_analysis.processes.v1_process import V1AnalysisProcess

# In the TranscriptAnalyzer class
_process_registry = {
    "v0": V0AnalysisProcess,
    "v1": V1AnalysisProcess
}
```

### 3. Ensure Output Format Consistency

While your implementation can be completely different, the output format should be consistent to ensure compatibility with the storage mechanism and frontend expectations.

The output should include these top-level sections:
- `greeting`
- `customer_decision`
- `quoted_price`
- `company_mentions`
- `farewell`

Each section should include structured data with quotes and timestamps.

### 4. Test Your New Process

You can call the endpoint with your new process name:

```
POST /audio/analyze-transcript/{call_id}?process_name=v1&company_id={company_id}
```

Or test it programmatically:

```python
analyzer = TranscriptAnalyzer(process_name="v1")
result = analyzer.analyze_and_store(call_id, db)
```

## 📋 Output Format

All analysis processes should produce a consistent output format with the following structure:

```json
{
  "greeting": {
    "rep_greeted_customer": true,
    "rep_introduced_self": true,
    "company_name_mentioned": true,
    "greeting_quote": "Hello, this is John from Skyline Roofing.",
    "introduction_quote": "My name is John.",
    "company_mention_quote": "I'm from Skyline Roofing.",
    "greeting_timestamp": "00:00:10",
    "introduction_timestamp": "00:00:15",
    "company_mention_timestamp": "00:00:20"
  },
  "customer_decision": {
    "status": "deciding",
    "quote": "I need to think about it.",
    "timestamp": "00:45:30",
    "agreement_mentioned": false
  },
  "quoted_price": {
    "price_quoted": true,
    "price": "$12,500",
    "quote": "We can do the full roof replacement for $12,500.",
    "timestamp": "00:30:15",
    "payment_discussed": true,
    "payment_quote": "We offer financing options.",
    "payment_timestamp": "00:31:20"
  },
  "company_mentions": {
    "mentioned": true,
    "mention_count": 3,
    "quotes": [
      "I'm from Skyline Roofing.",
      "At Skyline Roofing, we specialize in...",
      "Skyline Roofing has been in business for 20 years."
    ],
    "timestamps": ["00:00:20", "00:15:30", "00:40:10"]
  },
  "farewell": {
    "professional_goodbye": true,
    "goodbye_quote": "Thank you for your time. Have a great day!",
    "goodbye_timestamp": "01:15:45",
    "follow_up_scheduled": true,
    "follow_up_quote": "I'll call you next week to follow up.",
    "follow_up_timestamp": "01:15:30"
  }
}
```

## 🔍 Implementing Different Analysis Strategies

When creating new process versions, consider these approaches:

### Chunked Analysis (for v1)
Break the transcript into smaller chunks and analyze each separately to handle longer transcripts.

### Multi-pass Analysis (for v2)
Perform multiple specialized passes over the transcript:
1. First pass: Identify key sections and timestamps
2. Second pass: Deep dive into each section with specialized prompts
3. Third pass: Reconcile and verify results

### Few-shot Learning (for v3)
Include examples of correct analyses in the prompts to improve accuracy.

### Chain-of-thought (for v4)
Guide the LLM through a step-by-step reasoning process rather than asking for direct extraction.

## 📊 Database Storage

Analysis results are stored in the `transcript_analyses` table with:
- Structured JSON data in dedicated fields
- Version tracking to store multiple analyses per call
- Process name tracking to know which implementation was used

## 🚀 Using the Analysis Endpoints

The API provides these endpoints:

1. **Analyze Transcript**
   ```
   POST /audio/analyze-transcript/{call_id}?process_name=v0&company_id={company_id}
   ```

2. **Get Analysis Results**
   ```
   GET /audio/transcript-analysis/{call_id}?company_id={company_id}&version={version}
   ```

3. **List Available Processes**
   ```
   GET /audio/analysis-processes
   ```

4. **List Analysis Versions**
   ```
   GET /audio/transcript-analyses/{call_id}/versions?company_id={company_id}
   ```

## 🔒 Best Practices

1. **Versioning** - Always create a new version file rather than modifying existing ones
2. **Testing** - Test with various transcript types and lengths
3. **Error Handling** - Always handle exceptions and provide informative error messages
4. **Output Validation** - Use the `_validate_response` method to ensure consistent output structure
5. **Documentation** - Document your process's strengths, weaknesses, and unique approach 