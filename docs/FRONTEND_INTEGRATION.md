# MSL Frontend Integration Guide

MSL provides seamless integration with popular frontend frameworks, allowing developers to easily connect their frontend applications with MSL backend services.

## Supported Frameworks

- **React** - Full support with hooks and components
- **Vue.js** - Vue 3 composition API and plugin system
- **Angular** - Injectable services and HTTP client
- **Vanilla JavaScript** - Pure JavaScript API client

## Quick Start

### 1. Add Frontend to Existing Project

```bash
# Add React frontend
msl add-frontend react

# Add Vue.js frontend  
msl add-frontend vue

# Add Angular frontend
msl add-frontend angular

# Add Vanilla JS frontend
msl add-frontend vanilla
```

### 2. Initialize Project with Frontend

```bash
# Create new project with React
msl init my-app --frontend react

# Create new project with Vue
msl init my-app --frontend vue
```

## Generated Files

When you add frontend integration, MSL generates:

- **API Client** - Framework-specific client for calling MSL endpoints
- **Environment Config** - Configuration file with MSL API settings
- **Example Components** - Sample code showing how to use MSL APIs
- **Documentation** - Frontend-specific README and guides

## Framework-Specific Usage

### React Integration

```javascript
import { useMSLApi } from './msl-api-client';

function MyComponent() {
  const { callApi, loading, error } = useMSLApi();
  const [result, setResult] = useState(null);
  
  const handleSubmit = async (data) => {
    try {
      const response = await callApi('my_endpoint', data);
      setResult(response);
    } catch (err) {
      console.error('MSL API Error:', err);
    }
  };
  
  return (
    <div>
      <button onClick={() => handleSubmit({name: 'test'})} disabled={loading}>
        {loading ? 'Processing...' : 'Call MSL API'}
      </button>
      {error && <div className="error">Error: {error}</div>}
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}
```

### Vue.js Integration

```vue
<template>
  <div>
    <button @click="handleSubmit" :disabled="loading">
      {{ loading ? 'Processing...' : 'Call MSL API' }}
    </button>
    <div v-if="error" class="error">Error: {{ error }}</div>
    <pre v-if="result">{{ JSON.stringify(result, null, 2) }}</pre>
  </div>
</template>

<script>
import { useMSL } from './msl-api-client';

export default {
  setup() {
    const { callApi, loading, error } = useMSL();
    const result = ref(null);
    
    const handleSubmit = async () => {
      try {
        const response = await callApi('my_endpoint', {name: 'test'});
        result.value = response;
      } catch (err) {
        console.error('MSL API Error:', err);
      }
    };
    
    return { handleSubmit, loading, error, result };
  }
};
</script>
```

### Angular Integration

```typescript
import { Component } from '@angular/core';
import { MSLApiService } from './msl-api.service';

@Component({
  selector: 'app-msl-example',
  template: `
    <button (click)="handleSubmit()" [disabled]="loading">
      {{ loading ? 'Processing...' : 'Call MSL API' }}
    </button>
    <div *ngIf="error" class="error">Error: {{ error }}</div>
    <pre *ngIf="result">{{ result | json }}</pre>
  `
})
export class MSLExampleComponent {
  loading = false;
  error: string | null = null;
  result: any = null;
  
  constructor(private mslApi: MSLApiService) {}
  
  async handleSubmit() {
    this.loading = true;
    this.error = null;
    
    try {
      this.result = await this.mslApi.my_endpoint({name: 'test'}).toPromise();
    } catch (err) {
      this.error = err.message;
    } finally {
      this.loading = false;
    }
  }
}
```

### Vanilla JavaScript Integration

```javascript
// Using the global MSL client
async function callMSLApi() {
  try {
    const result = await window.MSL.my_endpoint({name: 'test'});
    document.getElementById('result').textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    document.getElementById('error').textContent = error.message;
  }
}

// Or create your own instance
const mslClient = new MSLApiClient('http://localhost:8080');
const result = await mslClient.my_endpoint({name: 'test'});
```

## Configuration

### Environment Variables

MSL frontend integration uses environment variables for configuration:

```bash
# .env.msl
MSL_API_URL=http://localhost:8080
MSL_ENDPOINTS={"main":"/main","health":"/health"}
MSL_AUTH_TOKEN=your-auth-token
MSL_TIMEOUT=30000
```

