# -*- coding: utf-8 -*-
# This is a minimal implementation of the wire protocol for making requests to the Dropbox API.
# Based on The Official Dropbox API V2 SDK for Python (Release 95, v12.0.2, June 2024)
# https://github.com/dropbox/dropbox-sdk-python/tree/main
# Several of the original parameters and functionalities are removed.
# Error handling is simplified and only the most common errors are handled.
# The code is not intended to be a full implementation of the Dropbox API.
#
# Copyright (c) 2025 Istvan Z. Kovacs
#
# The MIT License (MIT)
#     Permission is hereby granted, free of charge, to any person obtaining
#     a copy of this software and associated documentation files (the
#     "Software"), to deal in the Software without restriction, including
#     without limitation the rights to use, copy, modify, merge, publish,
#     distribute, sublicense, and/or sell copies of the Software, and to
#     permit persons to whom the Software is furnished to do so, subject to
#     the following conditions:
#
#     The above copyright notice and this permission notice shall be
#     included in all copies or substantial portions of the Software.
#
#     THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#     EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#     MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#     NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
#     LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
#     OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
#     WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

__all__ = ["DropboxAPI"]

import sys
import time
from json import dumps, loads
from random import random
#from binascii import b2a_base64
from adafruit_requests import Session


if sys.implementation.name == "circuitpython":
    # The RTC (singleton) object is used to get the current time
    # https://docs.circuitpython.org/en/latest/shared-bindings/rtc/index.html
    # The correct time/date must be set before using the Dropbox API!
    from rtc import RTC
else:
    # This can be used when running the code on a PC (CPython)
    from fakertc import RTC

# Set up logging
from adafruit_logging import Handler, LogRecord
import adafruit_logging as logging

class DropboxLogHandler(Handler):
    """ Logging Dropbox info. """

    def __init__(self):
        """Create an instance."""
        super().__init__()

    def format(self, record: LogRecord) -> str:
        """Generate a timestamped message.

        :param LogRecord record: The record (message object) to be logged
        """
        _rtc = RTC()
        _created = _rtc.datetime
        return f"{_created.tm_year:04d}-{_created.tm_mon:02d}-{_created.tm_mday:02d} {_created.tm_hour:02d}:{_created.tm_min:02d}:{_created.tm_sec:02d} - DropboxCPY - {record.levelname} - {record.msg}"

    def emit(self, record: LogRecord):
        """Generate the message.

        :param LogRecord record: The record (message object) to be logged
        """
        print(self.format(record))

dbxlog = logging.getLogger('dropbox')
dbxlog.addHandler(DropboxLogHandler())
assert dbxlog.hasHandlers()
dbxlog.setLevel(logging.INFO)

#
# Dropbox API Hosts and routes
# https://www.dropbox.com/developers/documentation/http/documentation
#

# Host for RPC-style routes
# RPC style means that the argument and result of a route are contained in
# the HTTP body.
API_HOST           = "api.dropboxapi.com"
DB_TOKEN_ROUTE     = "oauth2/token"
DB_USERS_GCA_ROUTE = "users/get_current_account"
DB_LIST_ROUTE         = "files/list_folder"
DB_GETMETADATA_ROUTE  = "files/get_metadata"
DB_CREATEFOLDER_ROUTE           = "files/create_folder_v2"
DB_CREATEFOLDERBATCH_ROUTE      = "files/create_folder_batch"
DB_CREATEFOLDERBATCHCHECK_ROUTE = "files/create_folder_batch/check"

# Host for upload and download-style routes
# Upload style means that the route argument goes in a Dropbox-API-Arg
# header. The HTTP request body contains a binary payload. The result
# comes back in a Dropbox-API-Result header.
# Download style means that the route argument goes in a Dropbox-API-Arg
# header, and the result comes back in a Dropbox-API-Result header. The
# HTTP response body contains a binary payload.
API_CONTENT_HOST  = "content.dropboxapi.com"
DB_UPLOAD_ROUTE   = "files/upload"
DB_DOWNLOAD_ROUTE = "files/download"

# Host for longpoll routes
API_NOTIFICATION_HOST = "notify.dropboxapi.com"

# Maximum blocking timeout for requests
DEFAULT_TIMEOUT = 60
# Token expiration buffer time
TOKEN_EXPIRATION_BUFFER = 60*5
# HTTP status codes
HTTP_STATUS_INVALID_PATH_ROOT = 422

