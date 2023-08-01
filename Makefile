POETRY_VIRTUALENVS_IN_PROJECT = true
GIT_AUTO_MERGE_REPO ?= git@github.com:clintmod/git_auto_merge_test.git
IMAGE_NAME ?= clintmod/git-auto-merge
export

.DEFAULT_GOAL := all

.PHONY: test-update

BIN = .venv/bin/git-auto-merge
VERSION = $(shell yq .tool.poetry.version pyproject.toml)
SRC = Makefile .venv pyproject.toml .git-auto-merge.json \
	  $(shell find src tests -name '*.py') \
	  $(shell find tests -name '*.txt')

$(BIN): pyproject.toml Makefile .venv
	poetry install

all: reports format build test lint run

reports:
	mkdir -p reports

reports/format.ansi: $(SRC)
	poetry run black . && poetry run isort . | tee -i reports/format.ansi

format: reports/format.ansi

build: $(BIN)

reports/test.ansi: $(SRC)
	unbuffer poetry run pytest -vvv \
		--ignore repos \
		--ignore .venv \
		--cov=src \
		--cov-report term-missing:skip-covered \
		$(EXTRA_TEST_ARGS) \
	tests \
	| tee -i reports/test.ansi

test: reports/test.ansi
	
test-update:
	EXTRA_TEST_ARGS="--snapshot-update" make test

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
	$(IMAGE_NAME) \
	bash

docker-run:
	docker run \
		-it --rm \
		-e GIT_AUTO_MERGE_REPO=$(GIT_AUTO_MERGE_REPO) \
		-e DEBUG=1 \
		-v $(HOME)/.ssh:/home/app/.ssh \
	$(IMAGE_NAME)

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
