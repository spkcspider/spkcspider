#! /bin/sh

# installs and updates all dependencies to current level

yarn install --pure-lockfile
poetry install
poetry run ./manage.py migrate
poetry run ./manage.py collectstatic --no-input
