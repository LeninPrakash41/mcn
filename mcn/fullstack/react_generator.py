"""
React Project Generator for MCN UI Integration
Generates complete React projects from MCN UI definitions
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Any


class ReactProjectGenerator:
    """Generate React projects from MCN UI definitions"""
    
    def __init__(self):
        self.templates_dir = Path(__file__).parent / "templates" / "react"
    
    def generate_project(self, ui_manifest_path: str, output_dir: str, project_name: str):
        """Generate complete React project from UI manifest"""
        
        # Load UI manifest
        with open(ui_manifest_path, 'r') as f:
            manifest = json.load(f)
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate project structure
        self._create_project_structure(output_path)
        
        # Generate package.json
        self._generate_package_json(output_path, project_name)
        
        # Generate React components
        self._generate_components(output_path, manifest)
        
        # Generate routing
        self._generate_routing(output_path, manifest)
        
        # Generate MCN client
        self._generate_mcn_client(output_path)
        
        # Generate styles
        self._generate_styles(output_path)
        
        # Generate configuration files
        self._generate_config_files(output_path)
        
        return f"React project generated at {output_path}"
    
    def _create_project_structure(self, output_path: Path):
        """Create React project directory structure"""
        directories = [
            output_path / "src",
            output_path / "src" / "components",
            output_path / "src" / "pages", 
            output_path / "src" / "services",
            output_path / "src" / "hooks",
            output_path / "src" / "utils",
            output_path / "src" / "styles",
            output_path / "public",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _generate_package_json(self, output_path: Path, project_name: str):
        """Generate package.json"""
        package_json = {
            "name": project_name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "private": True,
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "react-router-dom": "^6.20.1",
                "react-scripts": "5.0.1",
                "typescript": "^5.3.3",
                "@types/react": "^18.2.45",
                "@types/react-dom": "^18.2.18",
                "axios": "^1.6.2",
                "recharts": "^2.8.0",
                "tailwindcss": "^3.3.6",
                "@headlessui/react": "^1.7.17",
                "@heroicons/react": "^2.0.18"
            },
            "scripts": {
                "start": "react-scripts start",
                "build": "react-scripts build", 
                "test": "react-scripts test",
                "eject": "react-scripts eject"
            },
            "eslintConfig": {
                "extends": ["react-app", "react-app/jest"]
            },
            "browserslist": {
                "production": [">0.2%", "not dead", "not op_mini all"],
                "development": ["last 1 chrome version", "last 1 firefox version", "last 1 safari version"]
            },
            "devDependencies": {
                "@types/node": "^20.10.5",
                "autoprefixer": "^10.4.16",
                "postcss": "^8.4.32"
            }
        }
        
        with open(output_path / "package.json", 'w') as f:
            json.dump(package_json, f, indent=2)
    
    def _generate_components(self, output_path: Path, manifest: Dict):
        """Generate React components from manifest"""
        
        # Generate page components
        for page_name, page_data in manifest.get('pages', {}).items():
            self._generate_page_component(output_path, page_name, page_data)
        
        # Generate reusable components
        self._generate_ui_components(output_path)
    
    def _generate_page_component(self, output_path: Path, page_name: str, page_data: Dict):
        """Generate individual page component"""
        
        component_code = f"""import React, {{ useState, useEffect, useCallback }} from 'react';
import {{ useMCN }} from '../services/mcn-client';
import {{ UIButton, UIInput, UIText, UIContainer, UIForm, UITable, UIChart }} from '../components/UIComponents';

interface PageData {{
    [key: string]: any;
}}

interface ApiResponse {{
    success: boolean;
    data?: PageData;
    error?: string;
}}

export function {page_name}Page() {{
    const mcn = useMCN();
    const [data, setData] = useState<PageData>({{}});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    const loadPageData = useCallback(async () => {{
        try {{
            setLoading(true);
            setError(null);
            
            const result: ApiResponse = await mcn.call('load_page_data', {{ page: '{page_name}' }});
            
            if (result?.success && result.data) {{
                setData(result.data);
            }} else {{
                throw new Error(result?.error || 'Failed to load data');
            }}
        }} catch (err) {{
            const errorMessage = err instanceof Error ? err.message : 'Failed to load page data';
            setError(errorMessage);
            console.error('Error loading page data:', err);
        }} finally {{
            setLoading(false);
        }}
    }}, [mcn]);
    
    useEffect(() => {{
        loadPageData();
    }}, [loadPageData]);
    
    const handleRefresh = useCallback(async () => {{
        try {{
            setLoading(true);
            setError(null);
            
            const result: ApiResponse = await mcn.call('refresh_dashboard', {{}});
            
            if (result?.success && result.data) {{
                setData(result.data);
            }} else {{
                throw new Error(result?.error || 'Failed to refresh data');
            }}
        }} catch (err) {{
            const errorMessage = err instanceof Error ? err.message : 'Failed to refresh data';
            setError(errorMessage);
        }} finally {{
            setLoading(false);
        }}
    }}, [mcn]);
    
    if (loading) {{
        return (
            <div className="flex items-center justify-center min-h-screen" role="status" aria-label="Loading">
                <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500" aria-hidden="true"></div>
                <span className="sr-only">Loading...</span>
            </div>
        );
    }}
    
    if (error) {{
        return (
            <div className="flex items-center justify-center min-h-screen" role="alert">
                <div className="text-red-500 text-center max-w-md">
                    <h2 className="text-xl font-bold mb-2">Error</h2>
                    <p className="mb-4">{{error}}</p>
                    <button 
                        onClick={{handleRefresh}}
                        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                        type="button"
                    >
                        Retry
                    </button>
                </div>
            </div>
        );
    }}
    
    return (
        <div className="page page-{page_name.lower()} min-h-screen bg-gray-50">
            {self._generate_page_content(page_data)}
        </div>
    );
}}

