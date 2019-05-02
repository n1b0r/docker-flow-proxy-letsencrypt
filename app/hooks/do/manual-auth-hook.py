#!/usr/bin/python
import os
import digitalocean
import time
import pip
import tldextract

CERTBOT_DOMAIN = os.environ.get('CERTBOT_DOMAIN')
CERTBOT_VALIDATION = os.environ.get('CERTBOT_VALIDATION')
CERTBOT_TOKEN = os.environ.get('CERTBOT_TOKEN')

DO_API_KEY = os.environ.get('DO_API_KEY')

extracted = tldextract.extract(CERTBOT_DOMAIN)

domain = digitalocean.Domain(token=DO_API_KEY,name=extracted.registered_domain)

# update the _acme-challenge. subdomain with a TXT record
subdomain = '_acme-challenge.{}'.format(extracted.subdomain)

print "Creating record: TXT {}".format(subdomain)

created = domain.create_new_domain_record(type='TXT',name=subdomain,data=CERTBOT_VALIDATION,ttl=300)

print "Record created: {}".format(created)

# sleep to make sure the change has time to propagate over to DNS
time.sleep(60)