# AtomsX Makefile
# Convenient commands for development and production environments

.PHONY: dev prod down build-prod logs clean help auth-clean

# Default target
help:
	@echo "AtomsX Docker Compose Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  dev          Start development environment (with debug ports exposed)"
	@echo "  dev-d        Start development environment (detached)"
	@echo "  prod         Start production environment (minimal port exposure)"
	@echo "  down         Stop all services"
	@echo "  build-prod   Build production images"
	@echo "  build-dev    Build development images"
	@echo "  logs         View all service logs"
	@echo "  logs-backend View backend logs"
	@echo "  logs-frontend View frontend logs"
	@echo "  logs-celery  View celery logs"
	@echo "  restart      Quick restart backend and frontend"
	@echo "  migrate      Run database migrations"
	@echo "  superuser    Create Django superuser"
	@echo "  clean        Remove volumes and containers (destructive)"
	@echo "  auth-clean   Remove Authentik data only (destructive)"
	@echo "  help         Show this help message"

# Development environment - exposes debug ports (8000, 5173, 5432, 6379, 9000)
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Development environment in detached mode
dev-d:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Production environment - minimal port exposure (80/443 only)
prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Stop all services
down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.prod.yml down

# Stop and remove volumes (destructive)
clean:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.prod.yml down -v
	@echo "All volumes removed. Data is gone."

# Remove Authentik data only (preserves main app data)
auth-clean:
	rm -rf .dev-cache/docker/authentik
	@echo "Authentik data removed. OIDC config will need to be re-created on next startup."

# Build production images
build-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# View all logs
logs:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

# View specific service logs
logs-backend:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f backend

logs-frontend:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f frontend

logs-celery:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f celery-worker

logs-authentik:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f authentik-server

# Rebuild development images
build-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml build

# Quick restart (for development)
restart:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml restart backend frontend

# Database migrations
migrate:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend uv run python manage.py migrate

# Create superuser
superuser:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml exec backend uv run python manage.py createsuperuser