export default {page_name}Page;
"""
        
        with open(output_path / "src" / "pages" / f"{page_name}Page.tsx", 'w') as f:
            f.write(component_code)
    
    def _generate_page_content(self, page_data: Dict) -> str:
        """Generate page content JSX"""
        components = page_data.get('components', [])
        
        content_jsx = ""
        for component in components:
            content_jsx += self._component_to_jsx(component)
        
        return content_jsx
    
    def _component_to_jsx(self, component: Dict) -> str:
        """Convert component definition to JSX"""
        comp_type = component.get('type', 'div')
        props = component.get('props', {})
        
        if comp_type == 'button':
            return f"""
            <UIButton 
                text="{props.get('text', 'Button')}"
                className="{props.get('className', 'btn')}"
                onClick={{() => mcn.call('{component.get('events', {}).get('onClick', '')}', {{}})}}
            />"""
        
        elif comp_type == 'input':
            return f"""
            <UIInput 
                placeholder="{props.get('placeholder', '')}"
                className="{props.get('className', 'input')}"
                onChange={{(value) => mcn.call('{component.get('events', {}).get('onChange', '')}', {{value}})}}
            />"""
        
        elif comp_type == 'text':
            return f"""
            <UIText 
                content="{props.get('content', '')}"
                tag="{props.get('tag', 'p')}"
                className="{props.get('className', 'text')}"
            />"""
        
        elif comp_type == 'container':
            children_jsx = ""
            for child in component.get('children', []):
                children_jsx += self._component_to_jsx(child)
            
            return f"""
            <UIContainer className="{props.get('className', 'container')}">
                {children_jsx}
            </UIContainer>"""
        
        elif comp_type == 'table':
            return f"""
            <UITable 
                columns={{[{', '.join([f'"{col}"' for col in props.get('columns', [])])}]}}
                data={{data.{props.get('dataSource', 'tableData')} || []}}
                className="{props.get('className', 'table')}"
            />"""
        
        elif comp_type == 'chart':
            return f"""
            <UIChart 
                type="{props.get('chartType', 'line')}"
                data={{data.{props.get('data', 'chartData')} || []}}
                className="{props.get('className', 'chart')}"
            />"""
        
        return f"<div>Unknown component: {comp_type}</div>"
    
    def _generate_ui_components(self, output_path: Path):
        """Generate reusable UI components"""
        
        ui_components_code = """import React, { useCallback } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface UIButtonProps {
    text: string;
    onClick?: () => void;
    className?: string;
    disabled?: boolean;
}

export function UIButton({ text, onClick, className = 'btn', disabled = false }: UIButtonProps) {
    const handleClick = useCallback(() => {
        if (!disabled && onClick) {
            onClick();
        }
    }, [disabled, onClick]);

    return (
        <button 
            className={`px-4 py-2 rounded font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${className} ${
                disabled ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-80'
            }`}
            onClick={handleClick}
            disabled={disabled}
            type="button"
            aria-label={text}
        >
            {text}
        </button>
    );
}

interface UIInputProps {
    placeholder?: string;
    onChange?: (value: string) => void;
    className?: string;
    type?: string;
}

export function UIInput({ placeholder = '', onChange, className = 'input', type = 'text' }: UIInputProps) {
    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        if (onChange) {
            onChange(e.target.value);
        }
    }, [onChange]);

    return (
        <input
            type={type}
            placeholder={placeholder}
            className={`px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500 ${className}`}
            onChange={handleChange}
            aria-label={placeholder || 'Input field'}
        />
    );
}

interface UITextProps {
    content: string;
    tag?: keyof JSX.IntrinsicElements;
    className?: string;
}

