import datetime
import json
import os
from client_certbot import CertbotClient
from client_dfp import DockerFlowProxyAPIClient

import logging
logger = logging.getLogger('letsencrypt')


cert_types = [
    ('combined', 'pem'),
    ('fullchain', 'crt'),
    ('privkey', 'key')]

class DFPLEClient():

    def __init__(self, **kwargs):
        logger.debug('> init')

        self.docker_client = kwargs.get('docker_client')
        # self.docker_socket_path = kwargs.get('docker_socket_path')
        # XXX-YYYYMMDD-HHMMSS
        self.size_secret = 64 - 16
        self.certbot = CertbotClient(
            kwargs.get('certbot_challenge'),
            webroot_path=kwargs.get('certbot_webroot_path'),
            options=kwargs.get('certbot_options'))
        self.certbot_folder = kwargs.get('certbot_path')
        self.dfp_service_name = kwargs.get('dfp_service_name', None)

        self.dfp_client = DockerFlowProxyAPIClient()

        self.secrets_initial = []
        self.service_dfp_secrets = []
        self.certs = []
        self.cert_combined_exists = None
        created = None
        self.secret_combined_found = None
        self.secret_combined_attached = None


        self.domains = kwargs.get('domains', [])
        self.email = kwargs.get('email')
        self.certs = {}
        self.certs_created = False
        self.secrets = {}
        self.secrets_created = False

        self.initial_checks()


    def initial_checks(self):

        # check certs
        self.check_certs()

        if self.docker_client is not None:

            # get secrets
            self.check_secrets()

            # get dfp service secrets
            self.check_secrets_dfp()

    def check_certs(self):
        logger.debug('> check_certs')
        self.certs = {}
        for domain in self.domains:
            self.certs[domain] = []
            for cert_type, cert_extension in cert_types:
                dest_file = os.path.join(self.certbot_folder, "{}.{}".format(domain, cert_extension))
                if os.path.exists(dest_file):
                    # logger.debug('  found {}'.format(dest_file))
                    self.certs[domain].append(dest_file)

        logger.debug('< certs={}'.format(self.certs))
    def check_secrets(self):
        logger.debug('> check_secrets')
        self.secrets = self.docker_client.secrets.list()
        logger.debug('< secrets={}'.format(self.secrets))

    def check_secrets_dfp(self):
        logger.debug('> check_secrets_dfp')
        self.secrets_dfp = []
        # get current dfp secrets
        self.dfp = self.service_dfp()
        self.secrets_dfp = self.dfp.attrs['Spec']['TaskTemplate']['ContainerSpec'].get('Secrets', [])
        logger.debug('< secrets_dfp={}'.format(self.secrets_dfp))


    def generate_certificates(self, domains, email):
        """
            Generate or renew certificates for given domains

            :param domains: Domain names to generate certificates. Comma separated.
            :param email: Email used during letsencrypt process
            :type a: string
            :type b: string
            :return: List of freshly created certificates path
            :rtype: list of string
        """
        certs = {}
        for domain in domains:
            certs[domain] = []

        logger.debug('Generating certificates domains:{} email:{}'.format(domains, email))
        error, created = self.certbot.update_cert(domains, email)

        if error and not created:
            logger.error('Error while generating certs for {}'.format(domains))
        elif not error and not created:
            logger.debug('nothing to do')
            # no certs generated, search for already existing certificates
            for domain in domains:
                for cert_type, cert_extension in cert_types:
                    dest_file = os.path.join(self.certbot_folder, "{}.{}".format(domain, cert_extension))
                    if os.path.exists(dest_file):
                        certs[domain].append(dest_file)

                if any(['.pem' in x for x in certs[domain]]):
                    logger.info('combined certificate found at "{}".'.format(self.certbot_folder))
                    self.cert_combined_exists = True
        elif created:
            logger.info('certificates successfully created using certbot.')

            # if multiple domains comma separated, take only the first one
            base_domain = domains[0]

            # generate combined certificate needed for haproxy
            combined_path = os.path.join(self.certbot_folder, 'live', base_domain, "combined.pem")
            with open(combined_path, "w") as combined, \
                 open(os.path.join(self.certbot_folder, 'live', base_domain, "privkey.pem"), "r") as priv, \
                 open(os.path.join(self.certbot_folder, 'live', base_domain, "fullchain.pem"), "r") as fullchain:

                combined.write(fullchain.read())
                combined.write(priv.read())
                logger.info('combined certificate generated into "{}".'.format(combined_path))

            # for each domain, create a symlink for main combined cert.
            for domain in domains:
                for cert_type, cert_extension in cert_types:
                    dest_file = os.path.join(self.certbot_folder, "{}.{}".format(domain, cert_extension))

                    if os.path.exists(dest_file):
                        os.remove(dest_file)

                    # generate symlinks
                    os.symlink(
                        os.path.join('./live', base_domain, "{}.pem".format(cert_type)),
                        dest_file)

                    certs[domain].append(dest_file)

        return certs, created

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
        secret_name = name[-self.size_secret:]
        secret_name += '-{}'.format(datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        return secret_name

    # def service_update_secrets(self, service, secrets):
    #     service.update(name=service.attrs['Spec']['Name'], networks=service.attrs['Spec']['Networks'], secrets=secrets)
    #     # spec = service.attrs['Spec']
    #     # container_spec = spec['TaskTemplate']['ContainerSpec']
    #     # container_spec['Secrets'] = secrets

    #     # cmd = """curl -X POST -H "Content-Type: application/json" --unix-socket {socket} http:/1.25/services/{service_id}/update?version={version} -d '{data}'""".format(
    #     #     data=json.dumps(spec), socket=self.docker_socket_path, service_id=service.id, version=service.attrs['Version']['Index'])
    #     # logger.debug('EXEC {}'.format(cmd))
    #     # code = os.system(cmd)

    def secret_create(self, secret_name, secret_data):

        secret_name = self.get_secret_name(secret_name)

        # create secret.
        logger.debug('creating secret {}'.format(secret_name))
        secret = self.docker_client.secrets.create(
            name=secret_name,
            data=secret_data)
        logger.debug('secret created {}'.format(secret.id))

        secret = self.docker_client.secrets.get(secret.id)
        return secret

    def service_get(self, service_name):
        services = self.docker_client.services.list(
            filters={'name': service_name})
        services = [x for x in services if x.name == service_name]
        if len(services) == 1:
            return services[0]
        else:
            return None

    def check_secret_combined_found(self, name):
        return len(self.docker_client.secrets.list(filters={'name': name})) > 0

    def service_dfp(self):
        return self.service_get(self.dfp_service_name)

    def process(self,
                version='1'):

        logger.info('Letsencrypt support enabled, processing request: domains={} email={}'.format(','.join(self.domains), self.email))

        self.certs, created = self.generate_certificates(self.domains, self.email)

        secrets_changed = False
        for domain, certs in self.certs.items():

            combined = [x for x in certs if '.pem' in x]
            if len(combined) == 0:
                logger.error('Combined certificate not found. Check logs for errors.')
                return False
            combined = combined[0]

            if self.docker_client == None:
                if created:
                    # no docker client provided, use docker-flow-proxy PUT request to update certificate
                    self.dfp_client.put(
                        self.dfp_client.url(
                            version,
                            '/cert?certName={}&distribute=true'.format(os.path.basename(combined))),
                        data=open(combined, 'rb').read(),
                        headers={'Content-Type': 'application/octet-stream'})
                    logger.info('Request PUT /cert sucessfully send to DFP.')

            else:
                # docker engine is provided, manage certificates as docker secrets

                # check that there is an existing secret for the combined cert
                # secrets = self.secrets_get()
                self.secret_combined_found = False #self.check_secret_combined_found('cert-{}.pem'.format(domain))
                # combined_found = any([x.name == 'cert-{}.pem'.format(domain) for x in self.secrets_get()])

                # check that an already existing secret for the combined cert is attached to dfp service.
                # TODO: what if the domain name is really long ?
                self.secret_combined_attached = any([x['File']['Name'] == 'cert-{}'.format(domain) for x in self.secrets_dfp])
                logger.debug('cert_created={} cert_exists={} secret_found={} secret_attached={}'.format(created, self.cert_combined_exists, self.secret_combined_found, self.secret_combined_attached))

                if created or not self.secret_combined_found:
                    # create secret
                    secret_cert = '{}.pem'.format(domain)
                    logger.info('creating secret for cert {}'.format(secret_cert))
                    secret = self.secret_create(
                            secret_cert,
                            open(combined, 'rb').read())
                    self.secrets.append(secret)
                # else:
                #     secret = secrets[0]

                if created or not self.secret_combined_attached:
                    # attach secret
                    # secret = self.docker_client.secrets.list(filters={'name': '{}.pem'.format(domain)})[-1]
                    logger.info('attaching secret {}'.format(secret.name))
                    # remove secrets already attached to the dfp service that are for the same domain.
                    self.secrets_dfp = [x for x in self.secrets_dfp if not x['SecretName'].startswith(domain)]

                    # append the secret
                    secrets_changed = True
                    self.secrets_dfp.append({
                        'SecretID': secret.id,
                        'SecretName': secret.name,
                        'File': {
                            'Name': 'cert-{}'.format(domain),
                            'UID': '0',
                            'GID': '0',
                            'Mode': 0}
                        })

        if secret_changed:
            logger.debug('secrets changed, updating dfp service...')
            self.dfp.update(name=self.dfp.attrs['Spec']['Name'], networks=self.dfp.attrs['Spec']['Networks'], secrets=self.secrets_dfp)
