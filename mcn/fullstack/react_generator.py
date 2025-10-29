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
                "@radix-ui/react-slot": "^1.0.2",
                "@radix-ui/react-dialog": "^1.0.5",
                "@radix-ui/react-dropdown-menu": "^2.0.6",
                "@radix-ui/react-select": "^2.0.0",
                "@radix-ui/react-toast": "^1.1.5",
                "class-variance-authority": "^0.7.0",
                "clsx": "^2.0.0",
                "tailwind-merge": "^2.0.0",
                "lucide-react": "^0.294.0"
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
                "postcss": "^8.4.32",
                "tailwindcss-animate": "^1.0.7"
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
import { cn } from '../utils/cn';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';

interface UIButtonProps {
    text: string;
    onClick?: () => void;
    className?: string;
    disabled?: boolean;
}

export function UIButton({ text, onClick, className = '', disabled = false }: UIButtonProps) {
    const handleClick = useCallback(() => {
        if (!disabled && onClick) {
            onClick();
        }
    }, [disabled, onClick]);

    return (
        <Button 
            className={cn(className)}
            onClick={handleClick}
            disabled={disabled}
            aria-label={text}
        >
            {text}
        </Button>
    );
}

interface UIInputProps {
    placeholder?: string;
    onChange?: (value: string) => void;
    className?: string;
    type?: string;
}

