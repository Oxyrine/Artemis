#!/bin/sh
# migrate, create the signing key if missing, load the environment if the database is empty, then serve.
# One worker on purpose: batch and run state live in the process.
set -e
python -m scripts.seed
exec uvicorn artemis.api.main:app --host 0.0.0.0 --port 8000
