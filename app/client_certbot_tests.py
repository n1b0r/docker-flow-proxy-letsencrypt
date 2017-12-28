import docker
import os
import shutil
from mock import patch
from unittest import TestCase

from client_certbot import CertbotClient


class CertbotClientTestCase(TestCase):

	def test_staging_per_container(self):
		certbot_client = CertbotClient(challenge='http', webroot_path='/tmp')
		assert '--staging' in certbot_client.get_options(testing=True)
		certbot_client = CertbotClient(challenge='http', webroot_path='/tmp', options="--staging")
		assert '--staging' in certbot_client.get_options(testing=True)
		certbot_client = CertbotClient(challenge='http', webroot_path='/tmp')
		assert '--staging' not in certbot_client.get_options(testing=False)
		certbot_client = CertbotClient(challenge='http', webroot_path='/tmp', options="--staging")
		assert '--staging' not in certbot_client.get_options(testing=False)
		certbot_client = CertbotClient(challenge='http', webroot_path='/tmp', options="--staging")
		assert '--staging' in certbot_client.get_options(testing=None)
		certbot_client = CertbotClient(challenge='http', webroot_path='/tmp')
		assert '--staging' not in certbot_client.get_options(testing=None)