export function UIInput({ placeholder = '', onChange, className = '', type = 'text' }: UIInputProps) {
    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        if (onChange) {
            onChange(e.target.value);
        }
    }, [onChange]);

    return (
        <Input
            type={type}
            placeholder={placeholder}
            className={cn(className)}
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

export function UITable({ columns, data, className = '' }: UITableProps) {
    if (!Array.isArray(data) || !Array.isArray(columns)) {
        return (
            <Card className={cn('p-4', className)}>
                <CardContent className="text-center text-muted-foreground">
                    No data available
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className={cn(className)}>
            <Table>
                <TableHeader>
                    <TableRow>
                        {columns.map((column, index) => (
                            <TableHead key={`header-${index}`}>
                                {column}
                            </TableHead>
                        ))}
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {data.map((row, rowIndex) => (
                        <TableRow key={`row-${rowIndex}`}>
                            {columns.map((column, colIndex) => (
                                <TableCell key={`cell-${rowIndex}-${colIndex}`}>
                                    {row[column.toLowerCase()] || row[column] || '-'}
                                </TableCell>
                            ))}
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </Card>
    );
}

interface UIChartProps {
    type: 'bar' | 'line';
    data: any[];
    className?: string;
}

export function UIChart({ type, data, className = '' }: UIChartProps) {
    const ChartComponent = type === 'bar' ? BarChart : LineChart;
    const DataComponent = type === 'bar' ? Bar : Line;
    
    return (
        <Card className={cn(className)}>
            <CardContent className="p-6">
                <div className="w-full h-64">
                    <ResponsiveContainer width="100%" height="100%">
                        <ChartComponent data={data}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" />
                            <YAxis />
                            <Tooltip />
                            <Legend />
                            <DataComponent dataKey="value" fill="hsl(var(--primary))" stroke="hsl(var(--primary))" />
                        </ChartComponent>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
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
        
        # Generate Tailwind config with ShadCN
        tailwind_config = """/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: 0 },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: 0 },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
"""
        
        with open(output_path / "tailwind.config.js", 'w') as f:
            f.write(tailwind_config)
        
        # Generate main CSS with ShadCN variables
        main_css = """@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96%;
    --secondary-foreground: 222.2 84% 4.9%;
    --muted: 210 40% 96%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96%;
    --accent-foreground: 222.2 84% 4.9%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 221.2 83.2% 53.3%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --popover: 222.2 84% 4.9%;
    --popover-foreground: 210 40% 98%;
    --primary: 217.2 91.2% 59.8%;
    --primary-foreground: 222.2 84% 4.9%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 224.3 76.3% 94.1%;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}

/* Custom MCN styles */
.metric-card {
    @apply bg-card p-6 rounded-lg shadow-sm border;
}

.metric-value {
    @apply text-2xl font-bold text-primary;
}

.dashboard-header {
    @apply flex justify-between items-center mb-6 p-4 bg-card rounded-lg shadow-sm border;
}

.dashboard-title {
    @apply text-3xl font-bold text-foreground;
}

.metrics-row {
    @apply grid grid-cols-1 md:grid-cols-3 gap-6 mb-6;
}

.loading {
    @apply text-center py-8 text-muted-foreground;
}
"""
        
        with open(output_path / "src" / "styles" / "index.css", 'w') as f:
            f.write(main_css)
    
    def _generate_config_files(self, output_path: Path):
        """Generate configuration files"""
        
        # Generate ShadCN UI components first
        self._generate_shadcn_components(output_path)
        
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
                "jsx": "react-jsx",
                "baseUrl": ".",
                "paths": {
                    "@/*": ["./src/*"]
                }
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
    
    def _generate_shadcn_components(self, output_path: Path):
        """Generate ShadCN UI components"""
        
        # Create ui components directory
        ui_dir = output_path / "src" / "components" / "ui"
        ui_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate utils/cn.ts
        utils_dir = output_path / "src" / "utils"
        utils_dir.mkdir(parents=True, exist_ok=True)
        
        cn_utils = """import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
"""
        
        with open(utils_dir / "cn.ts", 'w') as f:
            f.write(cn_utils)
        
        # Generate Button component
        button_component = """import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/cn"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
"""
        
        with open(ui_dir / "button.tsx", 'w') as f:
            f.write(button_component)
        
        # Generate Input component
        input_component = """import * as React from "react"

import { cn } from "@/utils/cn"

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
"""
        
        with open(ui_dir / "input.tsx", 'w') as f:
            f.write(input_component)
        
        # Generate Card component
        card_component = """import * as React from "react"

import { cn } from "@/utils/cn"

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border bg-card text-card-foreground shadow-sm",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "text-2xl font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-0", className)}
    {...props}
  />
))
CardFooter.displayName = "CardFooter"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
"""
        
        with open(ui_dir / "card.tsx", 'w') as f:
            f.write(card_component)
        
        # Generate Table component
        table_component = """import * as React from "react"

import { cn } from "@/utils/cn"

const Table = React.forwardRef<
  HTMLTableElement,
  React.HTMLAttributes<HTMLTableElement>
>(({ className, ...props }, ref) => (
  <div className="relative w-full overflow-auto">
    <table
      ref={ref}
      className={cn("w-full caption-bottom text-sm", className)}
      {...props}
    />
  </div>
))
Table.displayName = "Table"

const TableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead ref={ref} className={cn("[&_tr]:border-b", className)} {...props} />
))
TableHeader.displayName = "TableHeader"

const TableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody
    ref={ref}
    className={cn("[&_tr:last-child]:border-0", className)}
    {...props}
  />
))
TableBody.displayName = "TableBody"

const TableFooter = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tfoot
    ref={ref}
    className={cn(
      "border-t bg-muted/50 font-medium [&>tr]:last:border-b-0",
      className
    )}
    {...props}
  />
))
TableFooter.displayName = "TableFooter"

const TableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn(
      "border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted",
      className
    )}
    {...props}
  />
))
TableRow.displayName = "TableRow"

const TableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <th
    ref={ref}
    className={cn(
      "h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0",
      className
    )}
    {...props}
  />
))
TableHead.displayName = "TableHead"

const TableCell = React.forwardRef<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <td
    ref={ref}
    className={cn("p-4 align-middle [&:has([role=checkbox])]:pr-0", className)}
    {...props}
  />
))
TableCell.displayName = "TableCell"

const TableCaption = React.forwardRef<
  HTMLTableCaptionElement,
  React.HTMLAttributes<HTMLTableCaptionElement>
>(({ className, ...props }, ref) => (
  <caption
    ref={ref}
    className={cn("mt-4 text-sm text-muted-foreground", className)}
    {...props}
  />
))
TableCaption.displayName = "TableCaption"

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
"""
        
        with open(ui_dir / "table.tsx", 'w') as f:
            f.write(table_component)