
FROM python:alpine

LABEL description="Vistoq2 Demo Portal"
LABEL version="1.0"
LABEL maintainer="nembery@paloaltonetworks.com"

WORKDIR /app
ADD requirements.txt /app/requirements.txt
RUN apk add --no-cache git
RUN pip install -r requirements.txt
COPY app /app/vistoq
#COPY tests /app/tests
RUN python /app/vistoq/manage.py migrate
RUN python /app/vistoq/manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_superuser('vistoq', 'admin@example.com', 'Vistoq123!!!')"

EXPOSE 5000
CMD ["python", "/app/vistoq/manage.py", "runserver", "0.0.0.0:5000"]
#CMD sh