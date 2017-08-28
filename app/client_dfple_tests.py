import docker
import os
import shutil
from mock import patch
from unittest import TestCase

from client_dfple import DFPLEClient

import logging
logging.basicConfig(level=logging.ERROR, format="%(levelname)s;%(asctime)s;%(message)s")
logging.getLogger('letsencrypt').setLevel(logging.DEBUG)

CERTBOT_OUTPUT = {
	'null': """
		-------------------------------------------------------------------------------
		Certificate not yet due for renewal; no action taken.
		-------------------------------------------------------------------------------
	""",
	'ok': """
		Saving debug log to /var/log/letsencrypt/letsencrypt.log
		Obtaining a new certificate
		Performing the following challenges:
		http-01 challenge for sfsdfsfsffsd.ks2.nibor.me
		Using the webroot path /opt/www for all unmatched domains.
		Waiting for verification...
		Cleaning up challenges

		IMPORTANT NOTES:
		 - Congratulations! Your certificate and chain have been saved at
		   /etc/letsencrypt/live/sfsdfsfsffsd.ks2.nibor.me/fullchain.pem. Your
		   cert will expire on 2017-11-25. To obtain a new or tweaked version
		   of this certificate in the future, simply run certbot again. To
		   non-interactively renew *all* of your certificates, run "certbot
		   renew"
	"""
}


