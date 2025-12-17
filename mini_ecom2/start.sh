#!/bin/bash
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn mini_ecom.wsgi --bind 0.0.0.0:$PORT
