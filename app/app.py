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

logging.basicConfig(level=LEVELS.get(os.environ.get('LOG', 'info').lower()))

logger = logging.getLogger(__name__)

DF_NOTIFY_CREATE_SERVICE_URL = os.environ.get('DF_NOTIFY_CREATE_SERVICE_URL')
DF_PROXY_SERVICE_BASE_URL = os.environ.get('DF_PROXY_SERVICE_BASE_URL')
CERTBOT_WEBROOT_PATH = os.environ.get('CERTBOT_WEBROOT_PATH', '/opt/www')
CERTBOT_OPTIONS = os.environ.get('CERTBOT_OPTIONS', '')
CERTBOT_FOLDER = "/etc/letsencrypt/"

docker_client = None
docker_socket_path = os.environ.get('DOCKER_SOCKET_PATH')
logger.debug('docker_socket_path {}'.format(docker_socket_path))
if docker_socket_path and os.path.exists(docker_socket_path):
    docker_client = docker.DockerClient(
        base_url='unix:/{}'.format(docker_socket_path),
        version='1.25')

dfple_client = DFPLE(docker_client, docker_socket_path, CERTBOT_WEBROOT_PATH, CERTBOT_OPTIONS, CERTBOT_FOLDER)

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

            logger.info('letencrypt support enabled.')

            # if letsencrypt support enabled, generate or renew certificates.
            domains = args.get('letsencrypt.host').split(',')
            email = args.get('letsencrypt.email')

            certificates, created = dfple_client.generate_certificates(domains, email)

            if docker_client == None:
                if created:
                    # no docker client provided, use docker-flow-proxy PUT request to update certificate
                    for domain, certs in certificates.items():
                        cert = [x for x in certs if '.pem' if x][0]
                        dfp_client.put(
                            dfp_client.url(
                                version, 
                                '/cert?certName={}&distribute=true'.format(os.path.basename(cert))),
                            data=open(cert, 'rb').read(),
                            headers={'Content-Type': 'application/octet-stream'})

            # docker engine is provided, manage certificates as docker secrets
            else:

                # get current dfp secrets
                service = dfple_client.service_get(os.environ.get('DF_PROXY_SERVICE_NAME'))
                service_secrets = service.attrs['Spec']['TaskTemplate']['ContainerSpec'].get('Secrets', [])
                logger.debug('service_secrets : {}'.format(service_secrets))
                secrets_changed = False

                # for each combined certificates
                for domain, certs in certificates.items():
                    combined = [x for x in certs if '.pem' in x][0]
                    
                    if created:
                        # create a docker secret
                        secret = dfple_client.secret_create(
                            '{}.pem'.format(domain),
                            open(combined, 'rb').read())                        

                        # remove secrets already attached to the dfp service
                        # that are for the same domain.
                        logger.debug('service_secrets222 : {}'.format(service_secrets))
                        service_secrets = [x for x in service_secrets if not x['SecretName'].startswith(domain)] 

                        # append the new secret
                        secrets_changed = True
                        service_secrets.append({
                            'SecretID': secret.id,
                            'SecretName': secret.name,
                            'File': {
                                'Name': 'cert-{}'.format(domain),
                                'UID': '0',
                                'GID': '0', 
                                'Mode': 0}
                            })
                    else:
                        # check that a already existing secret for the combined cert is attached to dfp service.
                        found = any([x['File']['Name'] == 'cert-{}'.format(domain) for x in service_secrets])
                        logger.debug('found: {}'.format(found))
                        if not found:
                            secret = docker_client.secrets().list(filters={'name': '{}.pem'.format(domain)})[-1] 
                            # append the secret
                            secrets_changed = True
                            service_secrets.append({
                                'SecretID': secret.id,
                                'SecretName': secret.name,
                                'File': {
                                    'Name': 'cert-{}'.format(domain),
                                    'UID': '0',
                                    'GID': '0', 
                                    'Mode': 0}
                                })   


                if secrets_changed:
                    logger.debug('secrets changed, updating...')
                    # attach new secrets to dfp service
                    dfple_client.service_update_secrets(service, service_secrets)

    # proxy requests to docker-flow-proxy
    dfp_client.get(dfp_client.url(version, '/reconfigure?{}'.format(
        '&'.join(['{}={}'.format(k, v) for k, v in args.items()]))))    

    return "OK"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)