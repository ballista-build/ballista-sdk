test:
    uv run coverage run -m pytest -s -vvvv

coverage:
    uv run coverage run -m pytest
    uv run coverage report -m
