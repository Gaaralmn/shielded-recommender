.PHONY: up down logs test lint build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

build:
	docker-compose build

test:
	docker-compose run --rm gatekeeper pytest
	docker-compose run --rm trainer pytest

lint:
	docker-compose run --rm gatekeeper flake8
	docker-compose run --rm trainer flake8
