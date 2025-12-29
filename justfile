uv := require("uv")

[private]
default:
    just --list

# Run tests
test_units path=".":
    uv run coverage run -m pytest -m unit -s -vvvv {{path}}
test path=".":
    uv run coverage run -m pytest -s -vvvv {{path}}

# Generate and report coverage
coverage:
    uv run coverage run -m pytest
    uv run coverage report -m
