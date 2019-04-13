#! /bin/sh

# installs and updates all dependencies to current level

npm install --no-save
poetry install
poetry run ./manage.py migrate
poetry run ./manage.py collectstatic --no-input
