#! /bin/sh

# installs and updates all dependencies to current level

npm install
poetry install
poetry shell
./manage.py migrate
./manage.py collectstatic --no-input
