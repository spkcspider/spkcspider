FROM python:3
ENV PYTHONUNBUFFERED 1
WORKDIR /app
ADD . /app
RUN curl -sL https://deb.nodesource.com/setup_10.x | bash -
RUN apt-get update && apt-get install nodejs npm curl -y
RUN pip install --upgrade pip
RUN pip install .
RUN ./tools/install_deps.sh
