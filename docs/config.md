# configuration

## Environment variables

| Name                           |      Description                                                                       | Default   |
|--------------------------------|:--------------------------------------------------------------------------------------:|----------:|
| CERTBOT_OPTIONS                | Custom options added to certbot command line (example: --staging)                      |           |
| CERTBOT_CHALLENGE              | Use a custom certbot challenge. Only webroot is currently implemented, use CERTBOT_OPTIONS to pass extra options (see [#11](https://github.com/n1b0r/docker-flow-proxy-letsencrypt/issues/11))  | webroot   |
| DF_PROXY_SERVICE_NAME          | Name of the docker-flow-proxy service (either SERVICE-NAME or STACK-NAME_SERVICE-NAME).| proxy     |
| DF_SWARM_LISTENER_SERVICE_NAME | Name of the docker-flow-proxy service. Used to force cert renewal.                     | swarm-listener |
| DOCKER_SOCKET_PATH             | Path to the docker socket. Required for docker secrets support.                        | /var/run/docker.sock      |
| LETSENCRYPT_RENEWAL_CRON       | Define cron timing for cert renewal                                                    | 30 2 * * * |
| LOG                            | Logging level (debug, info, warning, error)                                            | info      |
| RETRY                          | Number of forward request retries                                                      | 10        |
| RETRY_INTERVAL                 | Interval (seconds) between forward request retries                                     | 5         |
