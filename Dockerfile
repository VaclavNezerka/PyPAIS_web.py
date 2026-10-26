# AIBAL web app with GPU inference - built for the e-INFRA CZ (CERIT-SC) Kubernetes platform,
# see deploy/README.md. Runs as a non-root numeric user on port 8080, as the platform requires.
FROM python:3.11-slim-bookworm

# PyTorch CUDA build: 12.6 works with the widest range of NVIDIA drivers on the cluster's GPU nodes
ARG TORCH_VERSION=2.14.1
ARG TORCHVISION_VERSION=0.29.1
ARG TORCH_CUDA=cu126

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # the root filesystem is not writable for the app user - caches go to /tmp (an emptyDir in Kubernetes)
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    XDG_CACHE_HOME=/tmp/.cache \
    NO_ALBUMENTATIONS_UPDATE=1

# DejaVu fonts for the PDF report (reportlab looks them up by file name in a few fixed folders)
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core libglib2.0-0 \
    && ln -s /usr/share/fonts/truetype/dejavu/DejaVuSans*.ttf /usr/share/fonts/truetype/ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install torch==${TORCH_VERSION} torchvision==${TORCHVISION_VERSION} \
        --index-url https://download.pytorch.org/whl/${TORCH_CUDA}
COPY deploy/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY . /app
# translations are compiled in the repo; this only makes sure the .mo files match the .po files
RUN pybabel compile -d translations -f

USER 1000
EXPOSE 8080
# workers: WEB_CONCURRENCY; timeout and CPU threads per worker: gunicorn.conf.py
CMD ["gunicorn", "app:app", "--config", "gunicorn.conf.py", "--bind", "0.0.0.0:8080"]
