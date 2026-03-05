#!/bin/bash -eu

ruff format scripts/*.py
ruff check --select I --fix scripts/*.py
ruff check --fix scripts/*.py
