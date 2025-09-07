# LLM Integration Guide

This document describes how to integrate and use the trained SLM (Small Language Model) for data extraction in the HiLabs Roster Processing system.

## Overview

The system now supports a trained SLM as the primary data extraction method, with automatic fallback to rule-based extraction if the LLM fails or is unavailable.

## Architecture

```
Email Input → LLM Extractor (Primary) → Success
                    ↓ (if fails)
              Rule-based Extractor (Fallback) → Success
```

## Configuration

### Environment Variables

Add these variables to your `.env` file:

```bash
# SLM Configuration
SLM_ENABLED=true
SLM_BASE_URL=http://localhost:5000/v1
SLM_MODEL_NAME=gpt-4.1
SLM_API_KEY=dummy-key
SLM_TIMEOUT=30
SLM_MAX_TOKENS=4000
SLM_TEMPERATURE=0.1
SLM_FALLBACK_ENABLED=true
```

### Configuration Details

- **SLM_ENABLED**: Enable/disable SLM integration (default: true)
- **SLM_BASE_URL**: Base URL for the SLM service (default: http://localhost:5000/v1)
- **SLM_MODEL_NAME**: Model name to use (default: gpt-4.1)
- **SLM_API_KEY**: API key for authentication (default: dummy-key for local)
- **SLM_TIMEOUT**: Request timeout in seconds (default: 30)
- **SLM_MAX_TOKENS**: Maximum tokens for generation (default: 4000)
- **SLM_TEMPERATURE**: Temperature for generation (default: 0.1 for consistency)
- **SLM_FALLBACK_ENABLED**: Enable fallback to rule-based extraction (default: true)

## SLM Service Requirements

Your SLM service must:

1. **Run on localhost:5000** (or update SLM_BASE_URL)
2. **Support OpenAI Chat Completions API** format
3. **Accept the following request format**:

```json
{
  "model": "gpt-4.1",
  "messages": [
    {
      "role": "system",
      "content": "System prompt for data extraction..."
    },
    {
      "role": "user", 
      "content": "Email content to extract data from..."
    }
  ],
  "temperature": 0.1,
  "max_tokens": 4000,
  "timeout": 30
}
```

4. **Return JSON array** with extracted provider records

## Expected Output Format

The SLM should return a JSON array where each object represents a provider record:

```json
[
  {
    "Transaction Type": "Add",
    "Transaction Attribute": "Provider",
    "Effective Date": "2024-01-15",
    "Term Date": null,
    "Term Reason": null,
    "Provider Name": "Dr. John Smith",
    "Provider NPI": "1234567890",
    "Provider Specialty": "Internal Medicine",
    "State License": "MD12345",
    "Organization Name": "ABC Medical Group",
    "TIN": "12-3456789",
    "Group NPI": "0987654321",
    "Complete Address": "123 Main St, City, ST 12345",
    "Phone Number": "(555) 123-4567",
    "Fax Number": "(555) 123-4568",
    "PPG ID": "PPG001",
    "Line Of Business": "Commercial"
  }
]
```

## System Prompt

The system uses a comprehensive prompt that instructs the SLM to:

1. Extract ALL provider information from email content
2. Use exact field names from the schema
3. Handle missing data appropriately
4. Follow healthcare data standards
5. Return only the JSON array

## Processing Flow

1. **Email Intake**: Parse and validate incoming email
2. **Classification**: Determine email type and processing strategy
3. **LLM Extraction** (Primary):
   - Extract text content from email
   - Call SLM with system prompt and email content
   - Parse and validate JSON response
   - Map to standardized schema
4. **Fallback** (if LLM fails):
   - Use rule-based extraction
   - Apply regex patterns and NLP techniques
   - Continue with normal pipeline
5. **Normalization**: Standardize data formats
6. **Validation**: Validate data quality
7. **Versioning**: Create versioned snapshot
8. **Export**: Generate Excel file

## Testing

### Health Check

Test if your SLM service is available:

```bash
cd api
python test_llm_integration.py
```

### Manual Testing

You can test the SLM endpoint directly:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:5000/v1",
    api_key="dummy-key"
)

response = client.chat.completions.create(
    model="gpt-4.1",
    messages=[
        {"role": "system", "content": "You are a healthcare data extraction specialist..."},
        {"role": "user", "content": "Extract provider data from this email..."}
    ],
    temperature=0.1,
    max_tokens=4000
)

print(response.choices[0].message.content)
```

## Monitoring

The system logs LLM usage and performance:

- **LLM Health**: Regular health checks
- **Extraction Success/Failure**: Detailed logging
- **Fallback Usage**: When rule-based extraction is used
- **Performance Metrics**: Processing time and token usage

## Troubleshooting

### Common Issues

1. **Connection Refused**: SLM service not running on localhost:5000
2. **Timeout**: SLM service too slow, increase SLM_TIMEOUT
3. **Invalid JSON**: SLM returning malformed JSON
4. **Empty Results**: SLM not extracting data properly

### Debug Steps

1. Check SLM service is running: `curl http://localhost:5000/health`
2. Test with simple request using the test script
3. Check logs for detailed error messages
4. Verify SLM configuration in `.env` file

### Fallback Behavior

If SLM fails, the system automatically falls back to rule-based extraction:

- No data loss
- Processing continues normally
- Logs indicate fallback usage
- Same output format maintained

## Performance Considerations

- **Response Time**: SLM should respond within 30 seconds
- **Token Limits**: Configure SLM_MAX_TOKENS appropriately
- **Concurrent Requests**: SLM service should handle multiple requests
- **Memory Usage**: Monitor SLM service memory consumption

## Security

- **Local Only**: SLM runs locally, no external API calls
- **No PHI Exposure**: All processing happens within your environment
- **API Key**: Use dummy key for local services
- **Network**: SLM service should only accept local connections

## Future Enhancements

- **Model Versioning**: Support multiple SLM model versions
- **A/B Testing**: Compare SLM vs rule-based performance
- **Fine-tuning**: Continuous model improvement
- **Caching**: Cache SLM responses for similar emails
- **Batch Processing**: Process multiple emails in single SLM call
