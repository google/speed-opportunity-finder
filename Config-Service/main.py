"""
 Copyright 2020 Google Inc.

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""
"""This module provides a service for adding credentials to the agency
dashboard.

The module is used in conjunction with the rest of the agency dashboard solution
to provide the credentials required to acccess the Ads accounts that will be the
basis for reporting.

This must be deployed as part of the agency dashboard Google Cloud AppEngine
app. Optionally, this component can be left out of the deployment and the
required credentials can be inserted manually into the project firestore store.

The required credentials must be located in a document stored at
/agency_ads/credentials and have the following fields:
- mcc_id: the account id of the management account to be used with the app
- client_id: the client ID created in the Google API console
- client_secret: the client secret generated with the above client id
- developer_token: the developer token for the account to be used with the app
- refresh_token: an oauth2 refresh token generated using the client id and
secret above
"""

import logging
import urllib.parse

from bottle import Bottle
from bottle import HTTPError
from bottle import redirect
from bottle import request
from bottle import template
from bottle import view
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError

import google.cloud.exceptions
import google.cloud.firestore
import google.cloud.logging

app = Bottle()
logging_client = google.cloud.logging.Client()
logging_handler = logging_client.get_default_handler()
logger = logging.getLogger('Config-Service')
logger.addHandler(logging_handler)


def client_config_exists():
  """Retrives the Adwords client configuation from firestore.

  Retrieves the Adwords client configuration from firestore if it is available.
  If the client_config doc is not found in the data store, a NotFound exception
  is raised.

  Returns:
    A dict containing the web client configuration for Google Adwords

  Raises:
    google.cloud.exceptions.NotFound: the client_config document was not in the
    agency_ads collection
  """
  storage_client = google.cloud.firestore.Client()
  try:
    client_config = (
        storage_client.collection('agency_ads').document('credentials').get())
    try:
      client_config.get('client_id')
    except KeyError:
      return False
  except google.cloud.exceptions.NotFound:
    return False

  return True


@app.route('/config')
@view('start_config')
def start_ads_config():
  """This route starts the oauth authentication flow.

  The route displays a page that allows the user to input the information
  required

  The route first checks for the existance of the config. If there is an
  existing config, a message is show to the user to help them avoid writing over
  it.

  Returns:
    An html page with fields for entering credentials.

  """
  return {'client_config_exists': client_config_exists()}


@app.route('/config_end')
def end_ads_config():
  """This route completes the oauth flow and saves the returned refresh token.

  The oauth state saved in the start of the flow is also removed from the
  credentials doc.

  Returns:
    On success, an HTML page is returned letting the user know the authorization
    was successful. On failure, the user is returned the page to enter their
    credentials with an error message.
  """
  storage_client = google.cloud.firestore.Client()
  try:
    credentials_doc = (
        storage_client.collection('agency_ads').document('credentials').get())
    client_id = credentials_doc.get('client_id')
    client_secret = credentials_doc.get('client_secret')
    oauth_state = credentials_doc.get('oauth_state')
  except (google.cloud.exceptions.NotFound, KeyError):
    logger.exception('Unable to load ads credentials.')
    return template(
        'start_config', error='Error loading credentials after oauth')

  auth_code = request.query.get('code')
  if not auth_code:
    return template('start_config', error='No authorization code in request.')

  client_config = {
      'web': {
          'client_id': client_id,
          'client_secret': client_secret,
          'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
          'token_uri': 'https://accounts.google.com/o/oauth2/token',
      }
  }
  flow = Flow.from_client_config(
      client_config,
      scopes=['https://www.googleapis.com/auth/adwords'],
      state=oauth_state)

  req = urllib.parse.urlparse(request.url)
  redirect_uri = f'{req.scheme}://{req.hostname}/config_end'
  flow.redirect_uri = redirect_uri
  try:
    flow.fetch_token(code=auth_code)
  except InvalidGrantError:
    logger.exception('Error fetching refresh token after oauth')
    return template('start_config', error='Error retreiving refresh token.')

  storage_client = google.cloud.firestore.Client()
  try:
    credentials_doc = storage_client.collection('agency_ads').document(
        'credentials')
    credentials_doc.update({
        'refresh_token': flow.credentials.refresh_token,
        'oauth_state': google.cloud.firestore.DELETE_FIELD
    })
  except google.cloud.exceptions.NotFound:
    logger.exception('Error finding or updating credentials in firestore.')
    return template(
        'start_config', error='Error updating credentials doc in firestore')

  return template('config_complete')


@app.route('/config_upload_client', method='POST')
def save_client_config():
  """Route used to save the client configuration JSON file to firestore."""
  mcc_id = request.forms.get('mcc_id')
  client_id = request.forms.get('client_id')
  client_secret = request.forms.get('client_secret')
  developer_token = request.forms.get('developer_token')
  psi_api_token = request.forms.get('psi_api_token')

  client_config = {
      'web': {
          'client_id': client_id,
          'client_secret': client_secret,
          'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
          'token_uri': 'https://accounts.google.com/o/oauth2/token',
      }
  }
  flow = Flow.from_client_config(
      client_config, scopes=['https://www.googleapis.com/auth/adwords'])
  req = urllib.parse.urlparse(request.url)
  redirect_uri = f'{req.scheme}://{req.hostname}/config_end'
  flow.redirect_uri = redirect_uri
  auth_url, oauth_state = flow.authorization_url(prompt='consent')

  storage_client = google.cloud.firestore.Client()
  try:
    credentials_doc = storage_client.collection('agency_ads').document(
        'credentials')
    credentials_content = {
        'mcc_id': mcc_id,
        'client_id': client_id,
        'client_secret': client_secret,
        'developer_token': developer_token,
        'psi_api_token': psi_api_token,
        'oauth_state': oauth_state
    }
    credentials_doc.set(credentials_content)
  except google.cloud.exceptions.NotFound:
    logger.exception('Unable to find ads credentials.')
    raise HTTPError(500, 'Unable to find ads credentials.')

  redirect(auth_url)
  