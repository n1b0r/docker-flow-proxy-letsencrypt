# docker-flow-proxy letsencrypt support proposal 

## The actual design

The current design is pretty easy, `docker-flow-swarm-listener` sends all **RECONFIGURE** requests (as defined in the **CREATE** env var) to `docker-flow-proxy-letsencrypt`.

`docker-flow-proxy-letsencrypt` check if the created service use special labels (**com.df.letsencrypt.host**, **com.df.letsencrypt.email**):
  * if yes, we go throught certbot process and if a new certificate is generated, we send it to `docker-flow-proxy` via **PUT /certs**.
  * in both case (if special labels found or not), we forward the original request to `docker-flow-proxy`

`docker-flow-proxy` get the **RECONFIGURE** request and handle the job.


	swarm-listner >> proxy-le >> proxy


## Improved design

The current design is plug-and-play, but if a user do not need letsencrypt support we force him to go throught `docker-flow-proxy-letsencrypt` because all request are send to it.

We should provide a new env var for `docker-flow-swarm-listener` to be able to send a request to `docker-flow-proxy-letsencrypt`. Let say, `DF_NOTIFY_LETSENCRYPT_SERVICE_URL`.

`docker-flow-swarm-listener` could detected new services with letsencrypt support based on labels `com.df.letsencrypt.host`, `com.df.letsencrypt.email`. And then send a request to `docker-flow-swarm-listener` or `docker-flow-proxy`.

Should the `docker-flow-proxy` be also contacted by `docker-flow-swarm-listener` if letsencrypt labels are found ?

In my opinion, this is useless. If we do it, we are going to reload the haproxy two times instead of one (one by the `docker-flow-swarm-listener` and one by the `docker-flow-proxy-letsencrypt` after cert generation).

If we delegate the request to `docker-flow-proxy-letsencrypt`, we trust him to make the whole process happening. 

The purposed design work out of the box, no changes needed on `docker-flow-proxy-letsencrypt`.


	swarm-listner 
				| (if LE labels found) >> proxy-le >> proxy
				| (if no LE labels found) >> proxy

## Things to do

  * make the code more robust (correctly handle errors)
  * renewal process based on cron (we night need that `docker-flow-swarm-listener` gives us the list of services).