#
# Exceptions from the Dropbox Python SDK
#
class DropboxException(Exception):
    """All errors related to making an API request extend this."""

    def __init__(self, request_id, *args, **kwargs):
        # A request_id can be shared with Dropbox Support to pinpoint the exact
        # request that returns an error.
        super(DropboxException, self).__init__(request_id, *args, **kwargs)
        self.request_id = request_id

    def __str__(self):
        return repr(self)


class ApiError(DropboxException):
    """Errors produced by the Dropbox API."""

    def __init__(self, request_id, error, user_message_text, user_message_locale):
        """
        :param (str) request_id: A request_id can be shared with Dropbox
            Support to pinpoint the exact request that returns an error.
        :param error: An instance of the error data type for the route.
        :param (str) user_message_text: A human-readable message that can be
            displayed to the end user. Is None, if unavailable.
        :param (str) user_message_locale: The locale of ``user_message_text``,
            if present.
        """
        super(ApiError, self).__init__(request_id, error)
        self.error = error
        self.user_message_text = user_message_text
        self.user_message_locale = user_message_locale

    def __repr__(self):
        return 'ApiError({!r}, {})'.format(self.request_id, self.error)


class HttpError(DropboxException):
    """Errors produced at the HTTP layer."""

    def __init__(self, request_id, status_code, body):
        super(HttpError, self).__init__(request_id, status_code, body)
        self.status_code = status_code
        self.body = body

    def __repr__(self):
        return 'HttpError({!r}, {}, {!r})'.format(self.request_id,
            self.status_code, self.body)


class PathRootError(HttpError):
    """Error caused by an invalid path root."""

    def __init__(self, request_id, error=None):
        super(PathRootError, self).__init__(request_id, 422, None)
        self.error = error

    def __repr__(self):
        return 'PathRootError({!r}, {!r})'.format(self.request_id, self.error)


class BadInputError(HttpError):
    """Errors due to bad input parameters to an API Operation."""

    def __init__(self, request_id, message):
        super(BadInputError, self).__init__(request_id, 400, message)
        self.message = message

    def __repr__(self):
        return 'BadInputError({!r}, {!r})'.format(self.request_id, self.message)


class AuthError(HttpError):
    """Errors due to invalid authentication credentials."""

    def __init__(self, request_id, error):
        super(AuthError, self).__init__(request_id, 401, None)
        self.error = error

    def __repr__(self):
        return 'AuthError({!r}, {!r})'.format(self.request_id, self.error)


class RateLimitError(HttpError):
    """Error caused by rate limiting."""

    def __init__(self, request_id, error=None, backoff=None):
        super(RateLimitError, self).__init__(request_id, 429, None)
        self.error = error
        self.backoff = backoff

    def __repr__(self):
        return 'RateLimitError({!r}, {!r}, {!r})'.format(
            self.request_id, self.error, self.backoff)


class InternalServerError(HttpError):
    """Errors due to a problem on Dropbox."""

    def __repr__(self):
        return 'InternalServerError({!r}, {}, {!r})'.format(
            self.request_id, self.status_code, self.body)


