#!/bin/bash

set -euxo pipefail

VERSION=0.8.0
IMG_NAME=docker.io/therealsedrubal/brother-printer-fwupd

uv build

set +u
if [ "$1" == "--publish" ]; then
    set -u
    uv publish
fi

podman pull python:latest
podman build -t "${IMG_NAME}:latest" .
podman tag "${IMG_NAME}:latest" "${IMG_NAME}:${VERSION}"

set +u
if [ "$1" == "--publish" ]; then
    set -u
    podman push "${IMG_NAME}:latest" "${IMG_NAME}:${VERSION}"
fi