class DFPLEClientTestCase(TestCase):

	def setUp(self):
		self.certbot_path = '/tmp'
		tmp_path = os.path.join(self.certbot_path, 'live')
		if os.path.exists(tmp_path):
			shutil.rmtree(tmp_path)

	def letsencrypt_mock(self, domains, output, error, code, tmp_files=None):

		if tmp_files is None:
			tmp_files = ['privkey.pem', 'fullchain.pem']

		# create tmp directory
		self.tmp_dirs = domains
		for d in domains:
			base_path = os.path.join(self.certbot_path, 'live', d)
			os.makedirs(base_path)
			for x in tmp_files:
				open(os.path.join(base_path, x), 'a').close()

		return output, error, code

	# def test_generate_cert(self):
	# 	"""
	# 	"""
	# 	domains = ['site.domain.com']
	# 	with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock(domains, CERTBOT_OUTPUT['ok'], '', 0)), \
	# 		patch.object(self.client.dfp_client, 'put', lambda url, data=None, headers=None: None):

	# 		self.client.process(domains=domains, email='email@domain.com')

	# 		# check combined file exists
	# 		self.assertTrue(os.path.exists(os.path.join(self.certbot_path, 'live', domains[0], 'combined.pem')))

	# def test_rate_limits(self):
	# 	"""
	# 	"""
	# 	domains = ['site.domain.com']
	# 	with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock(domains, '', '', 1)):
	# 		self.assertFalse(self.client.process(domains=domains, email='email@domain.com'))


	# def test_secret_fresh_install(self):
	# 	"""
	# 	"""
	# 	domains = ['site.domain.com']
	# 	self.client = DFPLEClient(
	# 		certbot_path=self.certbot_path,
	# 		docker_client=docker.DockerClient(version='1.25'),
	# 		dfp_service_name='proxy')

	# 	# service DFP is present with no secrets
	# 	mocked_docker_services_list = [
	# 		docker.models.services.Service(
	# 			attrs={
	# 				'Spec': {
	# 					'Name': 'proxy',
	# 					'TaskTemplate': {'ContainerSpec': {'Image': ''}},
	# 					'Networks': [],
	# 				}
	# 			})
	# 	]
	# 	mocked_docker_secrets_list = [
	# 		docker.models.secrets.Secret(attrs={'Spec': {'Name': 'proxy', 'TaskTemplate': {'ContainerSpec': {}}}})
	# 	]
	# 	mocked_docker_secrets_create = docker.models.secrets.Secret(attrs={'Spec': {'Name': 'toto'}})
	# 	mocked_docker_secrets_get = docker.models.secrets.Secret(attrs={})

	# 	with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock(domains, CERTBOT_OUTPUT['ok'], '', 0)), \
	# 		patch('client_dfple.DFPLEClient.secret_combined_found', return_value=False), \
	# 		patch('client_dfple.DFPLEClient.secret_create', return_value=mocked_docker_secrets_create), \
	# 		patch('docker.models.services.ServiceCollection.list', return_value=mocked_docker_services_list), \
	# 		patch('docker.models.services.Service.update', return_value=None), \
	# 		patch('docker.models.secrets.SecretCollection.list', return_value=mocked_docker_secrets_list), \
	# 		patch('docker.models.secrets.SecretCollection.get', return_value=mocked_docker_secrets_get):#, \
	# 		# patch('docker.models.secrets.SecretCollection.create', return_value=mocked_docker_secrets_create):

	# 		self.client.process(domains=domains, email='email@domain.com')

	# 		# check combined file exists
	# 		self.assertTrue(os.path.exists(os.path.join(self.certbot_path, 'live', domains[0], 'combined.pem')))

	# def test_secret_fresh_install(self):
	# 	"""
	# 	"""
	# 	domains = ['site.domain.com']
	# 	self.client = DFPLEClient(
	# 		certbot_path=self.certbot_path,
	# 		docker_client=docker.DockerClient(),
	# 		dfp_service_name='proxy')

	# 	mocked_data = {
	# 		'service_dfp': docker.models.services.Service(
	# 			attrs={
	# 				'Spec': {
	# 					'Name': 'proxy',
	# 					'TaskTemplate': {'ContainerSpec': {'Image': ''}},
	# 					'Networks': [],
	# 				}
	# 			}
	# 		),
	# 		'secrets': {
	# 			domains[0]: docker.models.secrets.Secret(attrs={'Spec': {'Name': ''}})
	# 		},
	# 		'secret_combined_found': False,
	# 	}



	# 	# mocked_docker_services_list = [
	# 	# 	docker.models.services.Service(
	# 	# 		attrs={
	# 	# 			'Spec': {
	# 	# 				'Name': 'proxy',
	# 	# 				'TaskTemplate': {'ContainerSpec': {'Image': ''}},
	# 	# 				'Networks': [],
	# 	# 			}
	# 	# 		})
	# 	# ]
	# 	# mocked_docker_secrets_list = [
	# 	# 	docker.models.secrets.Secret(attrs={'Spec': {'Name': 'proxy', 'TaskTemplate': {'ContainerSpec': {}}}})
	# 	# ]
	# 	# mocked_docker_secrets_create = docker.models.secrets.Secret(attrs={'Spec': {'Name': 'toto'}})
	# 	# mocked_docker_secrets_get = docker.models.secrets.Secret(attrs={})

	# 	with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock(domains, CERTBOT_OUTPUT['ok'], '', 0)), \
	# 		patch('client_dfple.DFPLEClient.secret_combined_found', return_value=mocked_data['secret_combined_found']), \
	# 		patch('client_dfple.DFPLEClient.secret_create', return_value=mocked_data['secrets'][domains[0]]), \
	# 		patch('client_dfple.DFPLEClient.service_dfp', return_value=mocked_data['service_dfp']), \
	# 		patch('docker.models.services.Service.update', return_value=None):#, \
	# 		# patch('docker.models.services.ServiceCollection.list', return_value=mocked_docker_services_list), \
	# 		# patch('docker.models.secrets.SecretCollection.list', return_value=mocked_docker_secrets_list), \
	# 		# patch('docker.models.secrets.SecretCollection.get', return_value=mocked_docker_secrets_get):#, \
	# 		# patch('docker.models.secrets.SecretCollection.create', return_value=mocked_docker_secrets_create):

	# 		self.client.process(domains=domains, email='email@domain.com')

	# 		# check combined file exists
	# 		self.assertTrue(os.path.exists(os.path.join(self.certbot_path, 'live', domains[0], 'combined.pem')))

