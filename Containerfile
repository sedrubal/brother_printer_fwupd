FROM python:latest

RUN    pip install --upgrade pipx \
    && pipx install brother-printer-fwupd[autodiscover]

CMD brother-printer-fwupd

ENV PATH="/root/.local/bin/:${PATH}"

MAINTAINER sedrubal
