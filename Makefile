GIT_REPO ?= git@github.com:clintmod/gitflow_merge_test

export

setup:
	poetry install

test:
	poetry run pytest -vvv \
		--ignore repos \
		--ignore .venv \
		--cov=src \
		--cov-report term-missing:skip-covered \
		$(EXTRA_TEST_ARGS) \
	tests

test-update:
	EXTRA_TEST_ARGS="--snapshot-update" make test


dry-run:
	poetry run src/gitflow_merge.py --dry-run

run:
	poetry run src/gitflow_merge.py -v

lint:
	poetry run pylint -j4 -f colorized src

format:
	poetry run black . && poetry run isort .

clean-reports:
	rm -rf reports/*

test-jenkinsfile: clean-reports
	docker run --rm -v $(PWD):/home/groovy/app groovy:3.0.6 \
		bash -c "cd /home/groovy/app && \
		groovy -cp scripts/jenkinsfile scripts/jenkinsfile/Tests.groovy"

test-jenkinsfile-local: clean-reports
	groovy -cp scripts/jenkinsfile scripts/jenkinsfile/Tests.groovy
