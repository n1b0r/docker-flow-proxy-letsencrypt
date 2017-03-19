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

logger = logging.getLogger('letsencrypt')

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

dfple_client = DFPLE(docker_client, docker_socket_path)

app = Flask(__name__)

@app.route("/.well-known/acme-challenge/<path>")
def acme_challenge(path):
    return send_from_directory(CERTBOT_WEBROOT_PATH,
        ".well-known/acme-challenge/{}".format(path))

@app.route("/v<int:version>/docker-flow-proxy-letsencrypt/reconfigure")
def update(version):

    dfp_client = DockerFlowProxyAPIClient()
    certbot = CertbotClient(CERTBOT_WEBROOT_PATH, CERTBOT_OPTIONS)
    
    if version == 1:

        args = request.args
        logger.info('request for service: {}'.format(args.get('serviceName')))
        
        
        is_letsencrypt_service = all([label in args.keys() for label in ('letsencrypt.host', 'letsencrypt.email')])
        if is_letsencrypt_service:
            logger.info('letencrypt service detected.')


            domains = args.get('letsencrypt.host')
            email = args.get('letsencrypt.email')

            if certbot.update_cert(domains, email):
                logger.info('certificates successfully generated using certbot.')

                # if multiple domains comma separated, take only the first one
                base_domain = domains.split(',')[0]

                # generate combined certificate
                combined_path = os.path.join(CERTBOT_FOLDER, 'live', base_domain, "combined.pem")
                with open(combined_path, "w") as combined, \
                     open(os.path.join(CERTBOT_FOLDER, 'live', base_domain, "privkey.pem"), "r") as priv, \
                     open(os.path.join(CERTBOT_FOLDER, 'live', base_domain, "fullchain.pem"), "r") as fullchain:

                    combined.write(fullchain.read())
                    combined.write(priv.read())
                    logger.info('combined certificate generated into "{}".'.format(combined_path))


                cert_types = [
                    ('combined', 'pem'),
                    ('fullchain', 'crt'),
                    ('privkey', 'key')]

                new_secrets = {}
                domains = domains.split(',')
                for domain in domains:
                    
                    # generate symlinks
                    for cert_type, cert_extension in cert_types:

                        dest_file = os.path.join(CERTBOT_FOLDER, "{}.{}".format(domain, cert_extension))

                        if os.path.exists(dest_file):
                            os.remove(dest_file)

                        os.symlink(
                            os.path.join('./live', base_domain, "{}.pem".format(cert_type)),
                            dest_file)

                        # for each certificate, generate a secret as it could be used by other services
                        if docker_client != None:
                            secret_name = '{}.{}'.format(domain, cert_extension)
                            secret = dfple_client.secret_create(secret_name, open(dest_file, 'rb').read())
                            new_secrets.update({secret_name: secret})

                    if docker_client == None:
                        # old style, use docker-flow-proxy PUT request to update certs
                        cert = os.path.join(CERTBOT_FOLDER, "{}.pem".format(domain))
                        dfp_client.put(
                            dfp_client.url(
                                version, 
                                '/cert?certName={}&distribute=true'.format(os.path.basename(cert))),
                            data=open(cert, 'rb').read(),
                            headers={'Content-Type': 'application/octet-stream'})


                if docker_client != None:
                    
                    # update secrets of docker-flow-proxy service
                    service = dfple_client.service_get(os.environ.get('DF_PROXY_SERVICE_NAME'))
                    if service:
                        # get service current secrets
                        current_secrets = service.attrs['Spec']['TaskTemplate']['ContainerSpec'].get('Secrets', [])

                        # keep secrets that are not going to be updated
                        secrets = [ x for x in current_secrets if not any([ d in x['File']['Name'] for d in domains])] 

                        # for each domain, add combined cert secret
                        for d in domains:

                            # get the new secret generated for the current cert.
                            name = '{}.pem'.format(d)
                            secret = new_secrets[name]
                            
                            # append it to the secrets list and name it correctly to be handled by dfp (cert-*)
                            secrets.append({
                                'SecretID': secret.id,
                                'SecretName': secret.name,
                                'File': {
                                    'Name': 'cert-{}'.format(d),
                                    'UID': '0',
                                    'GID': '0', 
                                    'Mode': 0}
                                })

                        dfple_client.service_update_secrets(service, secrets)
                    else:
                        logger.error('Could not find service named {}'.format(
                            os.environ.get('DF_PROXY_SERVICE_NAME')))

                    # # find dfp service
                    # dfp_service = os.environ.get('DF_PROXY_SERVICE_NAME')
                    # services = docker_client.services.list(
                    #     filters={'name': dfp_service})
                    # services = [x for x in services if x.name == dfp_service]

                    # if len(services) == 1:
                    #     dfp_service = services[0]

                    #     # find combined certificates
                    #     secrets = [docker_client.secrets().get(x) for x in service_secrets]
                    #     secrets = [x for x in secrets if x.name.endswith('.pem') and x.name.statswith('dfple-cert-')]

                    #     if len(secrets):

                    #         update_data = dfp_service.attrs['Spec']
                    #         container_spec = update_data['TaskTemplate']['ContainerSpec']

                    #         if "Secrets" in container_spec.keys():
                    #             # keep secrets that are not certificates for this domains
                    #             new_secrets = [x for x in container_spec['Secrets'] if not any([x['File']['Name'] == 'cert-{}'.format(a) for a in domains])]
                    #         else:
                    #             new_secrets = []

                    #         for d in domains:
                    #             secret = [ x for x in secrets if d in x.name ]
                    #             secret = secret[0]
                    #             new_secrets.append({
                    #                 'SecretID': secret.id,
                    #                 'SecretName': secret.name,
                    #                 'File': {
                    #                     'Name': 'cert-{}'.format(domain),
                    #                     'UID': '0',
                    #                     'GID': '0',
                    #                     'Mode': 0}})

                    #         container_spec['Secrets'] = new_secrets

                    #         cmd = """curl -X POST -H "Content-Type: application/json" --unix-socket {socket} http:/1.25/services/{service_id}/update?version={version} -d '{data}'""".format(
                    #             data=json.dumps(update_data), socket=docker_socket_path, service_id=service.id, version=service.attrs['Version']['Index'])
                    #         logger.debug('EXEC {}'.format(cmd))
                    #         code = os.system(cmd)

                    #         logger.debug('docker api service update: {}'.format(code))
                    #     else:
                    #         logger.error('Could not find secrets !')
                            

                    # else:
                    #     logger.error('Could not find service named {}'.format(dfp_service))






    # proxy requests to docker-flow-proxy
    dfp_client.get(dfp_client.url(version, '/reconfigure?{}'.format(
        '&'.join(['{}={}'.format(k, v) for k, v in args.items()]))))    

    return "OK"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)