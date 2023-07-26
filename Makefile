POETRY_VIRTUALENVS_IN_PROJECT = true
GIT_AUTO_MERGE_REPO ?= git@github.com:clintmod/git_auto_merge_test.git

export

.DEFAULT_GOAL := all

.PHONY: test-update

BIN = .venv/bin/git-auto-merge
VERSION = 1.0.1
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

docker-build:
	docker build \
		--build-arg PYTHON_VERSION=$(shell cat .python-version) \
		-t clintmod/git-auto-merge:$(VERSION) \
	.

docker-build-builder:
	docker build \
		--target=builder \
		--build-arg PYTHON_VERSION=$(shell cat .python-version) \
		-t clintmod/git-auto-merge:builder \
	.

docker-push:
	docker push clintmod/git-auto-merge:$(VERSION)
	docker tag clintmod/git-auto-merge:$(VERSION) clintmod/git-auto-merge:latest
	docker push clintmod/git-auto-merge:latest

docker-shell:
	docker run \
		-it --rm --entrypoint= \
		-e GIT_AUTO_MERGE_REPO=git@github.com:clintmod/git_auto_merge_test \
		-e DEBUG=1 \
		-v $(HOME)/.ssh:/home/app/.ssh \
	clintmod/git-auto-merge \
	bash

docker-run:
	docker run \
		-it --rm \
		-e GIT_AUTO_MERGE_REPO=git@github.com:clintmod/git_auto_merge_test \
		-e DEBUG=1 \
		-v $(HOME)/.ssh:/home/app/.ssh \
	clintmod/git-auto-merge

test-jenkinsfile:
	docker run --rm -v $(PWD):/home/groovy/app groovy:3.0.6 \
		bash -c "cd /home/groovy/app && \
		groovy -cp scripts/jenkinsfile scripts/jenkinsfile/Tests.groovy"

test-jenkinsfile-local:
	groovy -cp scripts/jenkinsfile scripts/jenkinsfile/Tests.groovy
