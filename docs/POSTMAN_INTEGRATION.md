# MCN Postman Integration

## Overview

MCN automatically generates Postman collections for all API endpoints, making it easy for developers to test and integrate with MCN services.

## Features

- **Auto-Discovery**: Automatically detects MCN API endpoints
- **Collection Generation**: Creates complete Postman collections with examples
- **Environment Setup**: Generates environment variables for easy configuration
- **Documentation**: Includes comprehensive API documentation
- **Auto-Generation**: Generates collections on server startup

## Quick Start

### 1. Auto-Generate on Server Start

When you start an MCN server, Postman collections are automatically generated:

```bash
python run_mcn.py serve --file api.mcn --port 8080
```

Output:
```
✅ Postman collection generated: 8 endpoints
📁 Files saved to: postman_exports/
```

### 2. Manual Generation

```mcn
use "postman"

// Generate with default settings
var result = auto_generate()
log result

// Generate to custom directory
var custom = generate("my_api_docs")
log custom
```

### 3. Direct Function Call

```mcn
// Generate Postman collection
var postman_result = generate_postman("api_collections")
log postman_result
```

## Generated Files

### Collection File: `MCN_API_Collection.json`
- Complete API endpoint definitions
- Request/response examples
- Parameter documentation
- Organized by categories (ML, DB, AI, IoT, etc.)

### Environment File: `MCN_Development_Environment.json`
- Base URL configuration
- API key variables
- Common parameters

### Documentation: `README.md`
- Setup instructions
- Usage guidelines
- Endpoint descriptions

## API Endpoints Included

### Machine Learning
- `POST /api/ml/train` - Train ML models
- `POST /api/ml/predict` - Make predictions
- `GET /api/ml/models` - List models
- `POST /api/ml/deploy` - Deploy models

### Database
- `POST /api/db/query` - Execute SQL queries
- `GET /api/db/tables` - List tables
- `POST /api/db/backup` - Backup data

### AI Integration
- `POST /api/ai/chat` - AI chat interface
- `POST /api/ai/analyze` - Text analysis
- `POST /api/ai/summarize` - Text summarization

### IoT Devices
- `GET /api/iot/devices` - List devices
- `GET /api/iot/device/{id}/read` - Read sensor data
- `POST /api/iot/device/{id}/command` - Send commands

### Event System
- `POST /api/events/trigger` - Trigger events
- `GET /api/events/handlers` - List handlers
- `POST /api/events/subscribe` - Subscribe to events

### Autonomous Agents
- `POST /api/agents/create` - Create agents
- `POST /api/agents/{id}/activate` - Activate agent
- `POST /api/agents/{id}/think` - Agent processing

### Data Pipelines
- `POST /api/pipelines/create` - Create pipeline
- `POST /api/pipelines/{id}/run` - Execute pipeline
- `GET /api/pipelines/{id}/status` - Check status

## Import to Postman

### Step 1: Import Collection
1. Open Postman
2. Click "Import" button
3. Select `MCN_API_Collection.json`
4. Collection appears in sidebar

### Step 2: Import Environment
1. Click "Import" button
2. Select `MCN_Development_Environment.json`
3. Set as active environment (top-right dropdown)

### Step 3: Configure Variables
1. Click environment name in top-right
2. Update `base_url` if needed (default: `http://localhost:8080`)
3. Set `api_key` if authentication required
4. Save changes

## Usage Examples

### Test ML Training
```json
POST {{base_url}}/api/ml/train
{
  "model_type": "random_forest",
  "dataset_name": "customers",
  "target_column": "churn",
  "n_estimators": 100
}
```

### Make Prediction
```json
POST {{base_url}}/api/ml/predict
{
  "model_id": "rf_customers_123456",
  "input_data": {
    "age": 30,
    "income": 50000,
    "spending_score": 0.7
  }
}
```

### AI Chat
```json
POST {{base_url}}/api/ai/chat
{
  "prompt": "Analyze customer behavior trends",
  "model": "gpt-3.5-turbo",
  "max_tokens": 150
}
```

## Advanced Features

### Custom Endpoint Discovery

```python
from mcn.core_engine.mcn_postman_generator import MCNPostmanGenerator, MCNEndpoint

generator = MCNPostmanGenerator()

# Add custom endpoint
generator.add_endpoint(MCNEndpoint(
    path="/api/custom/endpoint",
    method="POST",
    name="Custom Operation",
    description="Custom business logic",
    body_schema={"param1": "value1"},
    response_example={"result": "success"}
))

# Generate collection
collection = generator.generate_collection("custom_collection.json")
```

### Environment Customization

```python
# Generate custom environment
env = generator.generate_environment("Production")
env["values"].append({
    "key": "custom_header",
    "value": "custom_value",
    "enabled": True
})
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Generate API Documentation
on: [push]
jobs:
  generate-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Generate Postman Collection
        run: |
          python -c "
          from mcn.core_engine.mcn_postman_generator import generate_postman_collection
          generate_postman_collection('docs/api')
          "
      - name: Upload Artifacts
        uses: actions/upload-artifact@v2
        with:
          name: postman-collection
          path: docs/api/
```

### Docker Integration

```dockerfile
FROM python:3.9
COPY . /app
WORKDIR /app
RUN pip install -e .
RUN python -c "from mcn.core_engine.mcn_postman_generator import generate_postman_collection; generate_postman_collection()"
EXPOSE 8080
CMD ["python", "run_mcn.py", "serve", "--port", "8080"]
```

## Configuration Options

### Generator Settings

```python
generator = MCNPostmanGenerator()
generator.collection_info = {
    "name": "My API Collection",
    "description": "Custom API documentation",
    "version": "2.0.0"
}
```

### Server Integration

```python
# Disable auto-generation
server.serve(host="0.0.0.0", port=8080, auto_postman=False)

# Custom output directory
os.environ["MCN_POSTMAN_DIR"] = "/custom/path"
```

## Troubleshooting

### Common Issues

1. **Collection not generating**
   - Check file permissions in output directory
   - Ensure MCN server has write access

2. **Missing endpoints**
   - Verify endpoints are properly registered
   - Check server startup logs

3. **Import errors in Postman**
   - Validate JSON format
   - Check Postman version compatibility

### Debug Mode

```mcn
use "postman"

// Enable debug output
var result = generate("debug_output")
if result.error
    log "Error: " + result.error
else
    log "Success: " + result.endpoints_count + " endpoints generated"
```

## Best Practices

1. **Version Control**: Include generated collections in version control
2. **Environment Variables**: Use variables for all configurable values
3. **Documentation**: Keep endpoint descriptions up to date
4. **Testing**: Use Postman tests for automated API validation
5. **Security**: Never commit API keys in environment files

## API Reference

### Functions Available

- `generate_postman(output_dir)` - Generate collection to directory
- `auto_generate()` - Generate with default settings
- `generate(output_dir)` - Package function for generation

### Return Format

```json
{
  "success": true,
  "collection_file": "path/to/collection.json",
  "environment_file": "path/to/environment.json",
  "endpoints_count": 8,
  "message": "Postman collection generated with 8 endpoints"
}
```

The MCN Postman integration makes API development and testing seamless for developers!