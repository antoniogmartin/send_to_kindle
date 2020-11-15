import smtplib
import base64
import json
from optparse import OptionParser
try:
    from urllib.request import urlopen
    from urllib.parse import quote, unquote, urlencode
except ImportError:
    from urllib import urlopen, quote, unquote, urlencode

import sys
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
from os import listdir
from os.path import isfile, join, basename

MAX_SIZE = 25000000
incompatible_file = False
incompatible_format = ['.doc', '.docx', '.rtf', '.htm', '.html', '.txt', '.zip', '.mobi', '.jpg', '.gif', '.bmp',
                       '.png']

REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
# The URL root for accessing Google Accounts.
GOOGLE_ACCOUNTS_BASE_URL = 'https://accounts.google.com'

if hasattr(__builtins__, 'raw_input'):
    def input_str(prompt):
        return raw_input(prompt).decode(sys.stdin.encoding)
else:
    input_str = input

def UrlEscape(text):
    # See OAUTH 5.1 for a definition of which characters need to be escaped.
    return quote(text, safe='~-._')

def RefreshToken(client_id, client_secret, refresh_token):
    """Obtains a new token given a refresh token.

    See https://developers.google.com/accounts/docs/OAuth2InstalledApp#refresh

    Args:
      client_id: Client ID obtained by registering your app.
      client_secret: Client secret obtained by registering your app.
      refresh_token: A previously-obtained refresh token.
    Returns:
      The decoded response from the Google Accounts server, as a dict. Expected
      fields include 'access_token', 'expires_in', and 'refresh_token'.
    """
    params = {}
    params['client_id'] = client_id
    params['client_secret'] = client_secret
    params['refresh_token'] = refresh_token
    params['grant_type'] = 'refresh_token'
    request_url = AccountsUrl('o/oauth2/token')

    data = urlencode(params).encode('utf-8')

    response = urlopen(request_url, data).read()
    return json.loads(response.decode('utf-8'))

def AuthorizeTokens(client_id, client_secret, authorization_code):
    """Obtains OAuth access token and refresh token.

    This uses the application portion of the "OAuth2 for Installed Applications"
    flow at https://developers.google.com/accounts/docs/OAuth2InstalledApp#handlingtheresponse

    Args:
      client_id: Client ID obtained by registering your app.
      client_secret: Client secret obtained by registering your app.
      authorization_code: code generated by Google Accounts after user grants
          permission.
    Returns:
      The decoded response from the Google Accounts server, as a dict. Expected
      fields include 'access_token', 'expires_in', and 'refresh_token'.
    """
    params = {}
    params['client_id'] = client_id
    params['client_secret'] = client_secret
    params['code'] = authorization_code
    params['redirect_uri'] = REDIRECT_URI
    params['grant_type'] = 'authorization_code'
    request_url = AccountsUrl('o/oauth2/token')

    data = urlencode(params).encode('utf-8')

    response = urlopen(request_url, data).read()
    return json.loads(response.decode('utf-8'))

def RequireOptions(options, *args):
    missing = [arg for arg in args if getattr(options, arg) is None]
    if missing:
        print('Missing options: %s' % ' '.join(missing))
        sys.exit(-1)


def SmtpAuthentication(user, auth_string):
    """Authenticates to SMTP with the given auth_string.

    Args:
      user: The Gmail username (full email address)
      auth_string: A valid OAuth2 string, not base64-encoded, as returned by
          GenerateOAuth2String.
    """
    print()
    auth_bytes = auth_string.encode('utf-8')
    smtp_conn = smtplib.SMTP('smtp.gmail.com', 587)
    smtp_conn.set_debuglevel(True)
    smtp_conn.ehlo('test')
    smtp_conn.starttls()
    smtp_conn.docmd('AUTH', 'XOAUTH2 ' + base64.b64encode(auth_bytes).decode())


def AccountsUrl(command):
    """Generates the Google Accounts URL.

    Args:
      command: The command to execute.

    Returns:
      A URL for the given command.
    """
    return '%s/%s' % (GOOGLE_ACCOUNTS_BASE_URL, command)

def FormatUrlParams(params):
    """Formats parameters into a URL query string.

    Args:
      params: A key-value map.

    Returns:
      A URL query string version of the given parameters.
    """
    param_fragments = []
    for param in sorted(iter(params.items()), key=lambda x: x[0]):
        param_fragments.append('%s=%s' % (param[0], UrlEscape(param[1])))
    return '&'.join(param_fragments)

def GeneratePermissionUrl(client_id, scope='https://mail.google.com/'):
    """Generates the URL for authorizing access.

    This uses the "OAuth2 for Installed Applications" flow described at
    https://developers.google.com/accounts/docs/OAuth2InstalledApp

    Args:
      client_id: Client ID obtained by registering your app.
      scope: scope for access token, e.g. 'https://mail.google.com'
    Returns:
      A URL that the user should visit in their browser.
    """
    params = {}
    params['client_id'] = client_id
    params['redirect_uri'] = REDIRECT_URI
    params['scope'] = scope
    params['response_type'] = 'code'
    return '%s?%s' % (AccountsUrl('o/oauth2/auth'),
                      FormatUrlParams(params))

def GenerateOauth2Token(client_id,client_secret):
    print('To authorize token, visit this url and follow the directions:')
    print('  %s' % GeneratePermissionUrl(client_id))
    authorization_code = input_str('Enter verification code: ')
    response = AuthorizeTokens(client_id, client_secret,
                               authorization_code)
    print('Refresh Token: %s' % response['refresh_token'])
    print('Access Token: %s' % response['access_token'])
    print('Access Token Expiration Seconds: %s' % response['expires_in'])
    return response

