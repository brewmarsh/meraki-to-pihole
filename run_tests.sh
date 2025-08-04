#!/bin/bash
set -e
export TESTING=true
poetry install
poetry run pytest
