"""
MCN Frontend Integration Module
Helps developers handle frontend applications with MCN backend services
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from .mcn_logger import log_error, log_step

class MCNFrontendIntegration:
    """Handles frontend application integration with MCN backend"""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path)
        self.frontend_configs = {}

    def detect_frontend_framework(self) -> Optional[str]:
        """Auto-detect frontend framework in the project"""

        log_step("Detecting frontend framework")

        # Check for common frontend files
        framework_indicators = {
            'react': ['package.json', 'src/App.js', 'src/App.tsx', 'public/index.html'],
            'vue': ['package.json', 'src/App.vue', 'public/index.html'],
            'angular': ['package.json', 'src/app/app.component.ts', 'angular.json'],
            'svelte': ['package.json', 'src/App.svelte'],
            'next': ['package.json', 'next.config.js', 'pages/'],
            'nuxt': ['package.json', 'nuxt.config.js', 'pages/'],
            'vanilla': ['index.html', 'main.js', 'style.css']
        }

        for framework, files in framework_indicators.items():
            if all((self.project_path / file).exists() for file in files[:2]):
                log_step(f"Detected {framework} framework")
                return framework

        return None

    def generate_api_client(self, mcn_endpoints: List[Dict[str, Any]],
                          framework: str = None) -> str:
        """Generate frontend API client code for MCN endpoints"""

        if not framework:
            framework = self.detect_frontend_framework() or 'vanilla'

        log_step(f"Generating API client for {framework}")

        generators = {
            'react': self._generate_react_client,
            'vue': self._generate_vue_client,
            'angular': self._generate_angular_client,
            'vanilla': self._generate_vanilla_client
        }

        generator = generators.get(framework, self._generate_vanilla_client)
        return generator(mcn_endpoints)

    def _generate_react_client(self, endpoints: List[Dict[str, Any]]) -> str:
        """Generate React API client"""

        client_code = '''
import axios from 'axios';

class MCNApiClient {
  constructor(baseURL = 'http://localhost:8080') {
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for auth
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('mcn_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('MCN API Error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }
'''

        # Generate methods for each endpoint
        for endpoint in endpoints:
            method_name = endpoint.get('name', 'unknown').replace('-', '_')
            http_method = endpoint.get('method', 'POST').lower()
            path = endpoint.get('path', f'/{method_name}')

            client_code += f'''
  async {method_name}(data = {{}}) {{
    try {{
      const response = await this.client.{http_method}('{path}', data);
      return response.data;
    }} catch (error) {{
      throw new Error(`MCN {method_name} failed: ${{error.message}}`);
    }}
  }}
'''

        client_code += '''
}

export default MCNApiClient;

// React Hook for MCN API
import { useState, useCallback } from 'react';

export const useMCNApi = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const client = new MCNApiClient();

  const callApi = useCallback(async (method, data) => {
    setLoading(true);
    setError(null);

    try {
      const result = await client[method](data);
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { callApi, loading, error };
};
'''

        return client_code

    def _generate_vue_client(self, endpoints: List[Dict[str, Any]]) -> str:
        """Generate Vue.js API client"""

        client_code = '''
import axios from 'axios';

class MCNApiClient {
  constructor(baseURL = 'http://localhost:8080') {
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }
'''

        for endpoint in endpoints:
            method_name = endpoint.get('name', 'unknown').replace('-', '_')
            http_method = endpoint.get('method', 'POST').lower()
            path = endpoint.get('path', f'/{method_name}')

            client_code += f'''
  async {method_name}(data = {{}}) {{
    const response = await this.client.{http_method}('{path}', data);
    return response.data;
  }}
'''

        client_code += '''
}

// Vue Plugin
export default {
  install(app) {
    const mcnClient = new MCNApiClient();
    app.config.globalProperties.$mcn = mcnClient;
    app.provide('mcn', mcnClient);
  }
};

// Composable for Vue 3
import { ref, inject } from 'vue';

export const useMCN = () => {
  const mcn = inject('mcn');
  const loading = ref(false);
  const error = ref(null);

  const callApi = async (method, data) => {
    loading.value = true;
    error.value = null;

    try {
      return await mcn[method](data);
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  return { callApi, loading, error };
};
'''

        return client_code

    def _generate_vanilla_client(self, endpoints: List[Dict[str, Any]]) -> str:
        """Generate vanilla JavaScript API client"""

        client_code = '''
class MCNApiClient {
  constructor(baseURL = 'http://localhost:8080') {
    this.baseURL = baseURL;
  }

  async request(endpoint, data = {}, method = 'POST') {
    const url = `${this.baseURL}${endpoint}`;

    try {
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: method !== 'GET' ? JSON.stringify(data) : undefined,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('MCN API Error:', error);
      throw error;
    }
  }
'''

        for endpoint in endpoints:
            method_name = endpoint.get('name', 'unknown').replace('-', '_')
            path = endpoint.get('path', f'/{method_name}')

            client_code += f'''
  async {method_name}(data = {{}}) {{
    return this.request('{path}', data);
  }}
'''

        client_code += '''
}

// Global instance
window.MCN = new MCNApiClient();
'''

        return client_code

    def _generate_angular_client(self, endpoints: List[Dict[str, Any]]) -> str:
        """Generate Angular service"""

        service_code = '''
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class MCNApiService {
  private baseURL = 'http://localhost:8080';

  constructor(private http: HttpClient) {}

  private getHeaders(): HttpHeaders {
    return new HttpHeaders({
      'Content-Type': 'application/json'
    });
  }
'''

        for endpoint in endpoints:
            method_name = endpoint.get('name', 'unknown').replace('-', '_')
            path = endpoint.get('path', f'/{method_name}')

            service_code += f'''
  {method_name}(data: any = {{}}): Observable<any> {{
    return this.http.post(`${{this.baseURL}}{path}`, data, {{
      headers: this.getHeaders()
    }});
  }}
'''

        service_code += '''
}
'''

        return service_code

    def create_frontend_config(self, framework: str, mcn_endpoints: List[Dict[str, Any]]):
        """Create frontend configuration files"""

        log_step(f"Creating frontend config for {framework}")

        # Create API client file
        client_code = self.generate_api_client(mcn_endpoints, framework)

        # Determine file extension and path
        extensions = {
            'react': 'js',
            'vue': 'js',
            'angular': 'ts',
            'vanilla': 'js'
        }

        ext = extensions.get(framework, 'js')
        client_file = self.project_path / f'mcn-api-client.{ext}'

        with open(client_file, 'w') as f:
            f.write(client_code)

        log_step(f"Created API client: {client_file}")

        # Create environment config
        env_config = {
            'MCN_API_URL': 'http://localhost:8080',
            'MCN_ENDPOINTS': {ep.get('name'): ep.get('path') for ep in mcn_endpoints}
        }

        env_file = self.project_path / '.env.mcn'
        with open(env_file, 'w') as f:
            for key, value in env_config.items():
                if isinstance(value, dict):
                    f.write(f"{key}={json.dumps(value)}\n")
                else:
                    f.write(f"{key}={value}\n")

        return {
            'client_file': str(client_file),
            'env_file': str(env_file),
            'framework': framework
        }

    def generate_frontend_examples(self, framework: str, endpoints: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate example frontend code for using MCN APIs"""

        examples = {}

        if framework == 'react':
            examples['component'] = '''
import React, { useState } from 'react';
import { useMCNApi } from './mcn-api-client';

const MCNExample = () => {
  const { callApi, loading, error } = useMCNApi();
  const [result, setResult] = useState(null);

  const handleApiCall = async () => {
    try {
      const data = await callApi('healthcare_patient_management', {
        patient_id: '12345',
        vitals: { heart_rate: 80, blood_pressure: '120/80' }
      });
      setResult(data);
    } catch (err) {
      console.error('API call failed:', err);
    }
  };

  return (
    <div>
      <button onClick={handleApiCall} disabled={loading}>
        {loading ? 'Processing...' : 'Call MCN API'}
      </button>
      {error && <div className="error">Error: {error}</div>}
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
};

export default MCNExample;
'''

        elif framework == 'vue':
            examples['component'] = '''
<template>
  <div>
    <button @click="handleApiCall" :disabled="loading">
      {{ loading ? 'Processing...' : 'Call MCN API' }}
    </button>
    <div v-if="error" class="error">Error: {{ error }}</div>
    <pre v-if="result">{{ JSON.stringify(result, null, 2) }}</pre>
  </div>
</template>

<script>
import { useMCN } from './mcn-api-client';

export default {
  setup() {
    const { callApi, loading, error } = useMCN();
    const result = ref(null);

    const handleApiCall = async () => {
      try {
        const data = await callApi('healthcare_patient_management', {
          patient_id: '12345',
          vitals: { heart_rate: 80, blood_pressure: '120/80' }
        });
        result.value = data;
      } catch (err) {
        console.error('API call failed:', err);
      }
    };

    return { handleApiCall, loading, error, result };
  }
};
</script>
'''

        return examples

# Global frontend integration instance
mcn_frontend = MCNFrontendIntegration()
