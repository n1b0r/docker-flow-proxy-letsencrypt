FROM certbot/certbot

ENV DF_NOTIFY_CREATE_SERVICE_URL="http://proxy:8080/v1/docker-flow-proxy/reconfigure" \
	DF_PROXY_SERVICE_BASE_URL="http://proxy:8080/v1/docker-flow-proxy" \
	DOCKER_SOCKET_PATH="/var/run/docker.sock"

RUN apk add --update curl

RUN mkdir -p /opt/www
RUN mkdir -p /etc/letsencrypt
RUN mkdir -p /var/lib/letsencrypt

ADD ./requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

EXPOSE 8080

ADD ./app /app

ENTRYPOINT [""]
CMD ["python", "/app/app.py"]