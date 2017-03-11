FROM python:alpine

RUN apk add --update certbot curl

ENV DF_NOTIFY_CREATE_SERVICE_URL="http://proxy:8080/v1/docker-flow-proxy/reconfigure" \
	DF_PROXY_SERVICE_BASE_URL="http://proxy:8080/v1/docker-flow-proxy" \
	DOCKER_SOCKET_PATH="/var/run/docker.sock"

ADD ./app/requirements.txt /app/requirements.txt

RUN pip install -r /app/requirements.txt

RUN mkdir -p /opt/www
RUN mkdir -p /etc/letsencrypt
RUN mkdir -p /var/lib/letsencrypt

EXPOSE 8080

ADD ./app /app

CMD ["python", "/app/app.py"]