# Setup And Run

## Local setup

1. Create and activate a Python 3.12 virtual environment.
2. Install the package in editable mode:
   - `pip install -e .[dev]`
3. Optionally copy `config/persona-profiles.example.json` into your own seed file.

## Run the HTTP app

- `uvicorn finkernel.main:app --reload`

Health check:

- `GET http://localhost:8000/api/health`

## Run the MCP server over stdio

- `powershell -ExecutionPolicy Bypass -File .\scripts\run-mcp-stdio.ps1`

## Useful local checks

- `pytest`
- `python .\scripts\verify-investment-routing-contract.py`
