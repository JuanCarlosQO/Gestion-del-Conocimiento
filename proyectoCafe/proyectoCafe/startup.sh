#!/bin/bash
cd /home/site/wwwroot
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
gunicorn --bind=0.0.0.0:8000 --workers=2 proyectoCafe.wsgi
