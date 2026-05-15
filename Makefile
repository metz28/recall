.PHONY: help build up down logs test clean

help:
	@echo "Recall - Personal Knowledge Base"
	@echo ""
	@echo "Commands:"
	@echo "  make build    - Build Docker containers"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make logs     - View logs"
	@echo "  make test     - Run tests"
	@echo "  make clean    - Clean up data and containers"
	@echo "  make shell    - Open a shell in the API container"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "✅ Services started!"
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/docs"
	@echo "Qdrant: http://localhost:6333/dashboard"

down:
	docker-compose down

logs:
	docker-compose logs -f

restart:
	docker-compose restart

test:
	docker-compose exec api pytest tests/ -v

shell:
	docker-compose exec api /bin/bash

clean:
	docker-compose down -v
	rm -rf data/
	@echo "⚠️  All data has been deleted!"

format:
	docker-compose exec api black .
	docker-compose exec api ruff check --fix .

dev:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000
