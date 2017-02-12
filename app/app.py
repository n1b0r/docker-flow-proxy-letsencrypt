import logging
import os
import requests
import subprocess

from flask import Flask, request, send_from_directory

LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warning': logging.WARNING,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}

logging.basicConfig(level=LEVELS.get(os.environ.get('LOG', 'debug').lower()))
logger = logging.getLogger('letsencrypt')

DF_NOTIFY_CREATE_SERVICE_URL = os.environ.get('DF_NOTIFY_CREATE_SERVICE_URL')
CERTBOT_WEBROOT_PATH = os.environ.get('CERTBOT_WEBROOT_PATH', '/opt/www')
CERTBOT_OPTIONS = os.environ.get('CERTBOT_OPTIONS', '')
CERTBOT_LIVE_FOLDER = "/etc/letsencrypt/live/"


def run(cmd):
    logger.debug('executing cmd : {}'.format(cmd.split()))
    process = subprocess.Popen(cmd.split(),
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
    output, error = process.communicate()
    logger.debug("o {}".format(output))
    if error:
        logger.debug(error)
    logger.debug("r: {}".format(process.returncode))
    
    return output, error, process.returncode

def update_cert(domains, email):
    """
    Update certifacts
    """
    output, error, code = run("""certbot certonly \
                --agree-tos \
                --domains {domains} \
                --email {email} \
                --expand \
                --noninteractive \
                --webroot \
                --webroot-path {webroot_path} \
                --debug \
                {options}""".format(
                    domains=domains,
                    email=email,
                    webroot_path=CERTBOT_WEBROOT_PATH,
                    options=CERTBOT_OPTIONS))

    if b'urn:acme:error:unauthorized' in error:
        logger.error('Error during ACME challenge, is the domain name associated with the right IP ?')


    if error:
        return False

    return True
def is_letsencrypt_service(args):
    """ Check if given service has special args """

    found = True
    for label in ('letsencrypt.host', 'letsencrypt.email'):
        if label in args.keys():
            logger.debug('argument {} found : {}'.format(label, args.get(label)))
        else:
            found = False
            logger.debug('argument {} NOT found.'.format(label))

    return found

def forward_request_to_proxy(args):
    # transmit the request to docker-flow-proxy
    url = '{}?{}'.format(
        DF_NOTIFY_CREATE_SERVICE_URL,
        '&'.join(['{}={}'.format(k, v) for k, v in args.items()]))
    logger.debug('forwarding request to url {}'.format(url))
    try:
        response = requests.get(url)
        logger.debug('response: {} {}'.format(
            response.status_code, response.text))
    except requests.exceptions.ConnectionError as e:
        logger.error('invalid domain name.')
        raise e



app = Flask(__name__)

@app.route("/.well-known/acme-challenge/<path>")
def acme_challenge(path):
    return send_from_directory(CERTBOT_WEBROOT_PATH,
        ".well-known/acme-challenge/{}".format(path))

@app.route("/v1/docker-flow-proxy-letsencrypt/reconfigure")
def update():
    args = request.args
    logger.info('request for service: {}'.format(args.get('serviceName')))
    if is_letsencrypt_service(args):
        logger.info('letencrypt service detected.')

        domain = args.get('letsencrypt.host')
        email = args.get('letsencrypt.email')

        if update_cert(domain, email):
            logger.info('certificates successfully generated using certbot.')

            # 
            combined_path = os.path.join(CERTBOT_LIVE_FOLDER, "{}.pem".format(domain))
            # create combined cert.
            with open(combined_path, "w") as combined, \
                 open(os.path.join(CERTBOT_LIVE_FOLDER, domain, "privkey.pem"), "r") as priv, \
                 open(os.path.join(CERTBOT_LIVE_FOLDER, domain, "fullchain.pem"), "r") as fullchain:

                combined.write(fullchain.read())
                combined.write(priv.read())
                logger.info('combined certificate generated into "{}".'.format(combined_path))

    forward_request_to_proxy(args)
    return "OK {}".format(request.args)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True, threaded=True)