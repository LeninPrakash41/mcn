# MCN ML System - Complete Guide

## Overview

The MCN ML System provides a comprehensive machine learning platform with real implementations, supporting the full ML lifecycle from data loading to model deployment.

## Features Completed

### ✅ Core ML Operations
- **Model Training**: Linear Regression, Random Forest, XGBoost
- **Prediction**: Single and batch predictions
- **Model Management**: Save, load, export models
- **Dataset Operations**: Load, preprocess, analyze datasets

### ✅ Advanced Features
- **Fine-tuning**: Language model fine-tuning with progress tracking
- **Auto-tuning**: Automatic hyperparameter optimization
- **Model Comparison**: Compare multiple models automatically
- **Pipeline Engine**: Create and execute ML pipelines
- **Model Deployment**: Deploy models as API endpoints
- **Batch Processing**: Handle large datasets efficiently

### ✅ Integration Features
- **Dynamic Package System**: `use "ml"` for ML functions
- **Database Integration**: Store models and results in SQLite
- **AI Integration**: AI-powered model analysis and recommendations
- **Event System**: ML events and notifications
- **Async Processing**: Background training and processing

## Quick Start

### 1. Basic Model Training

```mcn
use "ml"

// Load dataset
var dataset = load_dataset("sales", "data/sales.csv")

// Train model
var model = train("random_forest", "sales", "revenue", {
    "n_estimators": 100,
    "test_size": 0.2
})

// Make prediction
var prediction = predict(model.model_id, {
    "product_price": 29.99,
    "marketing_spend": 1000,
    "season": "summer"
})

log prediction
```

### 2. Complete ML Pipeline

```mcn
use "ml"
use "db"

// Load and preprocess data
var dataset = load_dataset("customers", "data/customers.csv")

var preprocessing = preprocess("customers", [
    {"type": "drop_nulls"},
    {"type": "normalize", "columns": ["age", "income"]},
    {"type": "encode_categorical", "columns": ["category"]}
])

// Compare multiple models
var comparison = compare_models("customers", "churn", [
    "linear_regression", 
    "random_forest", 
    "xgboost"
])

// Deploy best model
var best_model = comparison.best_model.model_id
var deployment = deploy_model(best_model, "churn_api")

log "Model deployed at: " + deployment.endpoint
```

### 3. Fine-tuning Language Models

```mcn
use "ml"

// Fine-tune GPT model
var fine_tune_job = fine_tune(
    "gpt-3.5-turbo", 
    "training_data.jsonl", 
    "custom_model", 
    {
        "epochs": 3,
        "learning_rate": 0.0001,
        "batch_size": 4
    }
)

// Monitor progress
var status = get_training_status(fine_tune_job.job_id)
log "Training progress: " + status.progress + "%"
```

## Available Functions

### Core Functions
- `train(model_type, dataset_name, target_column, **options)` - Train ML model
- `predict(model_id, input_data)` - Make prediction
- `load_dataset(name, file_path, **options)` - Load dataset
- `preprocess(dataset_name, operations)` - Preprocess data

### Advanced Functions
- `compare_models(dataset_name, target_column, model_types)` - Compare models
- `deploy_model(model_id, endpoint_name)` - Deploy as API
- `batch_predict(model_id, data_file, output_file)` - Batch predictions
- `export_model(model_id, format)` - Export model
- `fine_tune(base_model, training_data, new_name, **options)` - Fine-tune model
- `get_training_status(job_id)` - Check training progress

### Model Types Supported
- `linear_regression` - Linear regression for continuous targets
- `random_forest` - Random forest for classification/regression
- `xgboost` - XGBoost for high-performance ML (requires installation)

### Preprocessing Operations
```mcn
var operations = [
    {"type": "drop_nulls"},
    {"type": "fill_nulls", "strategy": "mean", "columns": ["age", "income"]},
    {"type": "normalize", "columns": ["numeric_columns"]},
    {"type": "encode_categorical", "method": "label", "columns": ["category"]},
    {"type": "feature_selection", "target": "target_col", "threshold": 0.1}
]
```

## Real Implementation Details

### Model Persistence
- Models saved to `mcn_models/` directory
- Automatic serialization with pickle
- Metadata stored with models
- Model registry for tracking

### Database Integration
- SQLite backend for data storage
- Automatic table creation
- Query interface for data access
- Results and metrics storage

### API Deployment
- Models deployed as REST endpoints
- Automatic endpoint generation
- JSON input/output format
- Status monitoring

### Performance Features
- Async training with progress tracking
- Batch processing for large datasets
- Memory-efficient data handling
- Automatic cleanup and optimization

## Error Handling

The ML system provides comprehensive error handling:

```mcn
var result = train("random_forest", "dataset", "target")

if result.error
    log "Training failed: " + result.error
else
    log "Model trained successfully: " + result.model_id
```

## Integration with Other MCN Systems

### AI System Integration
```mcn
use "ai"
use "ml"

// Train model
var model = train("random_forest", "data", "target")

// Get AI analysis
var analysis = ai("Analyze this model performance: " + model.metrics.accuracy)
log analysis
```

### Database Integration
```mcn
use "db"
use "ml"

// Store results
query("INSERT INTO ml_results (model_id, accuracy) VALUES (?, ?)", 
      (model.model_id, model.metrics.accuracy))
```

### Event System Integration
```mcn
use "ml"

// Register for training completion events
on("model_trained", "handle_completion")

function handle_completion(data) {
    log "Model training completed: " + data.model_id
}
```

## Best Practices

1. **Data Preparation**: Always preprocess data before training
2. **Model Comparison**: Use `compare_models()` to find best algorithm
3. **Validation**: Use test/validation splits for accurate metrics
4. **Deployment**: Test models before deploying to production
5. **Monitoring**: Track model performance over time
6. **Versioning**: Use descriptive model names and export metadata

## Troubleshooting

### Common Issues
- **Import Errors**: Install required packages (`pip install scikit-learn pandas numpy`)
- **Memory Issues**: Use batch processing for large datasets
- **Training Failures**: Check data quality and preprocessing
- **Deployment Issues**: Ensure model is trained and saved properly

### Performance Tips
- Use appropriate model types for your data size
- Preprocess data to improve training speed
- Use batch prediction for multiple predictions
- Monitor memory usage with large datasets

## Examples

See the following example files:
- `examples/ml_complete_example.mcn` - Comprehensive ML pipeline
- `examples/ml_test.mcn` - Simple ML test
- `use-cases/ml_model_training.mcn` - Real-world ML use case

The MCN ML System is now fully integrated and production-ready!