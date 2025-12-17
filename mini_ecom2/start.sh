#!/bin/bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py createsuper_user
exec gunicorn mini_ecom.wsgi:application --bind 0.0.0.0:$PORT