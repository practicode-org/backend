FROM python:3.9

ENV PYTHONUNBUFFERED=1
# Poetry will be installed here
ENV PATH="/root/.local/bin:${PATH}"
WORKDIR /code
EXPOSE 8000

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -

COPY poetry.lock pyproject.toml /code/
RUN poetry install
COPY . /code/

#CMD poetry run python3 manage.py runserver 0.0.0.0:8000


