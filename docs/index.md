# Docker Flow Proxy Letsencrypt

[![Build Status](https://travis-ci.org/n1b0r/docker-flow-proxy-letsencrypt.svg?branch=master)](https://travis-ci.org/n1b0r/docker-flow-proxy-letsencrypt)

`docker-flow-proxy-letsencrypt` is a `docker-flow-proxy` companion that automatically create and renew certificates for your swarm services using [letsencrypt](https://letsencrypt.org/).

Join the #df-letsencrypt Slack channel in [DevOps20](http://slack.devops20toolkit.com/) and ping me (@nibor) if you have any questions, suggestions, or problems.

## Concept

The mecanism is mostly inspired by the [JrCs/docker-letsencrypt-nginx-proxy-companion](https://github.com/JrCs/docker-letsencrypt-nginx-proxy-companion) designed for [jwilder/nginx-proxy](https://github.com/jwilder/nginx-proxy).


Normally (without using DFPLE) when a new service is created in the swarm, the `docker-flow-swarm-listener` (DFSL) will send a **notify** request to the `docker-flow-proxy` (DFP) wich reload based on new config.

```
DFSL  -----notify----->  DFP
```

`docker-flow-proxy-letsencrypt` (DFPLE) acts as a man-in-the-middle service which gets **notify** requests from DFSL, process its work, and then forward original request to DFP.

```
DFSL  -----notify----->  DFPLE  -----notify----->  DFP
```

Its work consists in :

  * check if letsencrypt support is enabled by the service (check service labels)
  * generate or renew certificates using certbot utility (if support enabled)
  * distribute certificates to DFP (if support enabled)
  * forward request to dfp


## Get started

Check the [tutorial](tutorial-volumes.md) to get started with `docker-flow-proxy-letsencrypt` environment.

Please note that in order to keep persistent certificates :

  * on DFPLE side : you will need to use a volume on `/etc/letsencrypt`,
  * on DFP side : you will have to either use a volume (see example [using volumes](example-volumes.md)) or store certificates as secrets (see example [using secrets](example-secrets.md))

You can use both `dns` and `http` letsencrypt ACME challenges (see [configuration](config.md)).

Automatic renewal is performed at fixed interval. By default renewal process is performed once per day at 2.30 am. You can specify your own interval using `LETSENCRYPT_RENEWAL_CRON` env var on DFLE (see [configuration](config.md)).