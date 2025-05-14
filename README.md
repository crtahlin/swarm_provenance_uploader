# Swarm Provenance Uploader

A CLI toolkit to wrap data files within a metadata structure
and upload them to the Swarm network via a Bee gateway.

## Setup

1. Create and activate a virtual environment.
   ```bash
    python -m venv .venv
    source .venv/bin/activate
   ```
2. Copy `.env.example` to `.env` and adjust values if needed.
   ```bash
    cp .env.example .env
   ```
3. Install in editable mode, including testing dependencies:
    ```bash
    pip install -e .[testing]
    ```

## Usage

```bash
swarm-prov-upload --file /path/to/your/file.txt
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

