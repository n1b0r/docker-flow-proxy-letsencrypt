import datetime
import docker
import json
import logging
import os
import requests
import subprocess
import time

from dfple import *
from flask import Flask, request, send_from_directory


LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warning': logging.WARNING,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}

logging.basicConfig(level=logging.ERROR, format="%(asctime)s;%(levelname)s;%(message)s")
logging.getLogger('letsencrypt').setLevel(os.environ.get('LOG', 'info').lower())
logger = logging.getLogger('letsencrypt')

CERTBOT_WEBROOT_PATH = os.environ.get('CERTBOT_WEBROOT_PATH', '/opt/www')

docker_client = None
docker_socket_path = os.environ.get('DOCKER_SOCKET_PATH')
if docker_socket_path and os.path.exists(docker_socket_path):
    logger.debug('docker_socket_path {}'.format(docker_socket_path))
    docker_client = docker.DockerClient(
        base_url='unix:/{}'.format(docker_socket_path),
        version='1.25')

# dfple_client = DFPLE(docker_client, docker_socket_path, CERTBOT_WEBROOT_PATH, CERTBOT_OPTIONS, CERTBOT_FOLDER)

app = Flask(__name__)

@app.route("/.well-known/acme-challenge/<path>")
def acme_challenge(path):
    return send_from_directory(CERTBOT_WEBROOT_PATH,
        ".well-known/acme-challenge/{}".format(path))

@app.route("/v<int:version>/docker-flow-proxy-letsencrypt/reconfigure")
def reconfigure(version):

    dfp_client = DockerFlowProxyAPIClient()
    args = request.args

    if version != 1:
        logger.error('Unable to use version : {}. Forwarding initial request to docker-flow-proxy service.'.format(version))
    else:

        logger.info('request for service: {}'.format(args.get('serviceName')))

        # Check if the newly registered service is usign letsencrypt companion.
        # Labels required:
        #   * com.df.letsencrypt.host
        #   * com.df.letsencrypt.email
        required_labels = ('letsencrypt.host', 'letsencrypt.email')
        if all([label in args.keys() for label in required_labels]):
            logger.info('letsencrypt support enabled.')

            args = {
                'domains': args['letsencrypt.host'],
                'email': args['letsencrypt.email'],
                'certbot_path': os.environ.get('CERTBOT_PATH', '/etc/letsencrypt'),
                'certbot_challenge': os.environ.get('CERTBOT_CHALLENGE', ''),
                'certbot_options': os.environ.get('CERTBOT_OPTIONS', ''),
                'docker_client': docker_client,
                'dfp_service_name': os.environ.get('DF_PROXY_SERVICE_NAME'),
            }

            client = DFPLEClient(**args)
            client.process()

    # proxy requests to docker-flow-proxy
    # sometimes we can get an error back from DFP, this can happen when DFP is not fully loaded.
    # resend the request until response status code is 200 (${RETRY} times waiting ${RETRY_INTERVAL} seconds between retries)
    t = 0
    while t < os.environ.get('RETRY', 10):
        t += 1

        logger.debug('forwarding request to docker-flow-proxy ({})'.format(t))
        response = dfp_client.get(dfp_client.url(version, '/reconfigure?{}'.format(
            '&'.join(['{}={}'.format(k, v) for k, v in args.items()]))))

        if response.status_code == 200:
            break

        time.sleep(os.environ.get('RETRY_INTERVAL', 5))

    return "OK"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)