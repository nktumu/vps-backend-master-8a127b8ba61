# VERITAS: Copyright (c) 2022 Veritas Technologies LLC. All rights reserved.
#
# THIS SOFTWARE CONTAINS CONFIDENTIAL INFORMATION AND TRADE SECRETS OF VERITAS
# TECHNOLOGIES LLC.  USE, DISCLOSURE OR REPRODUCTION IS PROHIBITED WITHOUT THE
# PRIOR EXPRESS WRITTEN PERMISSION OF VERITAS TECHNOLOGIES LLC.
#
# The Licensed Software and Documentation are deemed to be commercial computer
# software as defined in FAR 12.212 and subject to restricted rights as defined
# in FAR Section 52.227-19 "Commercial Computer Software - Restricted Rights"
# and DFARS 227.7202, Rights in "Commercial Computer Software or Commercial
# Computer Software Documentation," as applicable, and any successor
# regulations, whether delivered by Veritas as on premises or hosted services.
# Any use, modification, reproduction release, performance, display or
# disclosure of the Licensed Software and Documentation by the U.S. Government
# shall be solely in accordance with the terms of this Agreement.
# Product version __version__

# Usage:
#
#   make
# or
#   make -f <this file>
#
# will run the default target
#
# There are two definable command line variables
#
# First
#
#   make TESTKEY=special_test
#
# will run all tests whose names contain the value of TESTKEY
# so that test_this_is_a_special_test() would be run but
# text_this_is_just_special() would not be run.
#
# Second
#
#    make TESTFILE=path-to-file
#
# will run tests in the specified file, also filtered by TESTKEY
# if that is set.
#
# The path-to-file must be the full path, and the directory separators
# must be a forward slash, for example
#
#    make TESTFILE=src/unitest/python/test_connection.py
#

all: clean checkformat checkstyle checkspec test coverage-report doc

.PHONY: all \
	checkformat \
	checkspec \
	checkstyle \
	clean \
	coverage-report \
	ensureclean-force \
	ensureclean \
	env-create \
	env-update \
	env \
	lock \
	generate-excel \
	generate-models \
	install \
	package \
	publish \
	start-server \
	stress \
	stressonly \
	test \
	testcore \
	testserver \
	testxl

ifdef OS
   OSTYPE = Windows
else
   OSTYPE = $(shell uname)
endif

DOCS := documentation-wip.docx \
	troubleshooting-wip.docx \
	quick_start-wip.docx \
	whats_new-wip.docx

PDF_DOCS := documentation.pdf \
            troubleshooting.pdf \
            quick_start.pdf \
            whats_new.pdf

clean:
	coverage erase

env-create:
	(conda list --name vupc && conda env update -f environment.yml) || conda env create -f environment.yml

env-update: env-create
	conda env update -f dev-environment.yml

env: env-update

lock:
	docker build -t vps-backend:lock --target=lock .
	docker run vps-backend:lock > Pipfile.lock

publish: export PYTHONDONTWRITEBYTECODE=1
publish:
	python -m use_devtools.report

publishall: export PYTHONDONTWRITEBYTECODE=1
publishall:
	python -m use_devtools.report --build-all-the-things

start-server: checkformat checkstyle
	python -m use_server

checkformat:
	black --check src
	python -m use_devtools.format_json --check json_data/

checkstyle:
	flake8 src

