# Configuration

## Labels

| Name                           |      Description                                                                       | Default   |
|--------------------------------|:--------------------------------------------------------------------------------------:|----------:|
| com.df.letsencrypt.host        | Comma separated list of domains letsencrypt will generate/update certs for.            |           |
| com.df.letsencrypt.email       | Email used by letsencrypt when registering cert.                                       |           |
| com.df.letsencrypt.testing     | Enable/disable staging per service. Please see [#13](https://github.com/n1b0r/docker-flow-proxy-letsencrypt/pull/13) |           |


## Environment variables

| Name                           |      Description                                                                       | Default   |
|--------------------------------|:--------------------------------------------------------------------------------------:|----------:|
| CERTBOT_OPTIONS                | Custom options added to certbot command line (example: --staging)                      |           |
| CERTBOT_CHALLENGE              | Specify the challenge to use. `http` or `dns`                                          | http      |
| CERTBOT_MANUAL_AUTH_HOOK       | Manual auth script to register DNS subdomains. **Required** with `dns` challenge       |           |
| CERTBOT_MANUAL_CLEANUP_HOOK    | Manual cleanup script to clean DNS subdomains. **Required** with `dns` challenge       |           |
| DF_PROXY_SERVICE_NAME          | Name of the docker-flow-proxy service (either SERVICE-NAME or STACK-NAME_SERVICE-NAME).| proxy     |
| DF_SWARM_LISTENER_SERVICE_NAME | Name of the docker-flow-proxy service. Used to force cert renewal.                     | swarm-listener |
| DOCKER_SOCKET_PATH             | Path to the docker socket. Required for docker secrets support.                        | /var/run/docker.sock      |
| LETSENCRYPT_RENEWAL_CRON       | Define cron timing for cert renewal                                                    | 30 2 * * * |
| LOG                            | Logging level (debug, info, warning, error)                                            | info      |
| OVH_DNS_ZONE                   | OVH DNS domain zone to use when using OVH API. **Required** when using OVH dns provider with `dns` challenge.                                         |           |
| OVH_APPLICATION_KEY            | OVH application key to use when using OVH API. **Required** when using OVH dns provider with `dns` challenge.                                         |           |
| OVH_APPLICATION_SECRET         | OVH application secret to use when using OVH API. **Required** when using OVH dns provider with `dns` challenge.                                      |           |
| OVH_CONSUMER_KEY               | OVH consumer key to use when using OVH API. **Required** when using OVH dns provider with `dns` challenge.                                      |           |
| RETRY                          | Number of forward request retries                                                      | 10        |
| RETRY_INTERVAL                 | Interval (seconds) between forward request retries                                     | 5         |