### API Client Configuration

You can customize the API client behavior:

```javascript
// React/Vue/Vanilla
const client = new MSLApiClient('http://localhost:8080', {
  timeout: 30000,
  retries: 3,
  headers: {
    'Authorization': 'Bearer your-token'
  }
});

// Angular
@Injectable()
export class MSLApiService {
  constructor(private http: HttpClient) {
    this.baseURL = environment.mslApiUrl;
    this.timeout = environment.mslTimeout || 30000;
  }
}
```

## Error Handling

MSL frontend integration provides comprehensive error handling:

```javascript
try {
  const result = await callApi('my_endpoint', data);
} catch (error) {
  if (error.response) {
    // MSL API returned an error response
    console.error('API Error:', error.response.data);
  } else if (error.request) {
    // Network error
    console.error('Network Error:', error.message);
  } else {
    // Other error
    console.error('Error:', error.message);
  }
}
```

## Real-time Features

### WebSocket Integration

For real-time features, MSL can provide WebSocket connections:

```javascript
// Connect to MSL WebSocket
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle real-time updates from MSL
  updateUI(data);
};

// Send data to MSL via WebSocket
ws.send(JSON.stringify({
  action: 'process_data',
  data: { /* your data */ }
}));
```

### Server-Sent Events

For one-way real-time updates:

```javascript
const eventSource = new EventSource('http://localhost:8080/events');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle MSL events
  handleMSLEvent(data);
};
```

## Best Practices

### 1. Error Boundaries (React)

```javascript
class MSLErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }
  
  static getDerivedStateFromError(error) {
    return { hasError: true };
  }
  
  componentDidCatch(error, errorInfo) {
    console.error('MSL API Error:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return <div>Something went wrong with MSL API.</div>;
    }
    
    return this.props.children;
  }
}
```

### 2. Loading States

Always provide loading states for better UX:

```javascript
const [loading, setLoading] = useState(false);

const handleApiCall = async () => {
  setLoading(true);
  try {
    await callApi('endpoint', data);
  } finally {
    setLoading(false);
  }
};
```

### 3. Caching

Implement caching for frequently accessed data:

```javascript
const cache = new Map();

const cachedApiCall = async (endpoint, data) => {
  const key = `${endpoint}-${JSON.stringify(data)}`;
  
  if (cache.has(key)) {
    return cache.get(key);
  }
  
  const result = await callApi(endpoint, data);
  cache.set(key, result);
  
  return result;
};
```

## Deployment

### Development

```bash
# Start MSL backend
msl serve --dir msl/ --port 8080

# Start frontend development server
cd frontend
npm run dev
```

### Production

```bash
# Build frontend
cd frontend
npm run build

# Serve both backend and frontend
msl serve --dir msl/ --static frontend/dist --port 8080
```

## Troubleshooting

### Common Issues

1. **CORS Errors**
   ```javascript
   // Enable CORS in MSL configuration
   {
     "api": {
       "cors": true,
       "cors_origins": ["http://localhost:3000"]
     }
   }
   ```

2. **Network Timeouts**
   ```javascript
   // Increase timeout in API client
   const client = new MSLApiClient(baseURL, { timeout: 60000 });
   ```

3. **Authentication Issues**
   ```javascript
   // Ensure auth token is properly set
   localStorage.setItem('msl_token', 'your-token');
   ```

### Debug Mode

Enable debug mode for detailed logging:

```javascript
// Set debug flag
window.MSL_DEBUG = true;

// Or in environment
MSL_DEBUG=true npm start
```

## Examples

See the `examples/` directory for complete frontend integration examples:

- `examples/react-msl-app/` - Complete React application
- `examples/vue-msl-app/` - Complete Vue.js application  
- `examples/angular-msl-app/` - Complete Angular application
- `examples/vanilla-msl-app/` - Vanilla JavaScript example

## API Reference

### MSLApiClient

```javascript
class MSLApiClient {
  constructor(baseURL, options)
  async request(endpoint, data, method)
  async [endpoint_name](data)
}
```

### React Hooks

```javascript
const { callApi, loading, error } = useMSLApi();
```

### Vue Composables

```javascript
const { callApi, loading, error } = useMSL();
```

### Angular Services

```typescript
@Injectable()
class MSLApiService {
  [endpoint_name](data: any): Observable<any>
}
```