FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir semgrep pytest ruff

RUN curl -fsSL -o /tmp/gitleaks.tar.gz \
        https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz \
    && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
    && curl -fsSL -o /tmp/trivy.tar.gz \
        https://github.com/aquasecurity/trivy/releases/download/v0.76.2/trivy_0.76.2_Linux-64bit.tar.gz \
    && tar -xzf /tmp/trivy.tar.gz -C /usr/local/bin trivy \
    && curl -fsSL -o /usr/local/bin/osv-scanner \
        https://github.com/google/osv-scanner/releases/download/v2.7.1/osv-scanner_linux_amd64 \
    && chmod 755 /usr/local/bin/gitleaks /usr/local/bin/trivy /usr/local/bin/osv-scanner \
    && rm -rf /tmp/gitleaks.tar.gz /tmp/trivy.tar.gz

COPY egress_proxy.py semgrep.yml /opt/factory/
COPY entrypoint.sh /opt/factory/entrypoint.sh
RUN chmod 755 /opt/factory/entrypoint.sh \
    && useradd --uid 1000 --create-home --shell /bin/bash factory \
    && mkdir -p /work \
    && chown -R factory:factory /work /opt/factory

USER factory
WORKDIR /work
ENV HOME=/home/factory \
    HTTP_PROXY=http://127.0.0.1:3128 \
    HTTPS_PROXY=http://127.0.0.1:3128 \
    http_proxy=http://127.0.0.1:3128 \
    https_proxy=http://127.0.0.1:3128 \
    NO_PROXY=localhost,127.0.0.1 \
    no_proxy=localhost,127.0.0.1

ENTRYPOINT ["/opt/factory/entrypoint.sh"]
