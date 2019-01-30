
FROM python:alpine

LABEL description="Vistoq Demo Portal"
LABEL version="0.5.8"
LABEL maintainer="sp-solutions@paloaltonetworks.com"


WORKDIR /app
ADD app/requirements.txt /app/requirements.txt
ADD app/cnc/requirements.txt /app/cnc/requirements.txt
RUN apk add --update --no-cache  git gcc musl-dev python3-dev libffi-dev openssl-dev docker
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install -r cnc/requirements.txt
COPY app/src /app/src
COPY app/cnc /app/cnc
#COPY tests /app/tests

ENV TERRAFORM_VERSION=0.11.11
ENV TERRAFORM_SHA256SUM=94504f4a67bad612b5c8e3a4b7ce6ca2772b3c1559630dfd71e9c519e3d6149c

RUN echo "===> Installing Terraform..."  && \
    apk add --update git curl openssh && \
    curl https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip > terraform_${TERRAFORM_VERSION}_linux_amd64.zip && \
    echo "${TERRAFORM_SHA256SUM}  terraform_${TERRAFORM_VERSION}_linux_amd64.zip" > terraform_${TERRAFORM_VERSION}_SHA256SUMS && \
    sha256sum -cs terraform_${TERRAFORM_VERSION}_SHA256SUMS && \
    unzip terraform_${TERRAFORM_VERSION}_linux_amd64.zip -d /bin && \
    rm -f terraform_${TERRAFORM_VERSION}_linux_amd64.zip  && \
    rm -f terraform_${TERRAFORM_VERSION}_SHA256SUMS

RUN if [ -f /app/cnc/db.sqlite3 ]; then rm /app/cnc/db.sqlite3; fi
RUN python /app/cnc/manage.py migrate
RUN python /app/cnc/manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_superuser('vistoq', 'admin@example.com', 'Vistoq123')"

EXPOSE 80
#CMD ["python", "/app/cnc/manage.py", "runserver", "0.0.0.0:80"]
ENTRYPOINT ["/app/cnc/start_app.sh"]

