FROM python:3.9-slim-buster

# Install system dependencies
RUN apt-get update && apt-get install -y python3-dev libmysqlclient-dev default-build-essential
RUN apt-get install -y pkg-config



WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD ["gunicorn", "--worker-class=gevent", "--worker-connections=1000", "--workers=3", "app:app"]
