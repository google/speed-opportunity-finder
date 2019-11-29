from bottle import Bottle
from bottle import route
from bottle import template
from bottle import request
from bottle import redirect
from google.cloud import firestore
import google.cloud.exceptions
from google.cloud import error_reporting
from googleads import oauth2
import google.oauth2.credentials
import google_auth_oauthlib.flow
import json

app = Bottle()
logger = error_reporting.Client()

flow = None

def retrieve_client_config():
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
  storage_client = firestore.Client()
  try:
    storage_collection = storage_client.collection('agency_ads')
    client_config = storage_collection.document('client_config').get()
    return client_config
  except google.cloud.exceptions.NotFound:
    logger.report('Unable to load ads credentials.')
    raise

@route('/config')
def start_ads_config():
  """This route starts the oauth authentication flow.

  The route first checks for
  """
  try:
    client_config = retrieve_client_config()
  except google.cloud.exceptions.NotFound:
    return template('upload_client_config')

  flow = google_auth_oauthlib.flow.Flow.from_client_config(client_config, scopes=[oauth2.GetAPIScope('adwords')])
  flow.redirect_uri = 'https://agency-dashboard-v2.appspot.com/end_config'
  auth_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')

  redirect(auth_url)

@route('/config_end')
def end_ads_config():
  """
  """
  auth_code = request.query.get('auth_code')
  if auth_code == '':
    return template('config_complete', error='No authorization code in request.')

  if flow is None:
    return template('config_complete', error='Auth flow not setup. Try starting from config')

  flow.fetch_token(code=auth_code)
  credentials = flow.credentials

  storage_client = firestore.Client()
  credentials_doc = storage_client.collection('agency_ads').document('credentials')
  credentials_doc.set(credentials)

@route('/config_upload_client', method='POST')
def save_client_config():
  """ Route used to save the client configuation JSON file to the agency_ads
  collection in firestore.

  This is the route that is called from the upload_client_config template page.
  The request must contain a JSON file containing the user's Adwords client
  config. If the file isn't in the requrest, or if there are problems parsing
  it, the upload_client_config page is again shown with an error message.

  If everything works, the user is sent through the oauth flow.
  """
  config_file = request.files.get('client-config')
  if config_file == '':
    logger.report('upload_client_config called without a file.')
    return template('upload_client_config', error='No file in request.')
  try:
    client_config = json.load(config_file.file)
  except json.JSONDecodeError as ex:
    logger.report('Error parsing an uploaded client config.')
    logger.report_exception()
    return template('upload_client_config', error=ex.msg)

  storage_client = firestore.Client()
  config_doc = storage_client.collection('agency_ads').document('client_config')
  config_doc.set(client_config)

  start_ads_config()