def GenerateOAuth2String(username, access_token, base64_encode=True):
    """Generates an IMAP OAuth2 authentication string.

    See https://developers.google.com/google-apps/gmail/oauth2_overview

    Args:
      username: the username (email address) of the account to authenticate
      access_token: An OAuth2 access token.
      base64_encode: Whether to base64-encode the output.

    Returns:
      The SASL argument for the OAuth2 mechanism.
    """
    auth_string = 'user=%s\1auth=Bearer %s\1\1' % (username, access_token)
    if base64_encode:
        auth_bytes = auth_string.encode('utf-8')
        auth_string = base64.b64encode(auth_bytes).decode()
    return auth_string

def SetupOptionParser():
    # Usage message is the module's docstring.
    parser = OptionParser(usage=__doc__)
    parser.add_option('--client_id',
                      default=None,
                      help='Client ID of the application that is authenticating. '
                           'See OAuth2 documentation for details.')
    parser.add_option('--client_secret',
                      default=None,
                      help='Client secret of the application that is '
                           'authenticating. See OAuth2 documentation for '
                           'details.')
    parser.add_option('--access_token',
                      default=None,
                      help='OAuth2 access token')

    parser.add_option('--file_path',
                      default=None,
                      help='Docs file path.')
    parser.add_option('--refresh_token',
                      default=None,
                      help='OAuth2 refresh token')
    parser.add_option('--user',
                      default=None,
                      help='email address of user whose account is being '
                           'accessed')
    parser.add_option('--send_to',
                      default=None,
                      help='email address of user who will recive the email')
    parser.add_option('--quiet',
                      action='store_true',
                      default=False,
                      dest='quiet',
                      help='Omit verbose descriptions and only print '
                           'machine-readable outputs.')
    return parser


def CreateMsg(user,send_to,subject='Convertir'):
    msg = MIMEMultipart()
    msg['From'] = user
    msg['To'] = send_to
    msg['Subject'] = subject
    return msg
def SendToKindle(server,user,send_to,file_path):
    sum_size = 0
    incompatible_file=False
    files= [file_path + "/" + f for f in listdir(file_path) if
                 isfile(join(file_path, f)) and basename(f) != '.DS_Store']
    if len(files)>0:
        msg=CreateMsg(user,send_to)
        # check file format
        for f in files:
            file_name=basename(f)
            if any(x in file_name for x in incompatible_format):
                incompatible_file=True

            with open(f, "rb") as fil:
                if not incompatible_file:
                    if (file_name != '.DS_Store'):
                        file_stat = os.stat(f)
                        file_size = file_stat.st_size
                        acc_size= sum_size+file_size
                        if(acc_size <  MAX_SIZE):
                            sum_size += file_size
                        else:
                            acc_size= 0

                        # if it´s possible attach more files
                        if (sum_size < MAX_SIZE and file_size < MAX_SIZE):
                            part = MIMEApplication(fil.read(), Name=file_name)
                            part['Content-Disposition'] = 'attachment; filename="%s"' % file_name
                            msg.attach(part)
                            print(f, " ", file_size / 1000000, " ", sum_size / 1000000)

                        ## new mail because sum of sizes is greater than attachment max size
                        if (sum_size >= MAX_SIZE and file_size < MAX_SIZE):
                            #send mail until here
                            print("sending mail", "\n")
                            msg=CreateMsg(user,send_to)
                            server.sendmail(user, send_to, msg.as_string())
                            sum_size = file_size
                            print(f, " ", file_size / 1000000, " ", sum_size / 1000000)
                            #build new mail
                            part = MIMEApplication(fil.read(), Name=file_name)
                            part['Content-Disposition'] = 'attachment; filename="%s"' % file_name
                            msg.attach(part)
                else:
                    print("Incompatible: ", file_name)
                    incompatible_file = False

            # if last file send mail
            if (sum_size < MAX_SIZE and files[-1] == f):
                print("Reached end of folder...\nSending mail... ")
                server.sendmail(user, send_to, msg.as_string())

def TestSmtpAuthentication(user, auth_string):
    """Authenticates to SMTP with the given auth_string.

    Args:
      user: The Gmail username (full email address)
      auth_string: A valid OAuth2 string, not base64-encoded, as returned by
          GenerateOAuth2String.
    """
    auth_bytes = auth_string.encode('utf-8')
    smtp_conn = smtplib.SMTP('smtp.gmail.com', 587)
    smtp_conn.set_debuglevel(True)
    smtp_conn.starttls()
    smtp_conn.docmd('AUTH', 'XOAUTH2 ' + base64.b64encode(auth_bytes).decode())
    return smtp_conn

def main(argv):
    options_parser = SetupOptionParser()
    (options, args) = options_parser.parse_args()
    print(options,"\n\n",args)
    responseToken=GenerateOauth2Token(options.client_id,options.client_secret)
    access_token=responseToken['access_token']
    RequireOptions(options, 'user')
    oauth2_string = GenerateOAuth2String(options.user,access_token,base64_encode=False)
    smtp_conn=TestSmtpAuthentication(options.user, oauth2_string)
    SendToKindle(smtp_conn,options.user,options.send_to,options.file_path)

    if options.quiet:
        print(oauth2_string)

if __name__ == '__main__':
    main(sys.argv)