#!/usr/bin/python
import os
import ovh


CERTBOT_DOMAIN = os.environ.get('CERTBOT_DOMAIN')
CERTBOT_VALIDATION = os.environ.get('CERTBOT_VALIDATION')
CERTBOT_TOKEN = os.environ.get('CERTBOT_TOKEN')

OVH_DNS_ZONE = os.environ.get('OVH_DNS_ZONE', 'nibor.me')
OVH_APPLICATION_KEY = os.environ.get('OVH_APPLICATION_KEY')
OVH_APPLICATION_SECRET = os.environ.get('OVH_APPLICATION_SECRET')
OVH_CONSUMER_KEY = os.environ.get('OVH_CONSUMER_KEY')

client = ovh.Client(
    endpoint='ovh-eu',
    application_key=OVH_APPLICATION_KEY,
    application_secret=OVH_APPLICATION_SECRET,
    consumer_key=OVH_CONSUMER_KEY,
)

# update the _acme-challenge. subdomain with a TXT record
subdomain = '_acme-challenge.{}'.format(CERTBOT_DOMAIN.replace(OVH_DNS_ZONE, ''))[:-1]
zones = client.get('/domain/zone/{}/record'.format(OVH_DNS_ZONE), fieldType='TXT', subDomain=subdomain)
print("zones", zones)
if len(zones) == 1:
	zone = zones[0]
else:
	raise Exception('Could not find domain matching: {}'.format(CERTBOT_DOMAIN))
response = client.delete('/domain/zone/{}/record/{}'.format(OVH_DNS_ZONE, zone))
print("Record deleted : {}".format(response))

response = client.post('/domain/zone/{}/refresh'.format(OVH_DNS_ZONE))
print("Zone refreshed : {}".format(response))
