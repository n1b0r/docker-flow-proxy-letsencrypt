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
    -e OVH_DNS_ZONE=nibor.me \
    -e OVH_APPLICATION_KEY=XXXXXX \
    -e OVH_APPLICATION_SECRET=XXXXXX \
    -e OVH_CONSUMER_KEY=XXXXXX \
	--mount "type=volume,source=le-certs,destination=/etc/letsencrypt" \
	nib0r/docker-flow-proxy-letsencrypt
```




