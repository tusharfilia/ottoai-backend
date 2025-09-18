# OttoAI Backend - Makefile for Development and Verification

.PHONY: help verify verify:secrets verify:tests verify:all smoke test install clean

help: ## Show this help message
	@echo "OttoAI Backend - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

test: ## Run all tests
	pytest tests/ -v

verify:secrets: ## Verify no hardcoded secrets in codebase
	@echo "🔍 Scanning for hardcoded secrets..."
	@if command -v rg >/dev/null 2>&1; then \
		if rg -n '(sk-[A-Za-z0-9]{20,}|AC[A-Za-z0-9]{32}|pk_[A-Za-z0-9]{20,})' --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude='*.pyc' --exclude='.env*' --exclude='*.md' --exclude='*.yml' --exclude='*.yaml' --exclude='Makefile' --exclude='test_*.py' --exclude='*test*.py' .; then \
			echo "❌ SECRETS FOUND: Hardcoded secrets detected in codebase!"; \
			exit 1; \
		else \
			echo "✅ SECRETS OK: No hardcoded secrets found"; \
		fi; \
	else \
		if grep -r -n -E '(sk-[A-Za-z0-9]{20,}|AC[A-Za-z0-9]{32}|pk_[A-Za-z0-9]{20,})' --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude='*.pyc' --exclude='.env*' --exclude='*.md' --exclude='*.yml' --exclude='*.yaml' --exclude='Makefile' --exclude='test_*.py' --exclude='*test*.py' .; then \
			echo "❌ SECRETS FOUND: Hardcoded secrets detected in codebase!"; \
			exit 1; \
		else \
			echo "✅ SECRETS OK: No hardcoded secrets found"; \
		fi; \
	fi

verify:tests: ## Run foundation verification tests
	@echo "🧪 Running CORS and Tenant tests..."
	pytest -q tests/test_cors_tenant.py
	@echo "🧪 Running Rate Limiting tests..."
	pytest -q tests/test_rate_limiting.py

verify:idempotency: ## Run idempotency verification tests
	@echo "🧪 Running Idempotency tests..."
	pytest -q tests/test_idempotency.py

verify:obs: ## Run observability verification tests
	@echo "🧪 Running Observability tests..."
	pytest -q tests/test_logging_tracing.py
	pytest -q tests/test_metrics.py

verify:all: verify:secrets verify:tests verify:idempotency verify:obs ## Run all verification checks

verify: ## Run complete foundations verification
	@echo "🚀 Starting OttoAI Backend Foundations Verification..."
	@echo ""
	@$(MAKE) verify:secrets
	@echo ""
	@$(MAKE) verify:tests
	@echo ""
	@echo "✅ All foundation verifications passed!"

smoke: ## Run smoke test for foundations
	@echo "💨 Running smoke test for foundations..."
	bash scripts/smoke_foundations.sh

smoke:obs: ## Run smoke test for observability
	@echo "💨 Running smoke test for observability..."
	bash scripts/smoke_obs.sh

validate:infra: ## Validate infrastructure integration
	@echo "🔍 Validating infrastructure integration..."
	python scripts/quick_validation.py

validate:all: ## Run all validation tests
	@echo "🚀 Running comprehensive validation..."
	@$(MAKE) verify:all
	@$(MAKE) smoke:obs
	@$(MAKE) validate:infra

clean: ## Clean up temporary files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
