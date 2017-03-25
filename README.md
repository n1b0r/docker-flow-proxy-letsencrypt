# docker-flow-proxy letsencrypt 

`docker-flow-proxy-letsencrypt` is a `docker-flow-proxy` companion that automatically create ~~and renew certificates~~ for your swarm services.

> The automatic renew certificates feature is currently a work in progress. As a workaround, you can force a **notify-services** request to `docker-flow-swarm-listener` (eg: `curl http://swarm-listener-service-name:8080/v1/docker-flow-swarm-listener/notify-services`)

You need to set deployment labels to enable let's encrypt support for each proxied services:
  * com.df.letsencrypt.host
  * com.df.letsencrypt.email

**com.df.letsencrypt.host** generally match the **com.df.serviceDomain** label.

## Usage.

Create the `proxy` network.

```
docker network create -d overlay proxy
```

Then you can choose how you want to use `docker-flow-proxy-letsencrypt`:
  * using volumes
  * using secrets

### Using volumes


### Using secrets

```
version: "3"
services:

  proxy:
    image: vfarcic/docker-flow-proxy
    ports:
      - 80:80
      - 443:443
    networks:
      - proxy
    environment:
      - LISTENER_ADDRESS=swarm-listener
      - MODE=swarm
    deploy:
      replicas: 1

  swarm-listener:
    image: vfarcic/docker-flow-swarm-listener
    networks:
      - proxy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DF_NOTIFY_CREATE_SERVICE_URL=http://proxy-le:8080/v1/docker-flow-proxy-letsencrypt/reconfigure
      - DF_NOTIFY_REMOVE_SERVICE_URL=http://proxy_proxy:8080/v1/docker-flow-proxy/remove
    deploy:
      placement:
        constraints: [node.role == manager]

  proxy-le:
    image: nib0r/docker-flow-proxy-letsencrypt
    networks:
      - proxy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DF_PROXY_SERVICE_NAME=proxy_proxy
      # - LOG=debug
      # - CERTBOT_OPTIONS=--staging
    deploy:
      replicas: 1
      labels:
        - com.df.notify=true
        - com.df.distribute=true
        - com.df.servicePath=/.well-known/acme-challenge
        - com.df.port=8080
networks:
  proxy:
    external: true
volumes:
  le-certs:
    external: true
  dfp-certs:
    external: true

```

### Environment variables

  * `DF_PROXY_SERVICE_NAME`: `docker-flow-proxy` service name (either SERVICE-NAME or STACK-NAME_SERVICE-NAME).
  * `CERTBOT_OPTIONS`: custom options added to certbot command line (example: --staging).
  * `LOG`: logging level (debug, info, warning, error), defaults to info.


### service stack

```
version: "3"
services:
  whoami:
    image: jwilder/whoami
    networks:
      - proxy
    deploy:
      replicas: 1
      labels:
        - com.df.notify=true
        - com.df.distribute=true
        - com.df.serviceDomain=domain.com
        - com.df.servicePath=/
        - com.df.srcPort=443
        - com.df.port=8000
        - com.df.letsencrypt.host=domain.com
        - com.df.letsencrypt.email=email@domain.com
networks:
  proxy:
    external: true
```
