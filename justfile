test path=".":
    uv run coverage run -m pytest -s -vvvv {{path}}

coverage:
    uv run coverage run -m pytest
    uv run coverage report -m
