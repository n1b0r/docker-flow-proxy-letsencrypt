#!/bin/sh

# crond configuration
echo "${LETSENCRYPT_RENEWAL_CRON} curl http://${DF_SWARM_LISTENER_SERVICE_NAME}:8080/v1/docker-flow-swarm-listener/notify-services" >> /etc/crontabs/root

crond -L /var/log/crond.log && tail -f /var/log/crond.log &

exec "$@"