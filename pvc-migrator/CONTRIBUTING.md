# Contributing

## Local setup

```powershell
python -m pip install -e .[dev]
```

## Required checks

```powershell
pytest
pytest -m integration
pytest -m e2e
mypy src
mkdocs build --strict
```

## Change expectations

- Preserve typed interfaces.
- Add or update tests with every behavior change.
- Update docs for any CLI, execution, or workload-policy change.
- Keep execution paths explicit and safe by default.
