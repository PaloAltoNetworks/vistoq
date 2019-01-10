
FROM python:alpine

LABEL description="Vistoq Demo Portal"
LABEL version="0.2"
LABEL maintainer="nembery@paloaltonetworks.com"

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
RUN if [ -f /app/cnc/db.sqlite3 ]; then rm /app/cnc/db.sqlite3; fi
RUN python /app/cnc/manage.py migrate
RUN python /app/cnc/manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_superuser('vistoq', 'admin@example.com', 'Vistoq123')"

EXPOSE 80
CMD ["python", "/app/cnc/manage.py", "runserver", "0.0.0.0:80"]
#CMD sh