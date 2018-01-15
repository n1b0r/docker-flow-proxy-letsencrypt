import datetime
import docker
import json
import logging
import os
import requests
import subprocess
import time

from client_dfple import *
from flask import Flask, request, send_from_directory


LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warning': logging.WARNING,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}

logging.basicConfig(level=logging.ERROR, format="%(asctime)s;%(levelname)s;%(message)s")
logging.getLogger('letsencrypt').setLevel(LEVELS[os.environ.get('LOG', 'info').lower()])
logger = logging.getLogger('letsencrypt')

CERTBOT_WEBROOT_PATH = os.environ.get('CERTBOT_WEBROOT_PATH', '/opt/www')

docker_client = None
docker_socket_path = os.environ.get('DOCKER_SOCKET_PATH')
if docker_socket_path and os.path.exists(docker_socket_path):
    logger.debug('docker_socket_path {}'.format(docker_socket_path))
    docker_client = docker.DockerClient(
        base_url='unix:/{}'.format(docker_socket_path),
        version='1.25')

args = {
    'certbot_path': os.environ.get('CERTBOT_PATH', '/etc/letsencrypt'),
    'certbot_challenge': os.environ.get('CERTBOT_CHALLENGE', 'http'),
    'certbot_webroot_path': CERTBOT_WEBROOT_PATH,
    'certbot_options': os.environ.get('CERTBOT_OPTIONS', ''),
    'certbot_manual_auth_hook': os.environ.get('CERTBOT_MANUAL_AUTH_HOOK'),
    'certbot_manual_cleanup_hook': os.environ.get('CERTBOT_MANUAL_CLEANUP_HOOK'),
    'docker_client': docker_client,
    'docker_socket_path': docker_socket_path,
    'dfp_service_name': os.environ.get('DF_PROXY_SERVICE_NAME'),
}

client = DFPLEClient(**args)

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

        # Check if the newly registered service is using letsencrypt companion.
        # Labels required:
        #   * com.df.letsencrypt.email

        # explicitly make it a tuple
        required_labels = ('letsencrypt.email', )

        # v1: com.df.serviceDomain=example.com
        # v2: com.df.serviceDomain=example.com,foo.bar
        # v3: com.df.serviceDomain.1=example.com  com.df.serviceDomain.2=foo.bar
        # v4.1: 2+ domains are specified in serviceDomain and only one is in letsencrypt.host ?
        # v4.2 ... the the other way around
        # => we don't need to solve it - it's user's problem and / or user only wants 1 url behind HTTPS, the other not
        le_hosts = []
        extract_hosts_from_service_domain = False

        if 'letsencrypt.host' in args:
            le_hosts = args['letsencrypt.host'].split(',')
        else:
            extract_hosts_from_service_domain = True

        if extract_hosts_from_service_domain:

            for key, value in args.iteritems():
                if 0 == key.find('serviceDomain'):
                    le_hosts += value.split(',')

        if all([label in args.keys() for label in required_labels]):
            logger.info('letsencrypt support enabled.')

            testing = None
            if 'letsencrypt.testing' in args:
                testing = args['letsencrypt.testing']
                if isinstance(testing, basestring):
                    testing = True if testing.lower() == 'true' else False

            client.process(le_hosts, args['letsencrypt.email'], testing=testing)

    # proxy requests to docker-flow-proxy
    # sometimes we can get an error back from DFP, this can happen when DFP is not fully loaded.
    # resend the request until response status code is 200 (${RETRY} times waiting ${RETRY_INTERVAL} seconds between retries)
    t = 0
    while t < os.environ.get('RETRY', 10):
        t += 1

        logger.debug('forwarding request to docker-flow-proxy ({})'.format(t))
        try:
            response = dfp_client.get(dfp_client.url(version, '/reconfigure?{}'.format(
                '&'.join(['{}={}'.format(k, v) for k, v in request.args.items()]))))
            if response.status_code == 200:
                break
        except Exception, e:
            logger.error('Error while trying to forward request: {}'.format(e))
        logger.debug('waiting for retry')
        time.sleep(os.environ.get('RETRY_INTERVAL', 5))

    return "OK"


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)