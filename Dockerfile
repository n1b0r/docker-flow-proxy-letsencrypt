FROM certbot/certbot

ENV DOCKER_SOCKET_PATH="/var/run/docker.sock" \
	LETSENCRYPT_RENEWAL_CRON="30 2 * * *" \
	DF_PROXY_SERVICE_NAME="proxy" \
	DF_SWARM_LISTENER_SERVICE_NAME="swarm-listener"

RUN apk add --update curl

RUN mkdir -p /opt/www
RUN mkdir -p /etc/letsencrypt
RUN mkdir -p /var/lib/letsencrypt
RUN touch /var/log/crond.log

COPY ./requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

COPY ./entrypoint.sh /

EXPOSE 8080

COPY ./app /app

ENTRYPOINT ["sh", "/entrypoint.sh"]
CMD ["python", "/app/app.py"]