checkspec:
	# openapi-spec-validator --schema 3 json_data/openapi.yaml
	$(info skipping API validation due to https://stash.veritas.com/projects/VUPC/repos/vps-backend/pull-requests/803/overview?commentId=2242825)

PYTEST := coverage run --append -m pytest --hypothesis-show-statistics
ifeq ($(OSTYPE),Darwin)
PYTEST_DEFAULT_TAG := -m "not slowtest"
else
PYTEST_DEFAULT_TAG :=
endif

test: generate-excel
ifdef TESTKEY
	$(PYTEST) -k $(TESTKEY) $(TESTFILE)
else
	$(PYTEST) $(PYTEST_DEFAULT_TAG) $(TESTFILE)
endif

testcore:
	$(PYTEST) src/core

testxl: generate-excel
	$(PYTEST) src/xl

testserver:
	$(PYTEST) src/server

NOTEBOOKS := \
	notebooks/5240-5340.ipynb \
	notebooks/5250.ipynb \
	notebooks/5350-flex.ipynb \
	notebooks/5350.ipynb \
	notebooks/access_s3_throughput.ipynb \
	notebooks/bekb.ipynb \
	notebooks/cc_validation.ipynb \
	notebooks/cpu_model_validation.ipynb \
	notebooks/master_server_memory.ipynb \
	notebooks/memory_model_validation.ipynb

NBVAL := $(PYTEST) --sanitize-with pytest_sanitize.cfg --nbval

testnotebook: download-benchmarks
	$(NBVAL) $(NOTEBOOKS)

testslownotebook: download-benchmarks
	$(NBVAL)  notebooks/master_server_parsing.ipynb

stress: export RUN_STRESS=1
stress: test

stressonly: export RUN_STRESS=1
stressonly: generate-excel
	$(PYTEST) -k test_stress

generate-models:
	python build-models.py

download-benchmarks:
	python tools/download-benchmark-data.py

# ensure that just running build-package doesn't create .pyc files
# that will itself cause ensureclean to always fail
ensureclean: export PYTHONDONTWRITEBYTECODE=1
ensureclean:
	python build-package.py ensureclean

ensureclean-force: export PYTHONDONTWRITEBYTECODE=1
ensureclean-force:
	python build-package.py ensureclean-force

package: all generate-models
	python build-package.py package

PKGS = src/xlwriter src/server src/devtools
ifneq ($(OSTYPE),Linux)
PKGS += src/xl
endif
install:
	pip install -e src/core
	pip install $(patsubst %,-e %,$(PKGS))

PROFILES := standard teradata

generate-excel: $(foreach profile,$(PROFILES),generate-excel-$(profile))

# Workbook filenames are generated from profile. Standard workbook
# filename is a special case, though.
generate-excel-%: profile_name=$(subst generate-excel-,,$@)
generate-excel-%: output_file=USE-1.0-$(profile_name).xlsm
generate-excel-standard: output_file=USE-1.0.xlsm

generate-excel-%:
	coverage run --append -m use_xlwriter --profile $(profile_name) $(output_file)

coverage-report:
	coverage report

doc: $(PDF_DOCS)

DOC_PROD_SOURCES := $(wildcard doc/product-documentation/*.md)
documentation-wip.docx: $(DOC_PROD_SOURCES) doc/styles-reference.docx Makefile
	pandoc $(DOC_PROD_SOURCES) \
		--from=markdown+grid_tables \
		--filter=pandoc-docx-pagebreakpy \
		--reference-doc=doc/styles-reference.docx \
		-o $@

DOC_TS_SOURCES := $(wildcard doc/troubleshooting/*.md)
troubleshooting-wip.docx: $(DOC_TS_SOURCES) doc/styles-reference.docx Makefile
	pandoc $(DOC_TS_SOURCES) \
		--filter=pandoc-docx-pagebreakpy \
		--reference-doc=doc/styles-reference.docx \
		-o $@

DOC_QS_SOURCES := $(wildcard doc/quick-start/*.md)
quick_start-wip.docx: $(DOC_QS_SOURCES) doc/styles-reference.docx Makefile
	pandoc $(DOC_QS_SOURCES) \
		--filter=pandoc-docx-pagebreakpy \
		--reference-doc=doc/styles-reference.docx \
		-o $@

DOC_WN_SOURCES := $(wildcard doc/whats-new/*.md)
whats_new-wip.docx: $(DOC_WN_SOURCES) doc/styles-reference.docx Makefile
	pandoc $(DOC_WN_SOURCES) \
		--filter=pandoc-docx-pagebreakpy \
		--reference-doc=doc/styles-reference.docx \
		-o $@

%.pdf: %-wip.docx
ifeq ($(OSTYPE),Linux)
	pandoc $? -o $@
else
	docx2pdf "$(abspath $?)" "$(abspath $@)"
endif

ifneq ($(OSTYPE),Linux)
screenshot: generate-excel
	python -m use_devtools.screenshotting
endif

start-celery:
	nohup python -m use_server > server.log &
	celery -A use_server.celery_app worker -l info --logfile=celery.log
