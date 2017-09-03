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
		http-01 challenge for site.domain.com
		Using the webroot path /opt/www for all unmatched domains.
		Waiting for verification...
		Cleaning up challenges

		IMPORTANT NOTES:
		 - Congratulations! Your certificate and chain have been saved at
		   /etc/letsencrypt/live/site.domain.com/fullchain.pem. Your
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


class VolumeTestCase(DFPLEClientTestCase):

	def setUp(self):
		DFPLEClientTestCase.setUp(self)

		self.domains = ['site.domain.com']
		self.email = 'email@domail.com'
		self.client_attrs = {
			'certbot_path': self.certbot_path,
			'certbot_challenge': 'http',
			'certbot_webroot_path': '/tmp',
			'domains': self.domains,
			'email': self.email,
		}


	def test(self):
		"""
		initial context:
		  * no certs, volume empty
		"""

		# create the client
		self.client = DFPLEClient(**self.client_attrs)

		# check certs do not exist
		certs = self.client.certs(self.domains)
		for d in self.domains:
			self.assertFalse(any(['{}.pem'.format(d) in x for x in certs[d]]))

		with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock(self.domains, CERTBOT_OUTPUT['ok'], '', 0)), \
			patch.object(self.client.dfp_client, 'put', lambda url, data=None, headers=None: None):
			self.client.process(self.domains, self.email)

		# check certs exist
		certs = self.client.certs(self.domains)
		for d in self.domains:
			self.assertTrue(any(['{}.pem'.format(d) in x for x in certs[d]]))

	def test_certbot_not_ok(self):
		"""
		initial context:
		  * no certs, volume empty
		"""

		# create the client
		self.client = DFPLEClient(**self.client_attrs)

		# check certs do not exist
		certs = self.client.certs(self.domains)
		for d in self.domains:
			self.assertFalse(any(['{}.pem'.format(d) in x for x in certs[d]]))

		error_occured = False
		with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock(self.domains, '', '', 1)), \
			patch.object(self.client.dfp_client, 'put', lambda url, data=None, headers=None: None):

			try:
				self.client.process()
			except:
				error_occured = True

		self.assertTrue(error_occured)



