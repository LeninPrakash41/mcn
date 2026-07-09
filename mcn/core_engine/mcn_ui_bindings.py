"""
MCN UI Bindings - Integration Layer for Full-Stack Development
Enables UI component definition and binding via MCN scripts
"""

import json
import os
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict


@dataclass
class UIComponent:
    """UI Component definition"""
    type: str
    props: Dict[str, Any]
    children: List['UIComponent'] = None
    events: Dict[str, str] = None
    id: Optional[str] = None


@dataclass
class UIPage:
    """UI Page definition"""
    name: str
    path: str
    components: List[UIComponent]
    layout: str = "default"
    meta: Dict[str, Any] = None


class UIBindingManager:
    """Manages UI component bindings and generation"""
    
    def __init__(self):
        self.components = {}
        self.pages = {}
        self.layouts = {}
        self.event_handlers = {}
        self.data_bindings = {}
    
    def create_component(self, component_type: str, **props):
        """Create UI component with props"""
        component_id = props.get('id', f"{component_type}_{len(self.components)}")
        
        component = UIComponent(
            type=component_type,
            props=props,
            children=props.get('children', []),
            events=props.get('events', {}),
            id=component_id
        )
        
        self.components[component_id] = component
        return component_id
    
    def button(self, text: str, onClick: str = None, **props):
        """Create button component"""
        events = {}
        if onClick:
            events['onClick'] = onClick
            
        return self.create_component('button', 
            text=text, 
            events=events,
            **props
        )
    
    def input(self, placeholder: str = "", onChange: str = None, **props):
        """Create input component"""
        events = {}
        if onChange:
            events['onChange'] = onChange
            
        return self.create_component('input',
            placeholder=placeholder,
            events=events,
            **props
        )
    
    def text(self, content: str, **props):
        """Create text component"""
        return self.create_component('text',
            content=content,
            **props
        )
    
    def container(self, children: List[str] = None, **props):
        """Create container component"""
        return self.create_component('container',
            children=children or [],
            **props
        )
    
    def form(self, children: List[str] = None, onSubmit: str = None, **props):
        """Create form component"""
        events = {}
        if onSubmit:
            events['onSubmit'] = onSubmit
            
        return self.create_component('form',
            children=children or [],
            events=events,
            **props
        )
    
    def table(self, columns: List[str], dataSource: str = None, **props):
        """Create table component"""
        return self.create_component('table',
            columns=columns,
            dataSource=dataSource,
            **props
        )
    
    def chart(self, chart_type: str, data: str = None, **props):
        """Create chart component"""
        return self.create_component('chart',
            chartType=chart_type,
            data=data,
            **props
        )
    
    def agent_chat(self, agent_name: str, **props):
        """Create an AI Agent Chat component"""
        return self.create_component('agent_chat',
            agentName=agent_name,
            **props
        )
    
    def enterprise_search(self, datasource_name: str, **props):
        """Create an Enterprise Search (RAG) component"""
        return self.create_component('enterprise_search',
            datasourceName=datasource_name,
            **props
        )
    
    def create_page(self, name: str, path: str, components: List[str], **meta):
        """Create UI page"""
        page = UIPage(
            name=name,
            path=path,
            components=[self.components[comp_id] for comp_id in components if comp_id in self.components],
            meta=meta
        )
        
        self.pages[name] = page
        return name
    
    def bind_data(self, component_id: str, data_source: str):
        """Bind component to data source"""
        self.data_bindings[component_id] = data_source
    
    def register_event_handler(self, handler_name: str, mcn_function: str):
        """Register event handler"""
        self.event_handlers[handler_name] = mcn_function
    
    def generate_react_component(self, component: Any) -> str:
        """Generate React component code"""
        if isinstance(component, str):
            if component in self.components:
                component = self.components[component]
            else:
                return f"<div>Unknown component ID: {component}</div>"

        component_name = component.type.capitalize()
        
        if component.type == 'button':
            return self._generate_button_react(component)
        elif component.type == 'input':
            return self._generate_input_react(component)
        elif component.type == 'text':
            return self._generate_text_react(component)
        elif component.type == 'container':
            return self._generate_container_react(component)
        elif component.type == 'form':
            return self._generate_form_react(component)
        elif component.type == 'table':
            return self._generate_table_react(component)
        elif component.type == 'chart':
            return self._generate_chart_react(component)
        elif component.type == 'agent_chat':
            return self._generate_agent_chat_react(component)
        elif component.type == 'enterprise_search':
            return self._generate_enterprise_search_react(component)
        else:
            return f"<div>Unknown component: {component.type}</div>"
    
    def _generate_button_react(self, component: UIComponent) -> str:
        """Generate React button component"""
        props = component.props
        events = component.events or {}
        
        onclick_handler = ""
        if 'onClick' in events:
            onclick_handler = f"onClick={{() => mcn.call('{events['onClick']}', {{}})}}"
        
        return f"""<button 
            className="{props.get('className', 'btn')}"
            {onclick_handler}
            disabled={{{str(props.get('disabled', False)).lower()}}}
        >
            {props.get('text', 'Button')}
        </button>"""
    
    def _generate_input_react(self, component: UIComponent) -> str:
        """Generate React input component"""
        props = component.props
        events = component.events or {}
        
        onchange_handler = ""
        if 'onChange' in events:
            onchange_handler = f"onChange={{(e) => mcn.call('{events['onChange']}', {{value: e.target.value}})}}"
        
        return f"""<input
            type="{props.get('type', 'text')}"
            placeholder="{props.get('placeholder', '')}"
            className="{props.get('className', 'input')}"
            {onchange_handler}
        />"""
    
    def _generate_text_react(self, component: UIComponent) -> str:
        """Generate React text component"""
        props = component.props
        tag = props.get('tag', 'p')
        
        return f"""<{tag} className="{props.get('className', 'text')}">
            {props.get('content', '')}
        </{tag}>"""
    
    def _generate_container_react(self, component: UIComponent) -> str:
        """Generate React container component"""
        props = component.props
        children_jsx = ""
        
        if component.children:
            for child in component.children:
                children_jsx += self.generate_react_component(child)
        
        return f"""<div className="{props.get('className', 'container')}">
            {children_jsx}
        </div>"""
    
    def _generate_form_react(self, component: UIComponent) -> str:
        """Generate React form component"""
        props = component.props
        events = component.events or {}
        
        onsubmit_handler = ""
        if 'onSubmit' in events:
            onsubmit_handler = f"onSubmit={{(e) => {{ e.preventDefault(); mcn.call('{events['onSubmit']}', {{}}); }}}}"
        
        children_jsx = ""
        if component.children:
            for child in component.children:
                children_jsx += self.generate_react_component(child)
        
        return f"""<form 
            className="{props.get('className', 'form')}"
            {onsubmit_handler}
        >
            {children_jsx}
        </form>"""
    
    def _generate_table_react(self, component: UIComponent) -> str:
        """Generate React table component"""
        props = component.props
        columns = props.get('columns', [])
        data_source = props.get('dataSource', 'data')
        
        columns_jsx = "".join([f"<th>{col}</th>" for col in columns])
        
        return f"""<table className="{props.get('className', 'table')}">
            <thead>
                <tr>{columns_jsx}</tr>
            </thead>
            <tbody>
                {{{data_source}.map((item, index) => (
                    <tr key={{index}}>
                        {{{', '.join([f"<td>{{item.{col.lower()}}}</td>" for col in columns])}}}
                    </tr>
                ))}}
            </tbody>
        </table>"""
    
    def _generate_chart_react(self, component: UIComponent) -> str:
        """Generate React chart component"""
        props = component.props
        chart_type = props.get('chartType', 'bar')
        data_source = props.get('data', 'chartData')
        
        return f"""<div className={`chart-container ${props.get('className', '')}`}>
            <Chart type="{chart_type}" data={{{data_source}}} />
        </div>"""
    
    def _generate_agent_chat_react(self, component: UIComponent) -> str:
        props = component.props
        agent_name = props.get('agentName', 'Agent')
        return f"""<div className="agent-chat-container p-4 border border-gray-800 rounded-xl shadow-2xl bg-gray-900 text-white">
            <h3 className="font-bold mb-4 text-xl bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-500">Chat with {agent_name}</h3>
            <div className="chat-messages h-64 overflow-y-auto mb-4 p-4 bg-gray-950 rounded-lg border border-gray-800">
                {{/* Messages will be rendered here dynamically */}}
            </div>
            <div className="chat-input flex space-x-2">
                <input type="text" className="flex-1 p-3 border border-gray-700 bg-gray-800 rounded-lg focus:outline-none focus:border-blue-500 transition-colors" placeholder="Type your message..." />
                <button className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium transition-colors shadow-lg shadow-blue-900/20" onClick={{() => mcn.call('agent_chat', {{agent: '{agent_name}'}})}}>Send</button>
            </div>
        </div>"""

    def _generate_enterprise_search_react(self, component: UIComponent) -> str:
        props = component.props
        ds_name = props.get('datasourceName', 'Knowledge Base')
        return f"""<div className="enterprise-search-container p-4 border border-gray-800 rounded-xl shadow-2xl bg-gray-900 text-white">
            <h3 className="font-bold mb-4 text-xl bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-purple-500">Search {ds_name}</h3>
            <div className="search-bar flex space-x-2 mb-4">
                <input type="text" className="flex-1 p-3 border border-gray-700 bg-gray-800 rounded-lg focus:outline-none focus:border-indigo-500 transition-colors" placeholder="Search enterprise data..." />
                <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-lg font-medium transition-colors shadow-lg shadow-indigo-900/20" onClick={{() => mcn.call('rag_query', {{datasource: '{ds_name}'}})}}>Search</button>
            </div>
            <div className="search-results min-h-32 p-4 bg-gray-950 rounded-lg border border-gray-800">
                <p className="text-gray-500 text-sm italic">Enter a query to search across connected data sources.</p>
            </div>
        </div>"""

    def generate_page_component(self, page_name: str) -> str:
        """Generate complete React page component"""
        if page_name not in self.pages:
            return f"// Page '{page_name}' not found"
        
        page = self.pages[page_name]
        
        # Generate imports
        imports = """import React, { useState, useEffect } from 'react';
import { useMCN } from '../services/mcn-client';"""
        
        # Generate component JSX
        components_jsx = ""
        for component in page.components:
            components_jsx += self.generate_react_component(component)
        
        # Generate page component
        page_component = f"""
{imports}

export function {page.name}Page() {{
    const mcn = useMCN();
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {{
        // Load initial data
        const loadData = async () => {{
            try {{
                const result = await mcn.call('load_page_data', {{ page: '{page.name}' }});
                if (result.success) {{
                    setData(result.data);
                }}
            }} catch (error) {{
                console.error('Error loading page data:', error);
            }} finally {{
                setLoading(false);
            }}
        }};
        
        loadData();
    }}, [mcn]);
    
    if (loading) {{
        return <div className="loading">Loading...</div>;
    }}
    
    return (
        <div className="page page-{page.name.lower()}">
            {components_jsx}
        </div>
    );
}}

export default {page.name}Page;
"""
        
        return page_component
    
    def export_to_react_project(self, output_dir: str):
        """Export all UI definitions to React project"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate page components
        pages_dir = os.path.join(output_dir, 'pages')
        os.makedirs(pages_dir, exist_ok=True)
        
        for page_name, page in self.pages.items():
            page_code = self.generate_page_component(page_name)
            
            with open(os.path.join(pages_dir, f"{page_name}Page.tsx"), 'w') as f:
                f.write(page_code)
        
        # Generate routing configuration
        self._generate_routing_config(output_dir)
        
        # Generate UI manifest
        self._generate_ui_manifest(output_dir)
    
    def _generate_routing_config(self, output_dir: str):
        """Generate React Router configuration"""
        routes = []
        
        for page_name, page in self.pages.items():
            routes.append({
                'path': page.path,
                'component': f"{page_name}Page",
                'name': page.name
            })
        
        routing_code = f"""import React from 'react';
