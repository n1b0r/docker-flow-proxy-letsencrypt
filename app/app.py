import docker
import json
import logging
import os
import requests
import subprocess
import time

from flask import Flask, request, send_from_directory

LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warning': logging.WARNING,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}

logging.basicConfig(level=LEVELS.get(os.environ.get('LOG', 'info').lower()))
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




class DockerFlowProxyAPIClient:
    def __init__(self, DF_PROXY_SERVICE_BASE_URL=None, adaptor=None):
        self.base_url = DF_PROXY_SERVICE_BASE_URL
        if self.base_url is None:
            self.base_url = os.environ.get('DF_PROXY_SERVICE_NAME')

        self.adaptor = adaptor
        if self.adaptor is None:
            self.adaptor = requests

    def url(self, version, url):
        return 'http://{}:8080/v{}/docker-flow-proxy'.format(self.base_url, version) + url

    def _request(self, method_name, url, **kwargs):
        logger.debug('[{}] {}'.format(method_name, url))
        r = getattr(self.adaptor, method_name)(url, **kwargs)
        logger.debug('     {}: {}'.format(r.status_code, r.text))
        return r 
    def put(self, *args, **kwargs):
        return self._request('put', *args, **kwargs)
    def get(self, *args, **kwargs):
        return self._request('get', *args, **kwargs)


class CertbotClient():
    def __init__(self):
        pass

    def run(self, cmd):
        # cmd = cmd.split()
        logger.debug('executing cmd : {}'.format(cmd))
        process = subprocess.Popen(cmd,
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE)
        output, error = process.communicate()
        logger.debug("o: {}".format(output))
        if error:
            logger.debug(error)
        logger.debug("r: {}".format(process.returncode))
        
        return output, error, process.returncode

    def update_cert(self, domains, email):
        """
        Update certifacts
        """
        output, error, code = self.run("""certbot certonly \
                    --agree-tos \
                    --domains {domains} \
                    --email {email} \
                    --expand \
                    --noninteractive \
                    --webroot \
                    --webroot-path {webroot_path} \
                    --debug \
                    {options}""".format(
                        domains=domains,
                        email=email,
                        webroot_path=CERTBOT_WEBROOT_PATH,
                        options=CERTBOT_OPTIONS).split())

        if b'urn:acme:error:unauthorized' in error:
            logger.error('Error during ACME challenge, is the domain name associated with the right IP ?')

        if error or b'no action taken.' in output:
            return False

        return True


class DFPLE():

    @classmethod    
    def service_update_secrets(cls, service, secrets):

        spec = service.attrs['Spec']
        container_spec = update_data['TaskTemplate']['ContainerSpec']

        if "Secrets" in container_spec.keys():
            # keep secrets that are not matching aliases
            secrets = [x for x in container_spec['Secrets'] if not any([x['File']['Name'] == a for a in secrets.keys()])]
        else:
            secrets = []

        for alias, secret in secrets.items():
            secrets.append({
                'SecretID': secret.id,
                'SecretName': secret.name,
                'File': {
                    'Name': alias,
                    'UID': '0',
                    'GID': '0',
                    'Mode': 0}})

        container_spec['Secrets'] = secrets

        cmd = """curl -X POST -H "Content-Type: application/json" --unix-socket {socket} http:/1.25/services/{service_id}/update?version={version} -d '{data}'""".format(
            data=json.dumps(update_data), socket=docker_socket_path, service_id=service.id, version=service.attrs['Version']['Index'])
        logger.debug('EXEC {}'.format(cmd))
        code = os.system(cmd)
     
    @classmethod    
    def secret_create(cls, secret_name, secret_data):

        # search for already existing secrets
        s = docker_client.secrets().list(filters={'name': secret_name})
        secret_name = "{}{}".format(secret_name, '-{}'.format(len(s)) if len(s) else '')

        # create secret.
        logger.debug('creating secret {}'.format(secret_name))
        secret = docker_client.secrets().create(
            name=secret_name,
            data=secret_data)
        logger.debug('secret created {}'.format(secret.id))

    @classmethod
    def service_get(service_name):
        services = docker_client.services.list(
            filters={'name': service_name})
        services = [x for x in services if x.name == service_name]
        if len(services) == 1:
            return services[0]
        else:
            return None


app = Flask(__name__)

@app.route("/.well-known/acme-challenge/<path>")
def acme_challenge(path):
    return send_from_directory(CERTBOT_WEBROOT_PATH,
        ".well-known/acme-challenge/{}".format(path))

@app.route("/v<int:version>/docker-flow-proxy-letsencrypt/reconfigure")
def update(version):

    dfp_client = DockerFlowProxyAPIClient()
    certbot = CertbotClient()
    
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

                service_secrets = []
                cert_types = [
                    ('combined', 'pem'),
                    ('fullchain', 'crt'),
                    ('privkey', 'key')]
                for domain in domains.split(','):
                    
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

                            secret = DFPLE.secret_create('dfple-cert-{}.{}'.format(domain, cert_extension), open(dest_file, 'rb').read())
                            service_secrets.append(secret)

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
                    service = DFPLE.service_get(os.environ.get('DF_PROXY_SERVICE_NAME'))
                    if service:
                        aliases = {}
                        for d in domains:
                            aliases.update({'cert-{}'.format(d): [ x for x in service_secrets if x.name.startswith('dfple-cert-{}.pem'.format(domain))][0]})
                        DFPLE.service_update_secrets(service, aliases)
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