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
        self.docker_socket_path = kwargs.get('docker_socket_path')
        # XXX-YYYYMMDD-HHMMSS
        self.size_secret = 64 - 16

        self.certbot = CertbotClient(
            challenge=kwargs.get('certbot_challenge'),
            webroot_path=kwargs.get('certbot_webroot_path'),
            options=kwargs.get('certbot_options'),
            manual_auth_hook=kwargs.get('certbot_manual_auth_hook'),
            manual_cleanup_hook=kwargs.get('certbot_manual_cleanup_hook')
            )
        self.certbot_folder = kwargs.get('certbot_path')

        self.dfp_service_name = kwargs.get('dfp_service_name', None)

        self.dfp_client = DockerFlowProxyAPIClient()

        # self.domains = kwargs.get('domains', [])
        # self.email = kwargs.get('email')
        # self.certs = {}
        # self.certs_created = False
        # self.secrets = {}
        # self.secrets_created = False

        # self.initial_checks()


    def certs(self, domains):
        certs = {}
        for domain in domains:
            certs[domain] = []
            for cert_type, cert_extension in cert_types:
                dest_file = os.path.join(self.certbot_folder, "{}.{}".format(domain, cert_extension))
                if os.path.exists(dest_file):
                    certs[domain].append(dest_file)
        return certs

    def secrets(self, domain=None):
        secrets = []
        attrs = {}
        if domain is not None:
            attrs['filters'] = {"name": self.get_secret_name_short('{}.pem'.format(domain))}
        return self.docker_client.secrets.list(**attrs)

    def services(self, name, exact_match=True):
        services = self.docker_client.services.list(
            filters={'name': name})
        if exact_match:
            services = [x for x in services if x.name == name]
        return services

    def service_get_secrets(self, service):
        return service.attrs['Spec']['TaskTemplate']['ContainerSpec'].get('Secrets', [])

    def get_secret_name_short(self, name):
        secret_name = name[-self.size_secret:]
        return secret_name

    def get_secret_name(self, name):
        secret_name = self.get_secret_name_short(name)
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
        secret = self.docker_client.secrets.create(
            name=secret_name,
            data=secret_data)
        logger.debug('secret created {}'.format(secret.id))

        secret = self.docker_client.secrets.get(secret.id)
        return secret

    def generate_certificates(self, domains, email, testing=False):
        """
            Generate or renew certificates for given domains

            :param testing: Issue testing / staging certificate
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

        logger.debug('Generating certificates domains:{} email:{} testing:{}'.format(domains, email, testing))
        error, created = self.certbot.update_cert(domains, email, testing)

        if error and not created:
            logger.error('Error while generating certs for {}'.format(domains))

        elif not error and not created:
            logger.debug('nothing to do')
            certs = self.certs(domains)

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

    def process(self, domains, email, version='1', testing=False):
        logger.info('Letsencrypt support enabled, processing request: domains={} email={} testing={}'.format(','.join(domains), email, testing))

        certs, created = self.generate_certificates(domains, email, testing)

        secrets_changed = False
        if self.docker_client != None:
            self.dfp = self.services(self.dfp_service_name)[0]
            self.dfp_secrets = self.service_get_secrets(self.dfp)

        for domain, certs in certs.items():

            combined = [x for x in certs if '.pem' in x]
            if len(combined) == 0:
                logger.error('Combined certificate not found. Check logs for errors.')
                # raise Exception to make a 500 response to dpf, and make it retry the request later.
                raise Exception('Combined cert not found')
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
                # secret_combined_found = any([x.name.startswith('{}.pem'.format(domain)[-self.size_secret:]) for x in self.secrets])
                self._secrets = self.secrets('{}.pem'.format(domain))
                secret_combined_found = False
                if len(self._secrets):
                    secret = self._secrets[-1]
                    logger.debug('combined secret for {} found : {} list: {}'.format(domain, secret, self._secrets))
                    secret_combined_found = True

                # check that an already existing secret for the combined cert is attached to dfp service.
                # secret_combined_attached = any([x['File']['Name'] == 'cert-{}'.format(domain) for x in self.secrets_dfp])
                secret_combined_attached = any([x['File']['Name'] == 'cert-{}'.format(domain) for x in self.dfp_secrets])

                logger.debug('cert_created={} secret_found={} secret_attached={}'.format(created, secret_combined_found, secret_combined_attached))

                if created or not secret_combined_found:
                    # create secret
                    secret_cert = '{}.pem'.format(domain)
                    logger.info('creating secret for cert {}'.format(secret_cert))
                    secret = self.secret_create(
                            secret_cert,
                            open(combined, 'rb').read())
                    self._secrets.append(secret)

                if created or not secret_combined_attached:
                    # attach secret
                    logger.info('attaching secret {}'.format(secret.name))

                    # remove secrets already attached to the dfp service that are for the same domain.
                    self.dfp_secrets = [x for x in self.dfp_secrets if not x['SecretName'].startswith(domain)]

                    # append the secret
                    secrets_changed = True
                    self.dfp_secrets.append({
                        'SecretID': secret.id,
                        'SecretName': secret.name,
                        'File': {
                            'Name': 'cert-{}'.format(domain),
                            'UID': '0',
                            'GID': '0',
                            'Mode': 0}
                        })

        if secrets_changed:
            logger.debug('secrets changed, updating dfp service...')
            # I cannot understand how to use the service.update method, use a POST request against docker socket instead
            # see https://github.com/docker/docker-py/issues/1503
            # self.dfp.update(name=self.dfp.attrs['Spec']['Name'], networks=self.dfp.attrs['Spec']['Networks'], secrets=self.secrets_dfp)
            self.service_update_secrets(self.dfp, self.dfp_secrets)