import {{ BrowserRouter as Router, Routes, Route }} from 'react-router-dom';

// Import page components
{chr(10).join([f"import {page.name}Page from './pages/{page.name}Page';" for page in self.pages.values()])}

export function AppRouter() {{
    return (
        <Router>
            <Routes>
                {chr(10).join([f'<Route path="{page.path}" element={{<{page.name}Page />}} />' for page in self.pages.values()])}
            </Routes>
        </Router>
    );
}}

export default AppRouter;
"""
        
        with open(os.path.join(output_dir, 'AppRouter.tsx'), 'w') as f:
            f.write(routing_code)
    
    def _generate_ui_manifest(self, output_dir: str):
        """Generate UI manifest for MCN integration"""
        manifest = {
            'pages': {name: asdict(page) for name, page in self.pages.items()},
            'components': {comp_id: asdict(comp) for comp_id, comp in self.components.items()},
            'event_handlers': self.event_handlers,
            'data_bindings': self.data_bindings
        }
        
        with open(os.path.join(output_dir, 'ui-manifest.json'), 'w') as f:
            json.dump(manifest, f, indent=2, default=str)

    def export_to_flutter_project(self, output_dir: str):
        """Export all UI definitions to Flutter project"""
        os.makedirs(output_dir, exist_ok=True)
        self._generate_ui_manifest(output_dir)
        
        manifest_path = os.path.join(output_dir, "ui-manifest.json")
        from mcn.fullstack.flutter_generator import FlutterProjectGenerator
        generator = FlutterProjectGenerator()
        generator.generate_project(manifest_path, output_dir, "MCN_App")


class UIIntegrationLayer:
    """Integration layer for MCN-React communication"""
    
    def __init__(self, interpreter):
        self.interpreter = interpreter
        self.ui_manager = UIBindingManager()
        self._register_ui_functions()
    
    def _register_ui_functions(self):
        """Register UI functions in MCN interpreter"""
        ui_functions = {
            'ui_button': self._ui_button,
            'ui_input': self._ui_input,
            'ui_text': self._ui_text,
            'ui_container': self._ui_container,
            'ui_form': self._ui_form,
            'ui_table': self._ui_table,
            'ui_chart': self._ui_chart,
            'ui_agent_chat': self._ui_agent_chat,
            'ui_enterprise_search': self._ui_enterprise_search,
            'ui_page': self._ui_page,
            'ui_bind_data': self._ui_bind_data,
            'ui_export': self._ui_export,
            'ui_export_flutter': self._ui_export_flutter,
        }
        
        self.interpreter.functions.update(ui_functions)
    
    def _ui_button(self, text: str, onClick: str = None, **props):
        """MCN function: Create button"""
        return self.ui_manager.button(text, onClick, **props)
    
    def _ui_input(self, placeholder: str = "", onChange: str = None, **props):
        """MCN function: Create input"""
        return self.ui_manager.input(placeholder, onChange, **props)
    
    def _ui_text(self, content: str, **props):
        """MCN function: Create text"""
        return self.ui_manager.text(content, **props)
    
    def _ui_container(self, *children, **props):
        """MCN function: Create container"""
        return self.ui_manager.container(list(children), **props)
    
    def _ui_form(self, *children, onSubmit: str = None, **props):
        """MCN function: Create form"""
        return self.ui_manager.form(list(children), onSubmit, **props)
    
    def _ui_table(self, columns: List[str], dataSource: str = None, **props):
        """MCN function: Create table"""
        return self.ui_manager.table(columns, dataSource, **props)
    
    def _ui_chart(self, chart_type: str, data: str = None, **props):
        """MCN function: Create chart"""
        return self.ui_manager.chart(chart_type, data, **props)
    
    def _ui_agent_chat(self, agent_name: str, **props):
        """MCN function: Create agent chat"""
        return self.ui_manager.agent_chat(agent_name, **props)
        
    def _ui_enterprise_search(self, datasource_name: str, **props):
        """MCN function: Create enterprise search"""
        return self.ui_manager.enterprise_search(datasource_name, **props)
    
    def _ui_page(self, name: str, path: str, *components, **meta):
        """MCN function: Create page"""
        return self.ui_manager.create_page(name, path, list(components), **meta)
    
    def _ui_bind_data(self, component_id: str, data_source: str):
        """MCN function: Bind data to component"""
        return self.ui_manager.bind_data(component_id, data_source)
    
    def _ui_export(self, output_dir: str):
        """MCN function: Export UI to React project"""
        self.ui_manager.export_to_react_project(output_dir)
        return f"UI exported to {output_dir}"

    def _ui_export_flutter(self, output_dir: str):
        """MCN function: Export UI to Flutter project"""
        self.ui_manager.export_to_flutter_project(output_dir)
        return f"UI exported to Flutter at {output_dir}"