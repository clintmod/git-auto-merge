REPO_LIST ?= backend,mobile,web,common

GITHUB_ORG ?= clintmod

export

setup:
	poetry install

test:
	poetry run pytest -vvv \
		--ignore repos \
		--ignore venv \
		--cov=src/gitflow_merge \
		--cov-report term-missing:skip-covered \
	.

run:
	src/gitflow_merge/gitflow_merge.py -v

lint:
	poetry run pylint -j4 -f colorized src

format:
	source venv/bin/activate && \
	black *.py && isort *.py

clean-reports:
	rm -rf reports/*

test-jenkinsfile: clean-reports
	docker run --rm -v $(PWD):/home/groovy/app groovy:3.0.6 \
		bash -c "cd /home/groovy/app && \
		groovy -cp scripts/jenkinsfile scripts/jenkinsfile/Tests.groovy"

test-jenkinsfile-local: clean-reports
	groovy -cp scripts/jenkinsfile scripts/jenkinsfile/Tests.groovy
