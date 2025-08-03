#!/bin/bash
set -e
poetry install
poetry run pytest
