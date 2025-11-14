.PHONY: help build build-python build-java build-node test test-python test-java test-node clean install validate

help:
	@echo "DebugIn Multi-Runtime Debugger - Build & Test"
	@echo ""
	@echo "Usage:"
	@echo "  make build           - Build all runtimes (Python, Java, Node)"
	@echo "  make build-python    - Build Python package"
	@echo "  make build-java      - Build Java agent-core JAR"
	@echo "  make build-node      - Prepare Node.js package"
	@echo ""
	@echo "  make test            - Run all tests (Python, Java, Node)"
	@echo "  make test-python     - Run Python test suite"
	@echo "  make test-java       - Run Java integration tests"
	@echo "  make test-node       - Run Node.js test suite"
	@echo ""
	@echo "  make install         - Install Python package in development mode"
	@echo "  make clean           - Remove build artifacts"
	@echo "  make validate        - Run component validation across all runtimes"

# ==============================================================================
# PYTHON RUNTIME
# ==============================================================================

.PHONY: build-python test-python
build-python:
	@echo "Building Python package (tracepointdebug)..."
	cd . && python -m pip install -e .

test-python:
	@echo "Running Python tests..."
	cd . && python -m pytest tests/ -v

# ==============================================================================
# JAVA RUNTIME
# ==============================================================================

.PHONY: build-java test-java
build-java:
	@echo "Building Java agent-core..."
	@if [ -d "agent-core" ]; then \
		cd agent-core && mvn clean verify -DskipTests; \
	else \
		echo "Warning: agent-core directory not found. Skipping Java build."; \
	fi

test-java:
	@echo "Running Java integration tests..."
	@if [ -d "agent-core" ]; then \
		cd agent-core && mvn clean verify; \
	else \
		echo "Warning: agent-core directory not found. Skipping Java tests."; \
	fi

# ==============================================================================
# NODE.JS RUNTIME
# ==============================================================================

.PHONY: build-node test-node
build-node:
	@echo "Preparing Node.js package..."
	@if [ -d "tracepointdebug_final_library" ]; then \
		cd tracepointdebug_final_library && npm install; \
	else \
		echo "Warning: tracepointdebug_final_library directory not found. Skipping Node build."; \
	fi

test-node:
	@echo "Running Node.js tests..."
	@if [ -f "tests/node_test_plan.js" ]; then \
		node tests/node_test_plan.js; \
	else \
		echo "Warning: Node test plan not found. Skipping Node tests."; \
	fi

# ==============================================================================
# AGGREGATE TARGETS
# ==============================================================================

build: build-python build-java build-node
	@echo "✓ All runtimes built successfully"

test: test-python test-java test-node
	@echo "✓ All runtime tests completed"

install:
	@echo "Installing Python package in development mode..."
	python -m pip install -e .

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@if [ -d "agent-core" ]; then \
		cd agent-core && mvn clean 2>/dev/null || true; \
	fi
	@if [ -d "tracepointdebug_final_library" ]; then \
		cd tracepointdebug_final_library && rm -rf node_modules 2>/dev/null || true; \
	fi

validate:
	@echo "Running component validation..."
	python scripts/component_validation.py

# ==============================================================================
# DOCKER TARGETS (Optional - for future CI environments)
# ==============================================================================

.PHONY: docker-build docker-test
docker-build:
	@echo "Building Docker image for multi-runtime testing..."
	docker build -t debugin:latest .

docker-test:
	@echo "Running tests in Docker container..."
	docker run --rm debugin:latest make test