#
# Dropbox API Client
#
class DropboxAPI(object):
    """
    A minimal implementation of the wire protocol for making requests to the Dropbox API.
    Based on https://github.com/dropbox/dropbox-sdk-python/blob/be4a41c7e7e88aa010784d57da065a25091efb0e/dropbox/dropbox_client.py#L120
    Several of the original parameters and functionalities are removed: session, ca_cert, scope, etc. to keep the code simple.

    """
    # The Dropbox server API version to use for the requests.
    _API_VERSION = '2'

    def __init__(self,
                 oauth2_access_token=None,
                 max_retries_on_error=4,
                 max_retries_on_rate_limit=None,
                 user_agent=None, 
                 session=None,
                 headers=None,
                 timeout=DEFAULT_TIMEOUT,
                 oauth2_refresh_token=None,
                 oauth2_access_token_expiration=None,
                 app_key=None,
                 app_secret=None):
        """
        :param str oauth2_access_token: OAuth2 access token for making client
            requests.
        :param int max_retries_on_error: On 5xx errors, the number of times to
            retry.
        :param Optional[int] max_retries_on_rate_limit: On 429 errors, the
            number of times to retry. If `None`, always retries.
        :param str user_agent: The user agent to use when making requests. This
            helps us identify requests coming from your application. We
            recommend you use the format "AppName/Version". If set, we append
            "/UnofficialDropboxCircuitPythonSDKv0/" to the user_agent
        :param session: Mandatory to be provided.
        :type session: :class:`adafruit_requests.Session`
        :param dict headers: Additional headers to add to requests.
        :param Optional[float] timeout: Maximum duration in seconds that
            client will wait for any single packet from the
            server. After the timeout the client will give up on
            connection. If `None`, client will wait forever. Defaults
            to 100 seconds.
        :param str oauth2_refresh_token: OAuth2 refresh token for refreshing access token
        :param int oauth2_access_token_expiration: Expiration (seconds) for oauth2_access_token
        :param str app_key: application key of requesting application; used for token refresh
        :param str app_secret: application secret of requesting application; used for token refresh
            Not required if PKCE was used to authorize the token
        """

        if not (oauth2_access_token or oauth2_refresh_token or (app_key and app_secret)):
            raise ValueError(
                'OAuth2 access token or refresh token or app key/secret must be set'
            )
        if session is None:
            raise ValueError('adafruit_requests.Session must be set')
        if not isinstance(session, Session):
            raise ValueError('Expected adafruit_requests.Session, got {}'
                                        .format(session))
        self._session = session

        if headers is not None and not isinstance(headers, dict):
            raise ValueError('Expected dict, got {}'.format(headers))

        self._headers = headers

        if oauth2_refresh_token and not app_key:
            raise ValueError("app_key is required to refresh tokens")

        self._oauth2_access_token = oauth2_access_token
        self._oauth2_refresh_token = oauth2_refresh_token
        self._oauth2_access_token_expiration = oauth2_access_token_expiration

        self._app_key = app_key
        self._app_secret = app_secret

        self._max_retries_on_error = max_retries_on_error
        self._max_retries_on_rate_limit = max_retries_on_rate_limit

        base_user_agent = "UnofficialDropboxCircuitPythonSDKv0" #"OfficialDropboxPythonSDKv2/12.0.2"
        if user_agent:
            self._raw_user_agent = user_agent
            self._user_agent = '{}/{}'.format(user_agent, base_user_agent)
        else:
            self._raw_user_agent = None
            self._user_agent = base_user_agent
        dbxlog.debug(f"User agent: {self._user_agent}")

        self._timeout = timeout
        dbxlog.debug(f"Timeout: {self._timeout}")


    def check_and_refresh_access_token(self):
        """
        Checks if access token needs to be refreshed and refreshes if possible.

        :return:
        """
        _real_time = RTC()
        time_now_sec = time.mktime(_real_time.datetime)
        can_refresh = self._oauth2_refresh_token and self._app_key
        needs_refresh = self._oauth2_refresh_token and \
            (not self._oauth2_access_token_expiration or
            (time_now_sec + int(TOKEN_EXPIRATION_BUFFER)) >=
                self._oauth2_access_token_expiration)
        needs_token = not self._oauth2_access_token
        if (needs_refresh or needs_token) and can_refresh:
            dbxlog.info('Access token expired, refreshing')
            self.refresh_access_token()

    def refresh_access_token(self):
        """
        Refreshes an access token via refresh token if available.

        :return:
        """
        if not (self._oauth2_refresh_token and self._app_key):
            dbxlog.error('Unable to refresh access token without \
                refresh token and app key')
            return

        url = "https://{}/oauth2/token".format(API_HOST)
        body = {'grant_type': 'refresh_token',
                'refresh_token': self._oauth2_refresh_token,
                'client_id': self._app_key,
                }
        if self._app_secret:
            body['client_secret'] = self._app_secret

        dbxlog.debug('POST for refreshing access token')
        with self._session.post(url, data=body, timeout=self._timeout) as res:
            self.raise_dropbox_error_for_resp(res)
            token_content = res.json()

        if "error" in token_content:
            dbxlog.error(f"Error refreshing access token: {token_content["error"]}")
            return
        
        # All good
        _real_time = RTC()
        self._oauth2_access_token = token_content["access_token"]
        time_now_sec = time.mktime(_real_time.datetime)
        dbxlog.debug(f"Previous expiration time: {self._oauth2_access_token_expiration}")
        self._oauth2_access_token_expiration = time_now_sec + \
            int(token_content["expires_in"])
        
        print("Copy these to the settings.toml file:")
        print(f'DBX_ACCESS_TOKEN = "{token_content['access_token']}"')
        print(f'DBX_EXPIRES_AT = {self._oauth2_access_token_expiration}')



    def users_get_current_account(self):
        """
        Gets the current account information for the access token.

        :return: json with account info
        """
        self.check_and_refresh_access_token()
        url = self._get_route_url(API_HOST, DB_USERS_GCA_ROUTE)

        return self.post_request_json_string_with_retry(
            url, 
            timeout=self._timeout)


    def files_list_folder(self, path='', recursive=False):
        """
        List files in a user App folder.

        :param str path: path to the folder
        :param bool recursive: if True, list all files in subfolders
        :return: json with list of files info
        """
        self.check_and_refresh_access_token()
        url = self._get_route_url(API_HOST, DB_LIST_ROUTE)
        # Using app authentication with /2/files/list_folder is meant for accessing the contents of a shared link
        # auth_header = b2a_base64(
        #         "{}:{}".format(self._app_key, self._app_secret).encode("utf-8"),
        #         newline=False
        #     )
        #'Authorization': 'Basic {}'.format(auth_header.decode("utf-8")),
        # Use Bearer token for user authentication
        headers = {
            'Content-Type': 'application/json',
        }
        params = {
            'path': path,
            'recursive': recursive,
            'include_media_info': False,
            'include_deleted': False,
            'include_has_explicit_shared_members': False,
            'include_mounted_folders': True
        }

        return self.post_request_json_string_with_retry(
            url, 
            headers=headers,
            json=params,
            timeout=self._timeout)


    def files_get_metadata(self, path: str):
        """
        Gets metadata for a file or folder.

        :param str path: path to the file or folder
        :return: json with metadata info
        """
        self.check_and_refresh_access_token()
        url = self._get_route_url(API_HOST, DB_GETMETADATA_ROUTE)
        headers = {
            'Content-Type': 'application/json'
        }
        params = {
            'path': path,
            'include_media_info': False,
            'include_deleted': False,
            'include_has_explicit_shared_members': False,
        }

        return self.post_request_json_string_with_retry(
            url, 
            headers=headers,
            json=params,
            timeout=self._timeout)


    def path_exists(self, file_dir: str) -> bool:
        """
        Check if the file/dir exists in Dropbox App 
        
        :param str file_dir: path to the file or folder
        :return: True if file/dir exists, False otherwise
        """
        res = self.files_get_metadata(file_dir)
        #if res[".tag"] == 'not_found':
        #    return False
        if res[".tag"] == 'folder': 
            return True
        if res[".tag"] == 'file':
            return True
        return False

    def files_upload(self, file, path: str, writemode: str ='overwrite'):
        """
        Uploads a file under user App root folder.
        NOTE: Do not use this to upload a file larger than 150 MiB. 
        Instead, create an upload session with upload_session/start.

        :param IO or memoryview/array file: File handle or base64 encoded memoryview/array for contents to upload.
        :param str path: remote path to the file to be uploaded
        :param str writemode: 'overwrite', 'add' or 'update' (default: 'overwrite')
        :return: json with upload info
        """
        self.check_and_refresh_access_token()
        url = self._get_route_url(API_CONTENT_HOST, DB_UPLOAD_ROUTE)
        headers = {
            'Content-Type': 'application/octet-stream',
            'Dropbox-API-Arg': dumps({
                'path': path,
                'mode': writemode,
                'autorename': True,
                'mute': False,
                'strict_conflict': False
            }),
        }

        return self.post_request_json_string_with_retry(
            url, 
            headers=headers,
            data=file,
            timeout=self._timeout)


    def files_create_folder(self, path: str, autorename: bool = True):
        """
        Creates a folder in the user App root folder.

        :param str path: path to the folder to be created
        :param bool autorename: if True, the folder will be renamed if it already exists
        :return: json with folder creation info
        """
        self.check_and_refresh_access_token()
        url = self._get_route_url(API_HOST, DB_CREATEFOLDER_ROUTE)
        headers = {
            'Content-Type': 'application/json'
        }
        params = {
            'path': path,
            'autorename': autorename,
        }

        return self.post_request_json_string_with_retry(
            url, 
            headers=headers,
            json=params,
            timeout=self._timeout)


    def post_request_json_string_with_retry(
        self,
        url: str,
        data = None,
        json: dict  = None,
        headers: dict[str, str] = None,
        stream: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        A simplified version of the Dropbox Python SDK's request_json_string_with_retry method.
        This method can be only be used for POST requests to the given url.

        :param str url: URL to send the POST request to.
        :param data: Data file_handle to send in the request body.
        :param dict json: JSON data to send in the request body.
        :param dict[str, str] headers: Headers to include in the request.
        :param bool stream: If True, stream the response.
        :param float timeout: Timeout for the request.
        :return: JSON response from the server.
        """
        attempt = 0
        rate_limit_errors = 0
        has_refreshed = False
        while True:
            dbxlog.debug(f"POST Request {url}")
            try:
                # Headers
                if headers is None:
                    headers = {}
                headers['User-Agent'] = self._user_agent
                headers['Authorization'] = "Bearer {}".format(self._oauth2_access_token)
                if self._headers:
                    headers.update(self._headers)

                with self._session.post(url, 
                                        data=data,
                                        json=json,
                                        headers=headers,
                                        stream=stream,
                                        timeout=timeout) as res:
                    self.raise_dropbox_error_for_resp(res)
                    if res.status_code in (403, 404, 409):
                        dbxlog.debug(f"POST Request failed with status code: {res.status_code}")
                        dbxlog.debug(f"Response: {res.content.decode('utf-8')}")
                        return res.content.decode('utf-8')
                    else:
                        assert res.headers.get('content-type') == 'application/json', (
                            f"Expected content-type to be application/json, got {res.headers.get('content-type')}")
                        return res.json()

            except AuthError as e:
                if e.error and e.error == 'expired_access_token': #and e.error.is_expired_access_token():
                    if has_refreshed:
                        dbxlog.error('AuthError: Refreshed token error.')
                        raise
                    else:
                        dbxlog.debug('ExpiredCredentials: Refreshing and Retrying')
                        self.refresh_access_token()
                        has_refreshed = True
                else:
                    dbxlog.error(f"AuthError: {e}")
                    raise
            except InternalServerError as e:
                attempt += 1
                if attempt <= self._max_retries_on_error:
                    # Use exponential backoff
                    backoff = 2**attempt * random()
                    dbxlog.debug(f"HttpError status_code={e.status_code}: Retrying in {backoff:.1f} seconds")
                    time.sleep(backoff)
                else:
                    dbxlog.error("InternalServerError: Max retries exceeded.")
                    raise
            except RateLimitError as e:
                rate_limit_errors += 1
                if (self._max_retries_on_rate_limit is None or
                        self._max_retries_on_rate_limit >= rate_limit_errors):
                    # Set default backoff to 5 seconds.
                    backoff = e.backoff if e.backoff is not None else 5.0
                    dbxlog.debug(f"Ratelimit: Retrying in {backoff:.1f} seconds.")
                    time.sleep(backoff)
                else:
                    dbxlog.error("RateLimitError: Max retries on rate limit exceeded.")
                    raise
            except PathRootError as e:
                dbxlog.error(f"PathRootError: {e}")
                raise
            except HttpError as e:
                dbxlog.error(f"HttpError: {e}")
                raise

    def raise_dropbox_error_for_resp(self, res):
        """Checks for errors from a res and handles appropiately.

        :param res: Response of an api request.
        """
        """Checks for errors from a res and handles appropiately.

        :param res: Response of an api request.
        """
        dbxlog.debug(f"Response: {res.status_code}:: {res.headers}")
        request_id = res.headers.get('x-dropbox-request-id')
        if res.status_code >= 500:
            raise InternalServerError(request_id, res.status_code, res.text)
        elif res.status_code == 400:
            try:
                if res.json()['error'] == 'invalid_grant':
                    #err = stone_serializers.json_compat_obj_decode(
                    #    AuthError_validator, 'invalid_access_token')
                    err = 'invalid_access_token'
                    raise AuthError(request_id, err)
                else:
                    raise BadInputError(request_id, res.text)
            except ValueError:
                raise BadInputError(request_id, res.text)
        elif res.status_code == 401:
            assert res.headers.get('content-type') == 'application/json', (
                'Expected content-type to be application/json, got %r' %
                res.headers.get('content-type'))
            err = res.json()['error']['.tag']
            raise AuthError(request_id, err)
        elif res.status_code == HTTP_STATUS_INVALID_PATH_ROOT:
            err = res.json()['error']
            raise PathRootError(request_id, err)
        elif res.status_code == 429:
            err = None
            if res.headers.get('content-type') == 'application/json':
            #     err = stone_serializers.json_compat_obj_decode(
            #         RateLimitError_validator, res.json()['error'])
            #     retry_after = err.retry_after
                err = res.json()['error']
                retry_after = err['retry_after']
            else:
                retry_after_str = res.headers.get('retry-after')
                if retry_after_str is not None:
                    retry_after = int(retry_after_str)
                else:
                    retry_after = None
            raise RateLimitError(request_id, err, retry_after)
        elif res.status_code in (403, 404, 409):
            # special case handled by requester
            return
        elif not (200 <= res.status_code <= 299):
            raise HttpError(request_id, res.status_code, res.text)


    def close(self):
        """
        Cleans up all resources like the request session/network connection.
        """
        pass

    def _get_route_url(self, hostname, route_name):
        """Returns the URL of the route.

        :param str hostname: Hostname to make the request to.
        :param str route_name: Name of the route.
        :rtype: str
        """
        return 'https://{hostname}/{version}/{route_name}'.format(
            hostname=hostname,
            version=DropboxAPI._API_VERSION,
            route_name=route_name,
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
