# Using secrets

## proxy stack

`docker-flow-proxy-letsencrypt` can store certificates into docker secrets.

Each time `docker-flow-proxy` will regenerated its config, it will scan for attached secrets and reload its config.

Create the `proxy` network.

```
docker network create -d overlay proxy
```

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
      - SERVICE_NAME=proxy_proxy
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
    environment:
      - DF_PROXY_SERVICE_NAME=proxy_proxy
      # - LOG=debug
      # - CERTBOT_OPTIONS=--staging
    volumes:
      # link docker socket to activate secrets support.
      - /var/run/docker.sock:/var/run/docker.sock
      # create a dedicated volume for letsencrypt folder.
      # MANDATORY to keep persistent certificates on DFPLE.
      # Without this volume, certificates will be regenerated every time DFPLE is recreated.
      # OPTIONALY you will be able to link this volume to another service that also needs certificates (gitlab/gitlab-ce for example)
      - le-certs:/etc/letsencrypt
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

```

## service stack

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