export function UIText({ content, tag: Tag = 'p', className = 'text' }: UITextProps) {
    return <Tag className={className}>{content}</Tag>;
}

interface UIContainerProps {
    children: React.ReactNode;
    className?: string;
}

export function UIContainer({ children, className = 'container' }: UIContainerProps) {
    return <div className={className}>{children}</div>;
}

interface UIFormProps {
    children: React.ReactNode;
    onSubmit?: () => void;
    className?: string;
}

export function UIForm({ children, onSubmit, className = 'form' }: UIFormProps) {
    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSubmit?.();
    };
    
    return (
        <form onSubmit={handleSubmit} className={className}>
            {children}
        </form>
    );
}

interface UITableProps {
    columns: string[];
    data: any[];
    className?: string;
}

export function UITable({ columns, data, className = 'table' }: UITableProps) {
    if (!Array.isArray(data) || !Array.isArray(columns)) {
        return (
            <div className={`p-4 text-center text-gray-500 ${className}`}>
                No data available
            </div>
        );
    }

    return (
        <div className={`overflow-x-auto ${className}`} role="region" aria-label="Data table">
            <table className="min-w-full bg-white border border-gray-200">
                <thead className="bg-gray-50">
                    <tr>
                        {columns.map((column, index) => (
                            <th 
                                key={`header-${index}`} 
                                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                                scope="col"
                            >
                                {column}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                    {data.map((row, rowIndex) => (
                        <tr key={`row-${rowIndex}`}>
                            {columns.map((column, colIndex) => (
                                <td 
                                    key={`cell-${rowIndex}-${colIndex}`} 
                                    className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                                >
                                    {row[column.toLowerCase()] || row[column] || '-'}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

interface UIChartProps {
    type: 'bar' | 'line';
    data: any[];
    className?: string;
}

export function UIChart({ type, data, className = 'chart' }: UIChartProps) {
    const ChartComponent = type === 'bar' ? BarChart : LineChart;
    const DataComponent = type === 'bar' ? Bar : Line;
    
    return (
        <div className={`w-full h-64 ${className}`}>
            <ResponsiveContainer width="100%" height="100%">
                <ChartComponent data={data}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <DataComponent dataKey="value" fill="#8884d8" stroke="#8884d8" />
                </ChartComponent>
            </ResponsiveContainer>
        </div>
    );
}
"""
        
        with open(output_path / "src" / "components" / "UIComponents.tsx", 'w') as f:
            f.write(ui_components_code)
    
    def _generate_routing(self, output_path: Path, manifest: Dict):
        """Generate React Router configuration"""
        
        pages = manifest.get('pages', {})
        
        # Generate imports
        imports = []
        routes = []
        
        for page_name, page_data in pages.items():
            imports.append(f"import {page_name}Page from './pages/{page_name}Page';")
            routes.append(f'<Route path="{page_data.get("path", "/")}" element={{<{page_name}Page />}} />')
        
        router_code = f"""import React from 'react';
import {{ BrowserRouter as Router, Routes, Route }} from 'react-router-dom';
import {{ MCNProvider }} from './services/mcn-client';

{chr(10).join(imports)}

export function AppRouter() {{
    return (
        <MCNProvider endpoint="http://localhost:8000">
            <Router>
                <Routes>
                    {chr(10).join(routes)}
                    <Route path="*" element={{<div>Page not found</div>}} />
                </Routes>
            </Router>
        </MCNProvider>
    );
}}

export default AppRouter;
"""
        
        with open(output_path / "src" / "AppRouter.tsx", 'w') as f:
            f.write(router_code)
    
    def _generate_mcn_client(self, output_path: Path):
        """Generate MCN client service"""
        
        mcn_client_code = """import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import axios, { AxiosError } from 'axios';

interface MCNContextType {
    endpoint: string;
    call: (action: string, data?: any) => Promise<any>;
    loading: boolean;
    error: string | null;
}

const MCNContext = createContext<MCNContextType | null>(null);

export function MCNProvider({ children, endpoint }: { children: React.ReactNode, endpoint: string }) {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    
    const call = useCallback(async (action: string, data: any = {}) => {
        if (!action?.trim()) {
            throw new Error('Action is required');
        }
        
        setLoading(true);
        setError(null);
        
        try {
            const response = await axios.post(`${endpoint}/api/main`, {
                action: action.trim(),
                ...data
            }, {
                headers: {
                    'Content-Type': 'application/json'
                },
                timeout: 30000,
                validateStatus: (status) => status < 500
            });
            
            if (response.status >= 400) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return response.data;
        } catch (err) {
            let errorMessage = 'Network error occurred';
            
            if (err instanceof AxiosError) {
                errorMessage = err.response?.data?.error || 
                              err.response?.data?.message || 
                              err.message || 
                              'Request failed';
            } else if (err instanceof Error) {
                errorMessage = err.message;
            }
            
            setError(errorMessage);
            throw new Error(errorMessage);
        } finally {
            setLoading(false);
        }
    }, [endpoint]);
    
    const contextValue = useMemo(() => ({
        endpoint,
        call,
        loading,
        error
    }), [endpoint, call, loading, error]);
    
    return (
        <MCNContext.Provider value={contextValue}>
            {children}
        </MCNContext.Provider>
    );
}

export function useMCN() {
    const context = useContext(MCNContext);
    if (!context) {
        throw new Error('useMCN must be used within MCNProvider');
    }
    return context;
}

export default MCNProvider;
"""
        
        with open(output_path / "src" / "services" / "mcn-client.tsx", 'w') as f:
            f.write(mcn_client_code)
    
    def _generate_styles(self, output_path: Path):
        """Generate CSS styles"""
        
        # Generate Tailwind config
        tailwind_config = """/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
"""
        
        with open(output_path / "tailwind.config.js", 'w') as f:
            f.write(tailwind_config)
        
        # Generate main CSS
        main_css = """@tailwind base;
@tailwind components;
@tailwind utilities;

/* Custom styles */
.btn {
    @apply px-4 py-2 rounded font-medium transition-colors;
}

.btn-primary {
    @apply bg-blue-500 text-white hover:bg-blue-600;
}

.btn-secondary {
    @apply bg-gray-500 text-white hover:bg-gray-600;
}

.btn-refresh {
    @apply bg-green-500 text-white hover:bg-green-600;
}

.metric-card {
    @apply bg-white p-6 rounded-lg shadow-md;
}

.metric-value {
    @apply text-2xl font-bold text-blue-600;
}

.dashboard-header {
    @apply flex justify-between items-center mb-6 p-4 bg-white rounded-lg shadow;
}

.dashboard-title {
    @apply text-3xl font-bold text-gray-800;
}

.metrics-row {
    @apply grid grid-cols-1 md:grid-cols-3 gap-6 mb-6;
}

.analysis-section {
    @apply bg-white p-6 rounded-lg shadow mb-6;
}

.insights-panel {
    @apply mt-4 p-4 bg-gray-50 rounded border;
}

.tables-section {
    @apply bg-white p-6 rounded-lg shadow;
}

.data-table {
    @apply mb-6;
}

.loading {
    @apply text-center py-8 text-gray-500;
}
"""
        
        with open(output_path / "src" / "styles" / "index.css", 'w') as f:
            f.write(main_css)
    
    def _generate_config_files(self, output_path: Path):
        """Generate configuration files"""
        
        # Generate tsconfig.json
        tsconfig = {
            "compilerOptions": {
                "target": "es5",
                "lib": ["dom", "dom.iterable", "es6"],
                "allowJs": True,
                "skipLibCheck": True,
                "esModuleInterop": True,
                "allowSyntheticDefaultImports": True,
                "strict": True,
                "forceConsistentCasingInFileNames": True,
                "noFallthroughCasesInSwitch": True,
                "module": "esnext",
                "moduleResolution": "node",
                "resolveJsonModule": True,
                "isolatedModules": True,
                "noEmit": True,
                "jsx": "react-jsx"
            },
            "include": ["src"]
        }
        
        with open(output_path / "tsconfig.json", 'w') as f:
            json.dump(tsconfig, f, indent=2)
        
        # Generate public/index.html
        index_html = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%PUBLIC_URL%/favicon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="MCN Full-Stack Application" />
    <title>MCN App</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>
"""
        
        with open(output_path / "public" / "index.html", 'w') as f:
            f.write(index_html)
        
        # Generate src/index.tsx
        index_tsx = """import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/index.css';
import AppRouter from './AppRouter';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <AppRouter />
  </React.StrictMode>
);
"""
        
        with open(output_path / "src" / "index.tsx", 'w') as f:
            f.write(index_tsx)
        
        # Generate README
        readme = """# MCN React Application

This project was generated by MCN UI Integration Layer.

## Available Scripts

### `npm start`
Runs the app in development mode. Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

### `npm run build`
Builds the app for production to the `build` folder.

### `npm test`
Launches the test runner in interactive watch mode.

## MCN Backend

Make sure your MCN backend is running on `http://localhost:8000` for the frontend to connect properly.

## Features

- React with TypeScript
- Tailwind CSS for styling
- React Router for navigation
- Recharts for data visualization
- MCN client integration
- Responsive design

## Project Structure

- `src/components/` - Reusable UI components
- `src/pages/` - Page components
- `src/services/` - MCN client and API services
- `src/styles/` - CSS and styling files
"""
        
        with open(output_path / "README.md", 'w') as f:
            f.write(readme)