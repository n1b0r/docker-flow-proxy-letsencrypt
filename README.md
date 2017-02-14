# docker-flow-proxy letsencrypt 

`docker-flow-proxy-letsencrypt` is a `docker-flow-proxy` companion that automatically create and renew certificates for your services.

You need to set deployment labels to enable let's encrypt support for each proxied services:
  * com.df.letsencrypt.host
  * com.df.letsencrypt.email

**com.df.letsencrypt.host** generally match the **com.df.serviceDomain** label.

## Usage.

Create the `proxy` network.

```
docker network create -d overlay proxy
```

### proxy stack

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
    image: robin/docker-flow-proxy-letsencrypt
    networks:
      - proxy
    environment:
      - DF_PROXY_SERVICE_NAME=proxy
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

```

Environment variables :
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
        - com.df.serviceDomain=git.nibor.me
        - com.df.servicePath=/
        - com.df.srcPort=443
        - com.df.port=8000
        - com.df.letsencrypt.host=git.nibor.me
        - com.df.letsencrypt.email=robinlucbernet@gmail.com
networks:
  proxy:
    external: true
```

## The actual design

The current design is pretty easy, `docker-flow-swarm-listener` sends all **RECONFIGURE** requests (as defined in the **CREATE** env var) to `docker-flow-proxy-letsencrypt`.

`docker-flow-proxy-letsencrypt` check if the created service use special labels (**com.df.letsencrypt.host**, **com.df.letsencrypt.email**):
  * if yes, we go throught certbot process and if a new certificate is generated, we send it to `docker-flow-proxy` via **PUT /certs**.
  * in both case (if special labels found or not), we forward the original request to `docker-flow-proxy`

`docker-flow-proxy` get the **RECONFIGURE** request and handle the job.


	swarm-listner >> proxy-le >> proxy


## Improved design

We should provide a new env var for `docker-flow-swarm-listener` to be able to send a request to `docker-flow-proxy-letsencrypt`. Let say, `DF_NOTIFY_LETSENCRYPT_SERVICE_URL`.

`docker-flow-swarm-listener` could detected new services with letsencrypt support based on labels `com.df.letsencrypt.host`, `com.df.letsencrypt.email`. And then send a request to `docker-flow-swarm-listener` or `docker-flow-proxy`.

`docker-flow-proxy-letsencrypt` should trigger only one request to perform reconfigure and certificate update (PUT request with certifcate as data ?)

## Things to do

  * renewal process based on cron (we night need that `docker-flow-swarm-listener` gives us the list of services).