class SecretsTestCase(DFPLEClientTestCase):

	def setUp(self):
		DFPLEClientTestCase.setUp(self)

		self.domains = ['site.domain.com']
		self.email = 'email@domail.com'
		self.client_attrs = {
			'certbot_path': self.certbot_path,
			'certbot_challenge': 'http',
			'certbot_webroot_path': '/tmp',
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

		# create the client
		self.client = DFPLEClient(**self.client_attrs)

		with patch('client_dfple.DFPLEClient.secrets', return_value=mocked_data['secrets_initial']), \
			patch('client_dfple.DFPLEClient.secret_create', return_value=mocked_data['secret_created']), \
			patch('client_dfple.DFPLEClient.service_update_secrets', return_value=None), \
			patch('client_dfple.DFPLEClient.services', return_value=[mocked_data['service_dfp']]), \
			patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock(self.domains, CERTBOT_OUTPUT['ok'], '', 0)):

			certs = self.client.certs(self.domains)
			secrets = self.client.secrets()
			dfp_secrets = self.client.service_get_secrets(self.client.services(self.client.dfp_service_name)[0])

			# check certs do not exist
			for d in self.domains:
				self.assertFalse(any(['{}.pem'.format(d) in x for x in certs[d]]))

			# check secrets not found and not attached
			for d in self.domains:
				self.assertFalse(any([d in x.name for x in secrets]))
				self.assertFalse(any([d == x['SecretName'] for x in dfp_secrets]))

			self.client.process(self.domains, self.email)

			# check certs exist
			certs = self.client.certs(self.domains)
			for d in self.domains:
				self.assertTrue(any(['{}.pem'.format(d) in x for x in certs[d]]))

			# check secrets found and attached
			for d in self.domains:
				self.assertTrue(any([d in x.name for x in self.client._secrets]))
				self.assertTrue(any([d == x['SecretName'] for x in self.client.dfp_secrets]))


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

		# create the client
		self.client = DFPLEClient(**self.client_attrs)

		with patch('client_dfple.DFPLEClient.secrets', return_value=mocked_data['secrets_initial']), \
			patch('client_dfple.DFPLEClient.secret_create', return_value=mocked_data['secret_created']), \
			patch('client_dfple.DFPLEClient.service_update_secrets', return_value=None), \
			patch('client_dfple.DFPLEClient.services', return_value=[mocked_data['service_dfp']]):

			# initialize context - create certs files.
			self.letsencrypt_mock(self.domains, None, None, None, tmp_files=['privkey.pem', 'fullchain.pem', 'combined.pem'])

			certs = self.client.certs(self.domains)
			secrets = self.client.secrets()
			dfp_secrets = self.client.service_get_secrets(self.client.services(self.client.dfp_service_name)[0])

			# check certs exist
			for d in self.domains:
				self.assertTrue(any(['{}.pem'.format(d) in x for x in certs[d]]))

			# check secrets not found and not attached
			for d in self.domains:
				self.assertFalse(any([d in x.name for x in secrets]))
				self.assertFalse(any([d == x['SecretName'] for x in dfp_secrets]))

			with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock([], CERTBOT_OUTPUT['null'], '', 0)):
				self.client.process(self.domains, self.email)

			# check certs exist
			certs = self.client.certs(self.domains)
			for d in self.domains:
				self.assertTrue(any(['{}.pem'.format(d) in x for x in certs[d]]))

			# check secrets found and attached
			for d in self.domains:
				self.assertTrue(any([d in x.name for x in self.client._secrets]), '{} not found in {}'.format(d, [x.name for x in self.client._secrets]))
				self.assertTrue(any([d == x['SecretName'] for x in self.client.dfp_secrets]))


	def test_secret_created_not_attached(self):
		"""
		initial context:
		  * certs are already present in certbot volume
		  * secrets are existing in the swarm
		  * proxy stack has been redeployed, secret needs to be attached
		"""
		mocked_data = {
			'service_dfp': docker.models.services.Service(
				attrs={'Spec': {'Name': 'proxy', 'TaskTemplate': {'ContainerSpec': {'Image': '', 'Secrets': []}}, 'Networks': [],}}
			),
			'secrets_initial': [docker.models.secrets.Secret(attrs={'Spec': {'Name': '{}.pem'.format(self.domains[0]), 'File': {'Name': 'cert-{}'.format(self.domains[0])}}})]
		}

		# create the client
		self.client = DFPLEClient(**self.client_attrs)

		with patch('client_dfple.DFPLEClient.secrets', return_value=mocked_data['secrets_initial']), \
			patch('client_dfple.DFPLEClient.service_update_secrets', return_value=None), \
			patch('client_dfple.DFPLEClient.services', return_value=[mocked_data['service_dfp']]):

			# initialize context - create certs files.
			self.letsencrypt_mock(self.domains, None, None, None, tmp_files=['privkey.pem', 'fullchain.pem', 'combined.pem'])

			certs = self.client.certs(self.domains)
			secrets = self.client.secrets()
			dfp_secrets = self.client.service_get_secrets(self.client.services(self.client.dfp_service_name)[0])

			# check certs exist
			for d in self.domains:
				self.assertTrue(any(['{}.pem'.format(d) in x for x in certs[d]]))

			# check secrets found and not attached
			for d in self.domains:
				self.assertTrue(any([d in x.name for x in secrets]))
				self.assertFalse(any([d == x['SecretName'] for x in dfp_secrets]))

			with patch.object(self.client.certbot, 'run', lambda cmd: self.letsencrypt_mock([], CERTBOT_OUTPUT['null'], '', 0)):
				self.client.process(self.domains, self.email)

			# check certs exist
			certs = self.client.certs(self.domains)
			for d in self.domains:
				self.assertTrue(any(['{}.pem'.format(d) in x for x in certs[d]]))

			# check secrets found and attached
			for d in self.domains:
				self.assertTrue(any([d in x.name for x in self.client._secrets]))
				print('ee', self.client.dfp_secrets)
				self.assertTrue(any(['{}.pem'.format(d) == x['SecretName'] for x in self.client.dfp_secrets]))