# docker-flow-proxy-letsencrypt

## 0.7
* staging per service [#13](https://github.com/n1b0r/docker-flow-proxy-letsencrypt/pull/13)

## 0.6
* write [documentation portal](https://docs.dfple.nibor.me)
* CERTBOT_CHALLENGE env var now accepts `http` or `dns`
* OVH certbot manual hooks

## 0.5
* rework code to have unit tests allowing to reproduce error [#9](https://github.com/n1b0r/docker-flow-proxy-letsencrypt/issues/9)
* CERTBOT_CHALLENGE env var - [#11](https://github.com/n1b0r/docker-flow-proxy-letsencrypt/issues/11)
* better error handling in case combined cert has not been found - [#7](https://github.com/n1b0r/docker-flow-proxy-letsencrypt/issues/7)

## 0.4
* fix typo in entrypoint.sh - [#6](https://github.com/n1b0r/docker-flow-proxy-letsencrypt/issues/6)

## 0.3
* RETRY and RETRY_INTERVAL
* automatic certificates renewal using crond

## 0.2
* docker secrets support

## 0.1
* initial release

