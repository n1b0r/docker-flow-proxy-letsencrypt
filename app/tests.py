from unittest import TestCase
from app import DockerFlowProxyAPIClient
import requests_mock
import tempfile


class CertbotClientTest(TestCase):

    @requests_mock.mock()
    def test_put_certificate(self, adaptor):

        with tempfile.NamedTemporaryFile() as temp:
            temp.write('Some data')
            temp.flush()
            
            client = DockerFlowProxyAPIClient(
                'http://base_url:8080/v1/docker-flow-proxy',
                adaptor=adaptor)
            response = client.put_cert(temp.name)
            self.assertEqual(response, 'TOTO')