class VolumeTestCase(DFPLEClientTestCase):

	def setUp(self):
		DFPLEClientTestCase.setUp(self)

		self.domains = ['site.domain.com']
		self.email = 'email@domail.com'
		self.client_attrs = {
			'certbot_path': self.certbot_path,
			'domains': self.domains,
			'email': self.email,
		}


	def test(self):
		"""
		initial context:
		  * no certs, no secrets
		"""

		# create the client
		self.client = DFPLEClient(**self.client_attrs)

		# check certs do not exist
		for d in self.domains:
			self.assertFalse(any(['{}.pem'.format(d) in x for x in self.client.certs[d]]))

		with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock(self.domains, CERTBOT_OUTPUT['ok'], '', 0)), \
			patch.object(self.client.dfp_client, 'put', lambda url, data=None, headers=None: None):
			self.client.process()

		# check certs exist
		for d in self.domains:
			self.assertTrue(any(['{}.pem'.format(d) in x for x in self.client.certs[d]]))




class SecretsTestCase(DFPLEClientTestCase):

	def setUp(self):
		DFPLEClientTestCase.setUp(self)

		self.domains = ['site.domain.com']
		self.email = 'email@domail.com'
		self.client_attrs = {
			'certbot_path': self.certbot_path,
			'domains': self.domains,
			'email': self.email,
			'docker_client': docker.DockerClient(),
		}


	def test_secret(self):
		"""
		initial context:
		  * no certs, no secrets
		"""
		mocked_data = {
			'service_dfp': docker.models.services.Service(
				attrs={'Spec': {'Name': 'proxy', 'TaskTemplate': {'ContainerSpec': {'Image': '', 'Secrets': []}}, 'Networks': [],}}
			),
			'secret_created': docker.models.secrets.Secret(attrs={'Spec': {'Name': self.domains[0]}}),
			'secrets_initial': []
		}

		with patch('client_dfple.DFPLEClient.secret_create', return_value=mocked_data['secret_created']), \
			patch('client_dfple.DFPLEClient.service_dfp', return_value=mocked_data['service_dfp']), \
			patch('client_dfple.DFPLEClient.service_update_secrets', return_value=None), \
			patch('docker.models.secrets.SecretCollection.list', return_value=[]):

			# create the client
			self.client = DFPLEClient(**self.client_attrs)

			# check certs do not exist
			for d in self.domains:
				self.assertFalse(any(['{}.pem'.format(d) in x for x in self.client.certs[d]]))

			# check secrets not found and not attached
			for d in self.domains:
				self.assertNotIn(d, self.client.secrets)
				self.assertNotIn(d, self.client.secrets_dfp)

			with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock(self.domains, CERTBOT_OUTPUT['ok'], '', 0)):
				self.client.process()

			# check secrets found and attached
			for d in self.domains:
				self.assertTrue(any([d in x.name for x in self.client.secrets]))
				self.assertTrue(any([d == x['SecretName'] for x in self.client.secrets_dfp]))

	def test_secret_not_created_not_attached(self):
		"""
		initial context:
		  * the whole process has already been done once
		  * certs are already present in certbot volume
		  * swarm has been destroyed and re-initialized
		"""
		mocked_data = {
			'service_dfp': docker.models.services.Service(
				attrs={'Spec': {'Name': 'proxy', 'TaskTemplate': {'ContainerSpec': {'Image': '', 'Secrets': []}}, 'Networks': [],}}
			),
			'secret_created': docker.models.secrets.Secret(attrs={'Spec': {'Name': self.domains[0]}}),
			'secrets_initial': []
		}

		with patch('client_dfple.DFPLEClient.secret_create', return_value=mocked_data['secret_created']), \
			patch('client_dfple.DFPLEClient.service_dfp', return_value=mocked_data['service_dfp']), \
			patch('client_dfple.DFPLEClient.service_update_secrets', return_value=None), \
			patch('docker.models.secrets.SecretCollection.list', return_value=[]):

			# initialize context - create certs files.
			self.letsencrypt_mock(self.domains, None, None, None, tmp_files=['privkey.pem', 'fullchain.pem', 'combined.pem'])

			# create the client
			self.client = DFPLEClient(**self.client_attrs)

			# check certs exist
			for d in self.domains:
				self.assertTrue(any(['{}.pem'.format(d) in x for x in self.client.certs[d]]))

			# check secrets not found and not attached
			for d in self.domains:
				self.assertNotIn(d, self.client.secrets)
				self.assertNotIn(d, self.client.secrets_dfp)

			with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock([], CERTBOT_OUTPUT['null'], '', 0)):
				self.client.process()

			# check secrets found and attached
			for d in self.domains:
				self.assertTrue(any([d in x.name for x in self.client.secrets]))
				self.assertTrue(any([d == x['SecretName'] for x in self.client.secrets_dfp]))





		# domains = ['site.domain.com']
		# self.client = DFPLEClient(
		# 	certbot_path=self.certbot_path,
		# 	docker_client=docker.DockerClient(version='1.25'),
		# 	dfp_service_name='proxy')

		# mocked_data = {
		# 	'service_dfp': docker.models.services.Service(
		# 		attrs={
		# 			'Spec': {
		# 				'Name': 'proxy',
		# 				'TaskTemplate': {
		# 					'ContainerSpec': {
		# 						'Image': '',
		# 						'Secrets': []}},
		# 				'Networks': [],
		# 			}
		# 		}
		# 	),
		# 	'secrets': {
		# 		domains[0]: docker.models.secrets.Secret(attrs={'Spec': {'Name': ''}})
		# 	},
		# 	'secret_combined_found': False,
		# }



		# # mocked_docker_services_list = [
		# # 	docker.models.services.Service(
		# # 		attrs={
		# # 			'Spec': {
		# # 				'Name': 'proxy',
		# # 				'TaskTemplate': {'ContainerSpec': {'Image': ''}},
		# # 				'Networks': [],
		# # 			}
		# # 		})
		# # ]
		# # mocked_docker_secrets_list = [
		# # 	docker.models.secrets.Secret(attrs={'Spec': {'Name': 'proxy', 'TaskTemplate': {'ContainerSpec': {}}}})
		# # ]
		# # mocked_docker_secrets_create = docker.models.secrets.Secret(attrs={'Spec': {'Name': 'toto'}})
		# # mocked_docker_secrets_get = docker.models.secrets.Secret(attrs={})

		# with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock(domains, CERTBOT_OUTPUT['null'], '', 0, tmp_files=['privkey.pem', 'fullchain.pem', 'combined.pem'])), \
		# 	patch('client_dfple.DFPLEClient.check_secret_combined_found', return_value=mocked_data['secret_combined_found']), \
		# 	patch('client_dfple.DFPLEClient.secret_create', return_value=mocked_data['secrets'][domains[0]]), \
		# 	patch('client_dfple.DFPLEClient.service_dfp', return_value=mocked_data['service_dfp']), \
		# 	patch('docker.models.services.Service.update', return_value=None):#, \
		# 	# patch('docker.models.services.ServiceCollection.list', return_value=mocked_docker_services_list), \
		# 	# patch('docker.models.secrets.SecretCollection.list', return_value=mocked_docker_secrets_list), \
		# 	# patch('docker.models.secrets.SecretCollection.get', return_value=mocked_docker_secrets_get):#, \
		# 	# patch('docker.models.secrets.SecretCollection.create', return_value=mocked_docker_secrets_create):





		# 	self.client.process(domains=domains, email='email@domain.com')

		# 	# # check combined file exists
		# 	# self.assertTrue(os.path.exists(os.path.join(self.certbot_path, 'live', domains[0], 'combined.pem')))

		# 	# check that the combined exists and it has not been created
		# 	self.assertTrue(self.client.cert_combined_exists)
		# 	self.assertFalse(self.client.cert_combined_created)

		# 	# check that the secret was not found
		# 	self.assertFalse(self.client.secret_combined_found)

		# 	# check that the secret was not attached
		# 	self.assertFalse(self.client.secret_combined_attached)
