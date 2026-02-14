.PHONY: help setup map

help:
	@echo "Usage:"
	@echo "  make setup  - Install uv and download dependencies"
	@echo "  make map    - Generate great circle route map from logbook.csv"

setup:
	@curl -LsSf https://astral.sh/uv/install.sh | sh
	@uv sync

map:
	@uv run python great_circle_map.py logbook.csv --output map.png && open map.png
