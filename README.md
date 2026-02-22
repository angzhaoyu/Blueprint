# Blueprint Project

This project contains a Blueprint application with UI components, page transitions, and state management.

## Project Structure

- `XYC2/` - Main project directory containing UI assets and configurations
  - `images/` - Contains UI images for various screens
  - `task/` - Contains page transition and state definitions
    - `page-change/` - Page transition JSON and image files
    - `page-states/` - Page state definitions
    - `pop-change/` - Popup transition definitions
    - `pop-states/` - Popup state definitions
    - `states.txt` - Text file with state information
  - `project.json` - Main project configuration file
- `blueprint_canvas.py` - Canvas-related functionality
- `blueprint_editor.py` - Editor functionality
- `blueprint_export.py` - Export functionality
- `blueprint_model.py` - Model/data structure definitions
- `__pycache__/` - Python compiled bytecode cache

## Features

- Multi-page UI navigation
- State management for different screen states
- Page transition handling
- Popup window support
- Configuration-driven UI design

## Setup

1. Ensure you have Python installed on your system
2. Install any required dependencies (check for requirements.txt if available)

## Usage

Run the main editor script to work with the Blueprint project:

```bash
python blueprint_editor.py
```

## License

This project does not specify a license. Check with the project maintainers for licensing information.
