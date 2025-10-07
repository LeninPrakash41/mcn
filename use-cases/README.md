# MSL Use Cases

Real-world examples demonstrating MSL's capabilities across different industries and applications.

## 🏥 Healthcare - Patient Management
**File:** `healthcare_patient_management.msl`

**Features:**
- Automated patient data processing
- AI-powered health assessment
- Critical condition alerts
- Care plan generation
- Healthcare team notifications

**Use Case:** Hospital patient intake system that automatically analyzes vital signs, generates risk assessments, and alerts medical staff for critical conditions.

## 🌐 MCP Server Creation
**File:** `mcp_server_creation.msl`

**Features:**
- Model Context Protocol server setup
- MSL tool registration
- Database initialization
- Request handling
- Health monitoring

**Use Case:** Create an MCP server that exposes MSL functions (database queries, AI analysis, webhooks) as standardized tools for AI assistants.

## 🤖 Machine Learning Pipeline
**File:** `ml_model_training.msl`

**Features:**
- Automated data preparation
- Model training orchestration
- Performance monitoring
- Deployment automation
- Batch predictions

**Use Case:** End-to-end ML pipeline for customer churn prediction, from data collection to model deployment and inference.

## 📊 Business Intelligence Dashboard
**File:** `bi_analytics_dashboard.msl`

**Features:**
- Real-time data aggregation
- KPI calculations
- AI-powered insights
- Anomaly detection
- Automated reporting

**Use Case:** Executive dashboard that automatically generates business insights, detects revenue anomalies, and sends reports to stakeholders.

## Running the Examples

### Prerequisites
```bash
# Install MSL
git clone <repository>
cd msl
pip install -r requirements.txt
```

### Execute Use Cases
```bash
# Healthcare example
python msl_cli.py use-cases/healthcare_patient_management.msl

# MCP Server (serve as API)
python msl_cli.py use-cases/mcp_server_creation.msl --serve --port 3000

# ML Pipeline
python msl_cli.py use-cases/ml_model_training.msl

# BI Dashboard
python msl_cli.py use-cases/bi_analytics_dashboard.msl
```

### Serve as APIs
```bash
# Serve all use cases as REST endpoints
python msl_cli.py --serve-dir use-cases/ --port 8080

# Access endpoints:
# POST http://localhost:8080/healthcare_patient_management
# POST http://localhost:8080/mcp_server_creation
# POST http://localhost:8080/ml_model_training
# POST http://localhost:8080/bi_analytics_dashboard
```

## Key MSL Features Demonstrated

### 🔄 Parallel Processing
```msl
task "data_fetch" "query" "SELECT * FROM users"
task "api_call" "trigger" "https://api.com/data"
var results = await "data_fetch" "api_call"
```

### 🤖 AI Integration
```msl
var analysis = ai("Analyze patient vitals: " + vital_signs)
var insights = ai("Generate business insights from: " + metrics)
```

### 🗄️ Database Operations
```msl
query("INSERT INTO patients VALUES (?, ?)", (id, data))
var results = query("SELECT * FROM analytics WHERE date > ?", (date))
```

### 🌐 API Automation
```msl
trigger("https://slack.com/webhook", {"text": "Alert message"})
var response = trigger("https://api.com/data", payload, "POST")
```

### 📦 Package System
```msl
use "db"    // Database utilities
use "ai"    // AI analysis functions
use "http"  // HTTP helpers
```

## Customization

Each use case can be customized for your specific needs:

1. **Database Schema**: Modify table structures and queries
2. **API Endpoints**: Update webhook URLs and payloads
3. **AI Prompts**: Customize AI analysis prompts
4. **Business Logic**: Adapt workflows to your processes
5. **Integrations**: Connect to your existing systems

## Industry Applications

- **Healthcare**: Patient monitoring, diagnosis assistance, treatment recommendations
- **Finance**: Risk assessment, fraud detection, automated reporting
- **E-commerce**: Customer analytics, inventory management, personalization
- **Manufacturing**: Quality control, predictive maintenance, supply chain optimization
- **Education**: Student performance analysis, curriculum optimization, automated grading