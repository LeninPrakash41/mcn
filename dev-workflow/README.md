# MCN Development Workflow - Integrated Approach

This folder contains the integrated development server approach for MCN full-stack development.

## Quick Start

```bash
# Run from mcn root directory
python dev-workflow/mcn_dev_cli.py dev examples/fullstack_integration_complete.mcn
```

## Commands

### Development Server (Integrated)
```bash
python dev-workflow/mcn_dev_cli.py dev script.mcn
python dev-workflow/mcn_dev_cli.py dev script.mcn --port 3000 --frontend-port 3001
```

### Run Script
```bash
python dev-workflow/mcn_dev_cli.py run script.mcn
```

### Generate React App
```bash
python dev-workflow/mcn_dev_cli.py generate script.mcn --output my-app
```

### Interactive REPL
```bash
python dev-workflow/mcn_dev_cli.py repl
```

## Features

- **Integrated Server**: Single command starts both backend and frontend
- **Auto-reload**: Changes trigger automatic rebuilds
- **Unified Logging**: Combined output from both processes
- **Easy Setup**: No separate terminal windows needed

## Comparison with Separate Processes

| Feature | Integrated (dev-workflow) | Separate (core_engine) |
|---------|---------------------------|------------------------|
| Setup | Single command | Multiple commands |
| Terminals | 1 | 2-3 |
| Logging | Combined | Separate |
| Production | Development only | Production ready |
| Control | Less granular | Full control |

## Usage Examples

```bash
# Start development server
cd d:\mcn
python dev-workflow/mcn_dev_cli.py dev examples/business_dashboard.mcn

# Generate standalone React app
python dev-workflow/mcn_dev_cli.py generate examples/ui_integration_demo.mcn --output my-dashboard
```