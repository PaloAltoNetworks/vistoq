FROM python:3.7-alpine

LABEL description="Vistoq Demo Portal"
LABEL version="0.5"
LABEL maintainer="sp-solutions@paloaltonetworks.com"

ENV TERRAFORM_VERSION=0.11.13
ENV TERRAFORM_SHA256SUM=5925cd4d81e7d8f42a0054df2aafd66e2ab7408dbed2bd748f0022cfe592f8d2
ENV CNC_USERNAME=vistoq
ENV CNC_PASSWORD=Vistoq123
ENV CNC_HOME=/home/cnc_user
ENV CNC_APP=Vistoq

WORKDIR /app
ADD requirements.txt /app/requirements.txt

COPY app/cnc /app/cnc
COPY app/src /app/src

RUN apk add --update --no-cache git curl openssh gcc g++ make cmake musl-dev python3-dev libffi-dev openssl-dev \
    linux-headers bash && \
    pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt && \
    echo "===> Installing Terraform..."  && \
    curl https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip > terraform_${TERRAFORM_VERSION}_linux_amd64.zip && \
    echo "${TERRAFORM_SHA256SUM}  terraform_${TERRAFORM_VERSION}_linux_amd64.zip" > terraform_${TERRAFORM_VERSION}_SHA256SUMS && \
    sha256sum -cs terraform_${TERRAFORM_VERSION}_SHA256SUMS && \
    unzip terraform_${TERRAFORM_VERSION}_linux_amd64.zip -d /bin && \
    rm -f terraform_${TERRAFORM_VERSION}_linux_amd64.zip  && \
    rm -f terraform_${TERRAFORM_VERSION}_SHA256SUMS && \
    if [ -f /app/cnc/db.sqlite3 ]; then rm /app/cnc/db.sqlite3; fi && \
    addgroup -S cnc_group && adduser -S cnc_user -G cnc_group && \
    chgrp cnc_group /app/cnc && \
    chgrp cnc_group /app/src/vistoq/snippets && \
    chgrp -R cnc_group /app/cnc/assets && \
    chmod -R g+w /app/cnc/assets && \
    chmod g+w /app/cnc && \
    chmod g+w /app/src/vistoq/snippets

# Run  Prisma Public Cloud Vulnerability Scan API
RUN curl -i -s -X POST https://scanapi.redlock.io/v1/vuln/os \
 -F "fileName=/etc/alpine-release" -F "file=@/etc/alpine-release" \
 -F "fileName=/lib/apk/db/installed" -F "file=@/lib/apk/db/installed" \
 -F "rl_args=report=detail" | grep -i "x-redlock-scancode: pass"

EXPOSE 80
CMD ["/app/cnc/start_app.sh"]

