import docker
import os
import time
import requests
import subprocess

from unittest import TestCase

class DFPLETestCase(TestCase):
    """
    """

    def setUp(self):
        """
        Setup the needed environment:
          * DFP
          * DFSL
        """

        time.sleep(10)
        self.test_name = os.environ.get('CI_BUILD_REF_SLUG', os.environ.get('CI_COMMIT_REF_SLUG', 'test'))
        self.proxy_le_service_name = 'proxy_le_{}'.format(self.test_name)

        self.docker_client = docker.from_env()
        self.base_domain = 'b.dfple.nibor.me'

        try:
            self.docker_client.swarm.init()
        except docker.errors.APIError:
            pass

        # docker network
        self.network_name = "test-network-dfple"
        self.network = self.docker_client.networks.create(name=self.network_name, driver='overlay')

        # docker-flow-proxy service
        # dfp_image = self.docker_client.images.pull('vfarcic/docker-flow-proxy')
        dfp_service = {
            'name': 'proxy_{}'.format(self.test_name),
            'image': 'vfarcic/docker-flow-proxy',
            'constraints': [],
            'endpoint_spec': docker.types.EndpointSpec(
                ports={80: 80, 443: 443, 8080: 8080}),
            'env': [
                "LISTENER_ADDRESS=swarm_listener_{}".format(self.test_name),
                "MODE=swarm",
                "DEBUG=true",
                "SERVICE_NAME=proxy_{}".format(self.test_name) ],
            'networks': [self.network_name]
        }

        # docker-flow-swarm-listener service
        # dfsl_image = self.docker_client.images.pull('vfarcic/docker-flow-swarm-listener')
        dfsl_service = {
            'name': 'swarm_listener_{}'.format(self.test_name),
            'image': 'vfarcic/docker-flow-swarm-listener',
            'constraints': ["node.role == manager"],
            'endpoint_spec': docker.types.EndpointSpec(
                ports={8081: 8080}),
            'env': [
                "DF_NOTIFY_CREATE_SERVICE_URL=http://proxy_le_{}:8080/v1/docker-flow-proxy-letsencrypt/reconfigure".format(self.test_name),
                "DF_NOTIFY_REMOVE_SERVICE_URL=http://proxy_{}:8080/v1/docker-flow-proxy/remove".format(self.test_name)],
            'mounts': ['/var/run/docker.sock:/var/run/docker.sock:rw'],
            'networks': [self.network_name]
        }

        # start services
        self.services = []

        self.dfp_service = self.docker_client.services.create(**dfp_service)
        self.services.append(self.dfp_service)

        self.dfsl_service = self.docker_client.services.create(**dfsl_service)
        self.services.append(self.dfsl_service)


    def tearDown(self):

        for service in self.services:
            service.remove()

        self.network.remove()

    def get_conf(self):
        try:
            return requests.get('http://{}:8080/v1/docker-flow-proxy/config'.format(self.base_domain), timeout=3).text
        except Exception as e:
            print('Error while getting config on {}: {}'.format(self.base_domain, e))
            return False

    def wait_until_found_in_config(self, texts, timeout=300):
        # print('WAITING FOR', text)

        _start = time.time()
        _current = time.time()

        print '-------------'
        print 'Searching in config for', '\n\t -{}'.format('\n\t -'.join(texts))

        while _current < _start + timeout:

            config = self.get_conf()
            if config:
                if all([t in config for t in texts]):
                    return True

            time.sleep(1)
            _current = time.time()

        print(self.get_conf())
        self.get_service_logs(self.proxy_le_service_name)


        return False


    def get_service_logs(self, name):
        """
        docker-py currently do not support getting service logs.
        """
        cmd = """curl -X GET https://{host}/services/{service_id}/logs?stdout=true&stderr=true --cert {cert} --key {key} --cacert {cacert}""".format(
            host=os.environ.get('DOCKER_HOST').split('//')[1],
            service_id=name,
            cert=os.path.join(os.environ.get('DOCKER_CERT_PATH'), 'cert.pem'),
            key=os.path.join(os.environ.get('DOCKER_CERT_PATH'), 'key.pem'),
            cacert=os.path.join(os.environ.get('DOCKER_CERT_PATH'), 'ca.pem'))

        print('executing cmd', cmd)
        cmd = cmd.split(' ')
        print('executing cmd', cmd)
        proc = subprocess.Popen(cmd,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        (out, err) = proc.communicate()
        print "output:", out, err


class Scenario():

    def test_basic(self):

        # start the testing service
        test_service = {
            'name': 'test_service_{}'.format(self.test_name),
            'image': 'jwilder/whoami',
            'labels': {
                "com.df.notify": "true",
                "com.df.distribute": "true",
                "com.df.serviceDomain": "{0}.{1},{0}2.{1}".format(self.test_name, self.base_domain),
                "com.df.letsencrypt.host": "{0}.{1},{0}2.{1}".format(self.test_name, self.base_domain),
                "com.df.letsencrypt.email": "test@test.com",
                "com.df.servicePath": "/",
                "com.df.srcPort": "443",
                "com.df.port": "8000",
            },
            'networks': [self.network_name]
        }
        service = self.docker_client.services.create(**test_service)
        self.services.append(service)

        # wait until service has registered routes
        self.assertTrue(
            self.wait_until_found_in_config(['test_service_{}'.format(self.test_name)]),
            "test service not registered.")

        # check certs are used
        certs_path = "/run/secrets/cert-"
        ext = ''
        if isinstance(self, DFPLEOriginal):
            certs_path = "/certs/"
            ext = '.pem'

        m = 'ssl crt-list /cfg/crt-list.txt'
        self.assertTrue(self.wait_until_found_in_config([m]))


class DFPLEOriginal(DFPLETestCase, Scenario):


    def setUp(self):

        super(DFPLEOriginal, self).setUp()

        # docker-flow-proxy-letsencrypt service
        dfple_image = self.docker_client.images.build(
            path=os.path.dirname(os.path.abspath(__file__)),
            tag='robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
            quiet=False)
        dfple_service = {
            'name': self.proxy_le_service_name,
            'image': 'robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
            'constraints': ["node.role == manager"],
            'env': [
                "DF_PROXY_SERVICE_NAME=proxy_{}".format(self.test_name),
                "DF_SWARM_LISTENER_SERVICE_NAME=swarm_listener_{}".format(self.test_name),
                "CERTBOT_OPTIONS=--staging",
                "LOG=debug",
            ],
            'labels': {
                "com.df.notify": "true",
                "com.df.distribute": "true",
                "com.df.servicePath": "/.well-known/acme-challenge",
                "com.df.port": "8080",
            },
            'networks': [self.network_name]
        }

        self.dfple_service = self.docker_client.services.create(**dfple_service)
        self.services.append(self.dfple_service)

        # wait until proxy_le service has registered routes
        proxy_le_present_in_config = self.wait_until_found_in_config([self.proxy_le_service_name])
        if not proxy_le_present_in_config:
            self.get_service_logs(self.proxy_le_service_name)

        self.assertTrue(proxy_le_present_in_config,
            "docker-flow-proxy-letsencrypt service not registered.")


class DFPLEChallengeDNS(DFPLETestCase, Scenario):


    def setUp(self):

        super(DFPLEChallengeDNS, self).setUp()

        # docker-flow-proxy-letsencrypt service
        dfple_image = self.docker_client.images.build(
            path=os.path.dirname(os.path.abspath(__file__)),
            tag='robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
            quiet=False)
        dfple_service = {
            'name': self.proxy_le_service_name,
            'image': 'robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
            'constraints': ["node.role == manager"],
            'env': [
                "DF_PROXY_SERVICE_NAME=proxy_{}".format(self.test_name),
                "DF_SWARM_LISTENER_SERVICE_NAME=swarm_listener_{}".format(self.test_name),
                "CERTBOT_OPTIONS=--staging",
                "LOG=debug",
                "CERTBOT_CHALLENGE=dns",
                "CERTBOT_MANUAL_AUTH_HOOK=/app/hooks/ovh/manual-auth-hook.sh",
                "CERTBOT_MANUAL_CLEANUP_HOOK=/app/hooks/ovh/manual-cleanup-hook.sh",
                "OVH_DNS_ZONE=nibor.me",
                "OVH_APPLICATION_KEY={}".format(os.environ.get('OVH_APPLICATION_KEY')),
                "OVH_APPLICATION_SECRET={}".format(os.environ.get('OVH_APPLICATION_SECRET')),
                "OVH_CONSUMER_KEY={}".format(os.environ.get('OVH_CONSUMER_KEY')),
            ],
            'networks': [self.network_name]
        }

        self.dfple_service = self.docker_client.services.create(**dfple_service)
        self.services.append(self.dfple_service)


class DFPLESecret(DFPLETestCase, Scenario):


    def setUp(self):

        super(DFPLESecret, self).setUp()

        # docker-flow-proxy-letsencrypt service
        dfple_image = self.docker_client.images.build(
            path=os.path.dirname(os.path.abspath(__file__)),
            tag='robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
            quiet=False)
        dfple_service = {
            'name': self.proxy_le_service_name,
            'image': 'robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
            'constraints': ["node.role == manager"],
            'env': [
                "DF_PROXY_SERVICE_NAME=proxy_{}".format(self.test_name),
                "DF_SWARM_LISTENER_SERVICE_NAME=swarm_listener_{}".format(self.test_name),
                "CERTBOT_OPTIONS=--staging",
                "LOG=debug",
            ],
            'labels': {
                "com.df.notify": "true",
                "com.df.distribute": "true",
                "com.df.servicePath": "/.well-known/acme-challenge",
                "com.df.port": "8080",
            },
            'networks': [self.network_name],
            'mounts': ['/var/run/docker.sock:/var/run/docker.sock:rw'],
        }

        self.dfple_service = self.docker_client.services.create(**dfple_service)
        self.services.append(self.dfple_service)

        # wait until proxy_le service has registered routes
        proxy_le_present_in_config = self.wait_until_found_in_config([self.proxy_le_service_name])
        if not proxy_le_present_in_config:
            self.get_service_logs(self.proxy_le_service_name)

        self.assertTrue(
            proxy_le_present_in_config,
            "docker-flow-proxy-letsencrypt service not registered.")

    def test_basic(self):

        super(DFPLESecret, self).test_basic()

        # check secrets
        service = self.docker_client.services.get(self.dfp_service.id)
        secret_aliases = [x['File']['Name'] for x in service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Secrets']]
        self.assertIn('cert-{}.{}'.format(self.test_name, self.base_domain), secret_aliases)
        self.assertIn('cert-{}2.{}'.format(self.test_name, self.base_domain), secret_aliases)


class DFPLEUpdate(DFPLETestCase, Scenario):


    def setUp(self):

        super(DFPLEUpdate, self).setUp()

        # docker-flow-proxy-letsencrypt service
        dfple_image = self.docker_client.images.build(
            path=os.path.dirname(os.path.abspath(__file__)),
            tag='robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
            quiet=False)
        dfple_service = {
            'name': self.proxy_le_service_name,
            'image': 'robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
            'constraints': ["node.role == manager"],
            'env': [
                "DF_PROXY_SERVICE_NAME=proxy_{}".format(self.test_name),
                "DF_SWARM_LISTENER_SERVICE_NAME=swarm_listener_{}".format(self.test_name),
                "CERTBOT_OPTIONS=--staging",
                "LOG=debug",
            ],
            'labels': {
                "com.df.notify": "true",
                "com.df.distribute": "true",
                "com.df.servicePath": "/.well-known/acme-challenge",
                "com.df.port": "8080",
            },
            'networks': [self.network_name],
            'mounts': ['/var/run/docker.sock:/var/run/docker.sock:rw'],
        }

        self.dfple_service = self.docker_client.services.create(**dfple_service)
        self.services.append(self.dfple_service)

        # wait until proxy_le service has registered routes
        proxy_le_present_in_config = self.wait_until_found_in_config([self.proxy_le_service_name])
        if not proxy_le_present_in_config:
            self.get_service_logs(self.proxy_le_service_name)

        self.assertTrue(
            proxy_le_present_in_config,
            "docker-flow-proxy-letsencrypt service not registered.")

    def test_basic(self):

        super(DFPLEUpdate, self).test_basic()

        # check secrets
        service = self.docker_client.services.get(self.dfp_service.id)
        secrets = [x for x in service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Secrets']]
        secret_aliases = [x['File']['Name'] for x in service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Secrets']]
        self.assertIn('cert-{}.{}'.format(self.test_name, self.base_domain), secret_aliases)
        self.assertIn('cert-{}2.{}'.format(self.test_name, self.base_domain), secret_aliases)

        ref_secret = [ x for x in secrets if x['File']['Name'] == 'cert-{}.{}'.format(self.test_name, self.base_domain)]

        # revoke certs
        #   - get dfple container
        container = self.docker_client.containers.list(filters={'name': self.proxy_le_service_name})
        if len(container):
            container = container[0]
        else:
            raise Exception('Unable to get proxy le container')

        # print(container.exec_run("rm /etc/letsencrypt/live/{}/cert.pem".format('{}.{}'.format(self.test_name, self.base_domain))))
        print(container.exec_run("certbot revoke --cert-path /etc/letsencrypt/live/{}/cert.pem --staging".format(
            "{0}.{1}".format(self.test_name, self.base_domain))))

        print(container.exec_run("rm /etc/letsencrypt/live/{}/combined.pem".format(
            "{0}.{1}".format(self.test_name, self.base_domain))))

        time.sleep(10)

        print(container.exec_run("certbot delete --cert-name {} --staging".format(
            "{0}.{1}".format(self.test_name, self.base_domain))))

        print(container.exec_run("cat /var/log/letsencrypt/letsencrypt.log"))

        # print(container.exec_run("certbot revoke --cert-path /etc/letsencrypt/live/{}/cert.pem --cert-path /etc/letsencrypt/live/{}/cert.pem".format(
        #     "{0}.{1}".format(self.test_name, self.base_domain),
        #     "{0}2.{1}".format(self.test_name, self.base_domain))))

        # trigger a update request
        print('Triggering an update request')
        requests.get('http://{}:8081/v1/docker-flow-swarm-listener/notify-services'.format(self.base_domain), timeout=3).text

        # wait until dfp restart with new certs.
        time.sleep(30)

        texts = [
            'bind *:443 ssl crt-list /cfg/crt-list.txt'.format(self.test_name, self.base_domain)
        ]

        self.assertTrue(self.wait_until_found_in_config(texts))

        service = self.docker_client.services.get(self.dfp_service.id)
        secrets = [x for x in service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Secrets']]
        new_ref = [ x for x in secrets if x['File']['Name'] == 'cert-{}.{}'.format(self.test_name, self.base_domain)]
        self.assertNotEqual(new_ref, ref_secret)