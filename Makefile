POETRY_VIRTUALENVS_IN_PROJECT = true
GIT_AUTO_MERGE_REPO ?= git@github.com:clintmod/git_auto_merge_test.git
IMAGE_NAME ?= clintmod/git-auto-merge
export

.DEFAULT_GOAL := all

.PHONY: test-unit-update

BIN = .venv/bin/git-auto-merge
VERSION = $(shell yq .tool.poetry.version pyproject.toml)
SRC = Makefile .venv pyproject.toml .git-auto-merge.json \
	  $(shell find src tests -name '*.py') \
	  $(shell find tests -name '*.txt')

$(BIN): pyproject.toml Makefile .venv
	poetry install

all: reports format build test-unit lint test-integration

dev: reports format build test-unit lint

reports:
	mkdir -p reports

reports/format.ansi: $(SRC)
	poetry run black . && poetry run isort . | tee -i reports/format.ansi

format: reports/format.ansi

build: $(BIN)

reports/test-unit.ansi: $(SRC)
	unbuffer poetry run pytest -vvv \
		--tb=long \
		--cov=src \
		--cov-report term-missing:skip-covered \
		$(EXTRA_TEST_ARGS) \
	tests/unit \
	| tee -i reports/test-unit.ansi

test-unit: reports/test-unit.ansi
	
test-unit-update:
	EXTRA_TEST_ARGS="--snapshot-update" make test-unit

reports/test-integration.ansi: $(SRC)
	unbuffer poetry run pytest -vvv \
		--tb=long \
		$(EXTRA_TEST_ARGS) \
	tests/integration \
	| tee -i reports/test-integration.ansi

test-integration: reports/test-integration.ansi

reports/safety.ansi: pyproject.toml
	scripts/safety.sh

safety: reports/safety.ansi

dry-run:
	poetry run $(BIN) --dry-run

run:
	poetry run $(BIN) $(EXTRA_RUN_ARGS)

reports/lint.ansi: $(SRC)
	poetry run pylint -j4 -f colorized src tests | tee -i reports/lint.ansi

lint: reports/lint.ansi

clean-reports:
	rm -rf reports/*

tag:
	git tag v$(VERSION)

git-push:
	git push --tags
	git push

docker-build:
	docker build \
		--build-arg PYTHON_VERSION=$(shell cat .python-version) \
		-t $(IMAGE_NAME):$(VERSION) \
	.

docker-test:
	docker run \
		-it --rm \
		-e GIT_AUTO_MERGE_REPO=https://github.com/clintmod/git_auto_merge_test.git \
		-e DEBUG=1 \
		-v $(HOME)/.ssh:/home/app/.ssh \
	$(IMAGE_NAME):$(VERSION) \
		--dry-run

docker-build-builder:
	docker build \
		--target=builder \
		--build-arg PYTHON_VERSION=$(shell cat .python-version) \
		-t $(IMAGE_NAME):builder \
	.

docker-push:
	docker push $(IMAGE_NAME):$(VERSION)
	docker tag $(IMAGE_NAME):$(VERSION) $(IMAGE_NAME):latest
	docker push $(IMAGE_NAME):latest

docker-shell:
	docker run \
		-it --rm --entrypoint= \
		-e GIT_AUTO_MERGE_REPO=$(GIT_AUTO_MERGE_REPO) \
		-e DEBUG=1 \
		-v $(HOME)/.ssh:/home/app/.ssh \
	$(IMAGE_NAME):$(VERSION) \
	bash

docker-run:
	docker run \
		-it --rm \
		-e GIT_AUTO_MERGE_REPO=$(GIT_AUTO_MERGE_REPO) \
		-e DEBUG=1 \
		-v $(HOME)/.ssh:/home/app/.ssh \
	$(IMAGE_NAME):$(VERSION)

docker-scan:
	@echo
	@echo "Scanning docker image $(IMAGE_NAME) for vulnerabilities with Trivy"
	@echo
	docker run --rm \
		-v /var/run/docker.sock:/var/run/docker.sock \
    	-v "$(HOME)/trivy/.cache:/root/.cache/" \
		-v "$(PWD)/.trivyignore:/.trivyignore" \
	aquasec/trivy:latest \
		image \
			--timeout 10m \
			--exit-code 1\
			--severity CRITICAL \
			--ignore-unfixed --timeout 20m \
			--ignorefile /.trivyignore \
		"$(IMAGE_NAME):$(VERSION)"

print-env:
	env | sort
