FROM python:3.9

ENV PYTHONUNBUFFERED=1
# Poetry will be installed here
ENV PATH="/root/.local/bin:${PATH}"

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -

WORKDIR /code
COPY poetry.lock pyproject.toml ./
RUN poetry install

COPY . .

RUN poetry run python manage.py migrate

EXPOSE 8000
