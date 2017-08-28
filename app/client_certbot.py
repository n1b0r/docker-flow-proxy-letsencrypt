import subprocess

import logging
logger = logging.getLogger('letsencrypt')


class CertbotClient():
    def __init__(self, challenge, webroot_path=None, options=None):
        self.challenge = challenge
        self.webroot_path = webroot_path
        self.options = options

    def run(self, cmd):
        # cmd = cmd.split()
        logger.debug('executing cmd : {}'.format(cmd))
        process = subprocess.Popen(cmd,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        output, error = process.communicate()
        logger.debug("o: {}".format(output))
        if error:
            logger.debug(error)
        logger.debug("r: {}".format(process.returncode))

        return output, error, process.returncode

    def update_cert(self, domains, email):
        """
        Update certifacts
        """

        c = ''
        if self.challenge == 'webroot':
        	c = "--webroot --webroot-path {}".format(self.webroot_path)

        output, error, code = self.run("""certbot certonly \
                    --agree-tos \
                    --domains {domains} \
                    --email {email} \
                    --expand \
                    --noninteractive \
                    {challenge}
                    --debug \
                    {options}""".format(
                        domains=','.join(domains),
                        email=email,
                        webroot_path=self.webroot_path,
                        options=self.options,
                        challenge=c).split())

        ret_error = False
        ret_created = True

        if b'urn:acme:error:unauthorized' in error:
            logger.error('Error during ACME challenge, is the domain name associated with the right IP ?')
            ret_error = True
            ret_created = False

        if b'no action taken.' in output:
            logger.debug('Nothing to do. Skipping.')
            ret_created = False

        if code != 0:
            logger.error('Certbot return code: {}. Skipping'.format(code))
            ret_error = True
            ret_created = False

        return ret_error, ret_created
