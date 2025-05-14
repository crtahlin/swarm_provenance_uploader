# Swarm Provenance Uploader

A CLI toolkit to wrap data files within a metadata structure
and upload them to the Swarm network via a Bee gateway.

## Setup

1. Create and activate a virtual environment.
   ```bash
    python -m venv .venv
    source .venv/bin/activate
    # Or on Windows: .\venv\Scripts\activate
   ```
2. Copy `.env.example` to `.env` and adjust values if needed.
   ```bash
    cp .env.example .env
   ```
3. Install in editable mode, including testing dependencies:
    ```bash
    pip install -e .[testing]
    ```

## Configure

Copy .env.example to .env.
Ensure you have a Bee node running and that BEE_GATEWAY_URL in .env points to it.

## Run Tests

(Requires a local Bee node, OR relies on Mocks):
The sample test above mocks the network calls, so it will run without a live Bee node.

```
pytest
``` 

## Usage

```bash
swarm-prov-upload --file /path/to/your/prov_file.txt

# Or with optional params
swarm-prov-upload --file my_prov.txt --std "MY-PROV-STD-V2"
```
Use `swarm-prov-upload --help` for all options.

## Project directory structure

```
swarm_provenance_uploader/
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── swarm_provenance_uploader/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── file_utils.py
│   │   ├── metadata_builder.py
│   │   └── swarm_client.py
│   └── models.py
└── tests/
    ├── __init__.py
    └── test_cli.py
```

