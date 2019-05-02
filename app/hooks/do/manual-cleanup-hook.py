#!/usr/bin/python
import os
import digitalocean
import requests
import time
import pip
import tldextract

CERTBOT_DOMAIN = os.environ.get('CERTBOT_DOMAIN')
CERTBOT_VALIDATION = os.environ.get('CERTBOT_VALIDATION')
CERTBOT_TOKEN = os.environ.get('CERTBOT_TOKEN')

DO_API_KEY = os.environ.get('DO_API_KEY')

headers = {'Authorization': 'Bearer {}'.format(DO_API_KEY)}

extracted = tldextract.extract(CERTBOT_DOMAIN)

domain = digitalocean.Domain(token=DO_API_KEY,name=extracted.registered_domain)

records = domain.get_records()

for record in records:
   if record.name == extracted.subdomain:
       matching = record
       break

if record:
    url = 'https://api.digitalocean.com/v2/domains/{}/records/{}'.format(extracted.registered_domain, record.id)
    response = requests.delete( url, headers=headers)
    print "Record deleted: {}".format(response)
else:
    print "Record not found."
