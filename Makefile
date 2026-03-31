.PHONY: help validate-all validate-frontend validate-backend smoke-test clean-smoke

help:
	@echo "Available targets:"
	@echo "  validate-all      - Run all blocking static checks and tests"
	@echo "  validate-frontend - Run frontend linter and type checks"
	@echo "  validate-backend  - Run Python linter, type checks, and pytest"
	@echo "  smoke-test        - Run the happy-path CLI proof on hype_reel.mp4"
	@echo "  clean-smoke       - Wipe the smoke_test output directory"

validate-all: validate-frontend validate-backend

validate-frontend:
	@echo "Running frontend validation..."
	cd web && npm run lint

validate-backend:
	@echo "Running backend validation..."
	poetry run ruff check src/ tests/
	poetry run pytest

clean-smoke:
	@echo "Clearing smoke test output directory..."
	rm -rf output/smoke_test
	mkdir -p output/smoke_test

smoke-test: clean-smoke
	@echo "Running happy-path CLI smoke test..."
	poetry run content-ai scan --input hype_reel.mp4 --output output/smoke_test
	@echo "Verifying structured success artifact..."
	@if [ ! -f "output/smoke_test/run_001/run_meta.json" ]; then \
		echo "ERROR: run_meta.json not found in output/smoke_test/run_001!"; \
		exit 1; \
	fi
	@echo "Verifying video output existence..."
	@if ! ls output/smoke_test/run_001/montage*.mp4 >/dev/null 2>&1 && ! ls output/smoke_test/run_001/clip_*.mp4 >/dev/null 2>&1; then \
		echo "ERROR: No output montage or clips found in output/smoke_test/run_001!"; \
		exit 1; \
	fi
	@echo "Smoke test passed successfully."
