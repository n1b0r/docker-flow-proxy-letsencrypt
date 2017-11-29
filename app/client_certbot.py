import subprocess

import logging
logger = logging.getLogger('letsencrypt')


class CertbotClient():
    def __init__(self, **kwargs):
        self.challenge = kwargs.get('challenge')
        self.webroot_path = kwargs.get('webroot_path')
        self.manual_auth_hook = kwargs.get('manual_auth_hook')
        self.manual_cleanup_hook = kwargs.get('manual_cleanup_hook')
        self.options = kwargs.get('options')

        if self.challenge not in ("http", "dns"):
            raise Exception('required argument "challenge" not set.')
        if self.challenge == "http" and self.webroot_path is None:
            raise Exception('required argument "webroot_path" not set. Required when using challenge "http"')
        if self.challenge == "dns" and (self.manual_auth_hook is None or self.manual_cleanup_hook is None):
            raise Exception('required argument "manual_auth_hook" or "manual_manual_hook" not set. Required when using challenge "dns"')


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

    def update_cert(self, domains, email, testing=None):
        """
        Update certificates
        """

        c = ''
        if self.challenge == 'http':
            c = "--webroot --webroot-path {}".format(self.webroot_path)
        if self.challenge == 'dns':
            c = "--manual --manual-public-ip-logging-ok --preferred-challenges dns --manual-auth-hook {} --manual-cleanup-hook {}".format(self.manual_auth_hook, self.manual_cleanup_hook)

        # is testing, add staging flag
        if testing:
            if -1 == self.options.find('--staging'):
                self.options += ' --staging'
        elif False == testing:
            # is not testing, remove staging flag
            self.options = self.options.replace('--staging', '')
        # else don't do anything, because label was not set - use glboal settings


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
