# MCN API Postman Collection

## Overview
This collection contains 9 API endpoints for the MCN system, automatically generated for easy testing and development.

## Setup Instructions

1. **Import Collection**
   - Open Postman
   - Click "Import" button
   - Select `MCN_API_Collection.json`

2. **Import Environment**
   - Click "Import" button
   - Select `MCN_Development_Environment.json`
   - Set as active environment

3. **Configure Variables**
   - Update `base_url` if your MCN server runs on different port
   - Set `api_key` if authentication is required

## Available Endpoints

### ML (Machine Learning)
- Train ML Model
- Make Prediction

### Database
- Execute Database Query

### AI
- AI Chat

### IoT
- List IoT Devices
- Read IoT Device

### Events
- Trigger Event

### Agents
- Create Agent

### Pipelines
- Run Data Pipeline

## Usage Tips

1. **Variables**: Use {{variable_name}} syntax for dynamic values
2. **Authentication**: API key is automatically included in headers
3. **Examples**: Each request includes example request/response data
4. **Testing**: Use Postman's test scripts for automated testing

## Generated on: 2026-07-09 17:18:14
