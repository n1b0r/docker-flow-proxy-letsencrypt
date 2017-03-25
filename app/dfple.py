import datetime
import logging
import os
import requests
import subprocess
import json

logger = logging.getLogger('letsencrypt')


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
    def __init__(self, webroot_path, options):
        self.webroot_path = webroot_path
        self.options = options

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
                        webroot_path=self.webroot_path,
                        options=self.options).split())

        if b'urn:acme:error:unauthorized' in error:
            logger.error('Error during ACME challenge, is the domain name associated with the right IP ?')

        if b'no action taken.' in output:
            logger.debug('Nothing to do. Skipping.')
            return False

        if code != 0:
            logger.error('Certbot return code: {}. Skipping'.format(code))
            return False

        return True


class DFPLE():

    def __init__(self, docker_client=None, docker_socket_path=None):
        self.docker_client = docker_client
        self.docker_socket_path = docker_socket_path
        # cert-XXX-YYYYMMDD-HHMMSS
        self.size_secret = 64 - 5 - 16

    def new_secret_name(self, name, template='{name}-{suffix}', suffix=None):
        """
        generate a new secret name. To make it unique, use datetime.
        """
        if suffix is None:
            suffix = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

        rest = 64 - len(suffix) - 1

        if len(name) > rest:
            name = name[-rest:]

        return template.format(
            name=name, 
            suffix=suffix)

    def service_new_secrets(self, secrets, service=None, service_secrets=None):
        if service:
            service_secrets = service.attrs['Spec']['TaskTemplate']['ContainerSpec'].get('Secrets', [])
        # keep other secrets
        _secrets = [ x for x in service_secrets if not any([x['File']['Name'] == a['File']['Name'] for a in secrets])]
        for x in secrets:
            _secrets.append(x)
        return _secrets

    def get_secret_name(self, name):
        secret_name = 'cert-' + name[-self.size_secret:]
        secret_name += '-{}'.format(datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        return secret_name

    def service_update_secrets(self, service, secrets):
        
        spec = service.attrs['Spec']
        container_spec = spec['TaskTemplate']['ContainerSpec']
        container_spec['Secrets'] = secrets

        cmd = """curl -X POST -H "Content-Type: application/json" --unix-socket {socket} http:/1.25/services/{service_id}/update?version={version} -d '{data}'""".format(
            data=json.dumps(spec), socket=self.docker_socket_path, service_id=service.id, version=service.attrs['Version']['Index'])
        logger.debug('EXEC {}'.format(cmd))
        code = os.system(cmd)
       
    def secret_create(self, secret_name, secret_data):

        secret_name = self.get_secret_name(secret_name)

        # create secret.
        logger.debug('creating secret {}'.format(secret_name))
        secret = self.docker_client.secrets().create(
            name=secret_name,
            data=secret_data)
        logger.debug('secret created {}'.format(secret.id))

        secret = self.docker_client.secrets().get(secret.id)
        return secret

    def service_get(self, service_name):
        services = self.docker_client.services.list(
            filters={'name': service_name})
        services = [x for x in services if x.name == service_name]
        if len(services) == 1:
            return services[0]
        else:
            return None