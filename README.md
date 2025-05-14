# swarm_provenance_uploader
A CLI toolkit for wrapping data and uploading to Swarm.

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

