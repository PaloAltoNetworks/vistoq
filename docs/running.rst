Running The Demo
----------------


1. Copy the local.env.example to local.env

    .. code-block::

    cp local.env.example local.env


2. Edit the local.env file to reflect your local environment

    .. code-block::

    vi local.env


3. source the local env file

    .. code-block::

    . local.env


4. Build the local db to prepare the application

    .. code-block::

    ./manage.py migrate


5. Create an Admin Username and Password

    .. code-block::

    manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_superuser('vistoq', 'admin@example.com', 'BIGSECRET')"


6. launch the application with the manage.py command

    .. code-block::

    ./manage.py runserver 8888


5. Launch a web browser and browse to http://localhost:8888
