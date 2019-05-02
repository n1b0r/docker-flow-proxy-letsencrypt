# Using letsencrypt DNS challenge

Please check the certbot [documentation related to manual scripts](https://certbot.eff.org/docs/using.html#pre-and-post-validation-hooks)

In this example we are using the OVH hooks. You could also provide your own manual scripts.

```
docker service create --name proxy_proxy-le \
	--network proxy \
	-e DF_PROXY_SERVICE_NAME=proxy_proxy \
	-e CERTBOT_OPTIONS=--staging \
	-e CERTBOT_CHALLENGE=dns \
    -e CERTBOT_MANUAL_AUTH_HOOK=/app/hooks/ovh/manual-auth-hook.sh \
    -e CERTBOT_MANUAL_CLEANUP_HOOK=/app/hooks/ovh/manual-cleanup-hook.sh \
    -e OVH_DNS_ZONE=XXXXXX \
    -e OVH_APPLICATION_KEY=XXXXXX \
    -e OVH_APPLICATION_SECRET=XXXXXX \
    -e OVH_CONSUMER_KEY=XXXXXX \
	--mount "type=volume,source=le-certs,destination=/etc/letsencrypt" \
	nib0r/docker-flow-proxy-letsencrypt
```


## DigitalOcean DNS hook

This example uses DigitalOcean hooks.

```
docker service create --name proxy_proxy-le \
	--network proxy \
	-e DF_PROXY_SERVICE_NAME=proxy_proxy \
	-e CERTBOT_OPTIONS=--staging \
	-e CERTBOT_CHALLENGE=dns \
    -e CERTBOT_MANUAL_AUTH_HOOK=/app/hooks/do/manual-auth-hook.sh \
    -e CERTBOT_MANUAL_CLEANUP_HOOK=/app/hooks/do/manual-cleanup-hook.sh \
    -e DO_API_KEY=XXXXXX \
	--mount "type=volume,source=le-certs,destination=/etc/letsencrypt" \
	nib0r/docker-flow-proxy-letsencrypt
```
