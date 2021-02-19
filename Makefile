REPO_LIST ?= backend,mobile,web,common

GITHUB_ORG ?= clintmod

export

setup:
	python -m venv venv && \
	source venv/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements.txt

test:
	source venv/bin/activate && \
	pytest -vvv \
	--ignore repos \
	--ignore venv \
	--cov=. \
	--cov-report term-missing:skip-covered

run:
	./gitflow_merge.py -v

debug:
	./gitflow_merge.py -v

lint:
	source venv/bin/activate && \
	pylint -j4 -f --rcfile=./pylintrc colorized *.py

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
