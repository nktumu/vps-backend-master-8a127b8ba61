ARG BASE_IMAGE=python:3.9.11-slim-bullseye
ARG LOCKFILE_IMAGE=busybox:1.35.0-uclibc
ARG WORKSPACE_BASE=/data/jenkins/workspace
ARG WORKSPACE=${WORKSPACE_BASE}
FROM ${BASE_IMAGE} AS base
LABEL org.opencontainers.image.authors="DL-VTAS-VUPC-SERVICE@veritas.com"
EXPOSE 7186

ARG WORKSPACE_BASE
USER root
RUN pip install --target=/opt/extra-packages setuptools
RUN groupadd --gid 999 vupc-user && \
    useradd --system --create-home --home $WORKSPACE_BASE --uid 999 --gid vupc-user vupc-user
USER vupc-user
WORKDIR $WORKSPACE_BASE
ENV PATH=$PATH:$WORKSPACE_BASE/.local/bin
ENV PYTHONPATH=/opt/extra-packages
RUN echo $PATH

FROM base as pipenv
RUN pip config set global.disable-pip-version-check true \
    && pip config set global.no-cache-dir false
RUN pip install --user pipenv==2022.9.21 setuptools

FROM pipenv as dep_files
# Installing dependencies is the slowest step, so do this before copying the lastest source
COPY --chown=vupc-user:vupc-user Pipfile Pipfile.lock ./
COPY --chown=vupc-user:vupc-user src/core/setup.py ./src/core/
COPY --chown=vupc-user:vupc-user src/server/setup.py ./src/server/
COPY --chown=vupc-user:vupc-user src/devtools/setup.py ./src/devtools/
ENTRYPOINT ["pipenv", "run"]

FROM dep_files AS lockfile
ARG LOCKFILE_IMAGE
ARG WORKSPACE_BASE
COPY --from=dep_files $WORKSPACE_BASE/Pipfile.lock ./
RUN pipenv lock --clear --pre

FROM ${LOCKFILE_IMAGE} AS lock
ARG WORKSPACE_BASE
COPY --from=lockfile $WORKSPACE_BASE/Pipfile.lock ./
CMD ["cat", "Pipfile.lock"]

FROM dep_files AS install
RUN pipenv install --deploy
RUN pipenv run pip install setuptools

FROM install AS test
RUN pipenv install --dev
RUN pipenv run pip install setuptools
ARG WORKSPACE
WORKDIR $WORKSPACE
COPY --chown=vupc-user:vupc-user . .
CMD ["pytest", "src/core", "src/server"]

FROM install AS deploy
COPY --chown=vupc-user:vupc-user . .
CMD ["python", "-m", "use_server"]