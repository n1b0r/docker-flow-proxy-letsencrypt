import docker
import os
import time
import requests

from unittest import TestCase

class DFPLETestCase(TestCase):
	"""
	Original DFPLE implementation rely on DFP /put request to update certs.
	"""

	def setUp(self):
		"""
		Setup the needed environment:
		  * DFP + DFPLE
		  * client service requesting certificates
		"""
		time.sleep(5)
		self.test_name = os.environ.get('CI_BUILD_REF_SLUG', 'test')
		self.docker_client = docker.DockerClient(
			base_url='unix://var/run/docker.sock')

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
				"SERVICE_NAME=proxy_{}".format(self.test_name) ],
			'networks': [self.network_name]
		}

		# docker-flow-swarm-listener service
		# dfsl_image = self.docker_client.images.pull('vfarcic/docker-flow-swarm-listener')
		dfsl_service = {
			'name': 'swarm_listener_{}'.format(self.test_name),
			'image': 'vfarcic/docker-flow-swarm-listener',
			'constraints': ["node.role == manager"],
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

	def config_match(self, text):
		try:
			conf = requests.get('http://localhost:8080/v1/docker-flow-proxy/config', timeout=3).text
			print('CONF', conf)
			return text in conf
		except Exception, e:
			print('Error while getting config: {}'.format(e))
			return False

	def wait_until_found_in_config(self, text, timeout=30):

		_start = time.time()
		_current = time.time()
		while _current < _start + timeout:
			print('<< while', _current)
			if self.config_match(text):
				print('<< found')
				return True
			time.sleep(1)
			_current = time.time()

		print('OUT OF TIME')
		return False


class Scenario():

	def test_one_domain(self):

		# start the testing service
		test_service = {
			'name': 'test_service_{}'.format(self.test_name),
			'image': 'jwilder/whoami',
			'labels': {
		        "com.df.notify": "true",
		        "com.df.distribute": "true",
		        "com.df.serviceDomain": "{}.ks2.nibor.me".format(self.test_name),
		        "com.df.letsencrypt.host": "{}.ks2.nibor.me".format(self.test_name),
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
			self.wait_until_found_in_config('test_service_{}'.format(self.test_name)),
			"test service not registered.")

		# check cert is used
		self.assertTrue(
			self.wait_until_found_in_config('ssl crt /certs/{}.ks2.nibor.me.pem'.format(self.test_name)))

	def test_multiple_domains(self):

		# start the testing service
		test_service = {
			'name': 'test_service_{}'.format(self.test_name),
			'image': 'jwilder/whoami',
			'labels': {
		        "com.df.notify": "true",
		        "com.df.distribute": "true",
		        "com.df.serviceDomain": "{0}.ks2.nibor.me,{0}2.ks2.nibor.me".format(self.test_name),
		        "com.df.letsencrypt.host": "{0}.ks2.nibor.me,{0}2.ks2.nibor.me".format(self.test_name),
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
			self.wait_until_found_in_config('test_service_{}'.format(self.test_name)),
			"test service not registered.")

		# check certs are used
		certs_path = "/certs"
		if isinstance(self, DFPLESecret):
			certs_path = "/run/secrets"


		print('WAINTING FOR', 'ssl crt {1}/{0}.ks2.nibor.me.pem crt {1}/{0}2.ks2.nibor.me.pem'.format(self.test_name, certs_path))
		self.assertTrue(
			self.wait_until_found_in_config('ssl crt {1}/{0}.ks2.nibor.me.pem crt {1}/{0}2.ks2.nibor.me.pem'.format(self.test_name, certs_path)))


class DFPLEOriginal(DFPLETestCase, Scenario):


	def setUp(self):

		super(DFPLEOriginal, self).setUp()

		# docker-flow-proxy-letsencrypt service
		dfple_image = self.docker_client.images.build(
			path=os.path.dirname(os.path.abspath(__file__)),
			tag='robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
			quiet=False)
		dfple_service = {
			'name': 'proxy_le_{}'.format(self.test_name),
			'image': 'robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
			'constraints': ["node.role == manager"],
			'env': [
      			"DF_PROXY_SERVICE_NAME=proxy_{}".format(self.test_name),
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
		self.assertTrue(
			self.wait_until_found_in_config('proxy_le_{}'.format(self.test_name)),
			"docker-flow-proxy-letsencrypt service not registered.")


class DFPLESecret(DFPLETestCase, Scenario):


	def setUp(self):

		super(DFPLESecret, self).setUp()

		# docker-flow-proxy-letsencrypt service
		dfple_image = self.docker_client.images.build(
			path=os.path.dirname(os.path.abspath(__file__)),
			tag='robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
			quiet=False)
		dfple_service = {
			'name': 'proxy_le_{}'.format(self.test_name),
			'image': 'robin/docker-flow-proxy-letsencrypt:{}'.format(self.test_name),
			'constraints': ["node.role == manager"],
			'env': [
      			"DF_PROXY_SERVICE_NAME=proxy_{}".format(self.test_name),
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
		self.assertTrue(
			self.wait_until_found_in_config('proxy_le_{}'.format(self.test_name)),
			"docker-flow-proxy-letsencrypt service not registered.")

	def test_one_domain(self):

		super(DFPLESecret, self).test_one_domain()

		# check secrets
		secret_aliases = [x['File']['Name'] for x in self.dfple_service.attrs['TaskTemplate']['ContainerSpec']['Secrets']]
		self.assertIn('cert-{}.ks2.nibor.me.pem'.format(self.test_name), secret_aliases)