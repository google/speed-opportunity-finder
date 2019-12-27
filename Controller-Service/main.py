# Lint as: python3
"""TODO(adamread): DO NOT SUBMIT without one-line documentation for main.

TODO(adamread): DO NOT SUBMIT without a detailed description of main.
"""

import datetime
import logging
import os
import time

from bottle import Bottle
from bottle import HTTPError
from googleads import adwords

import google.cloud.bigquery
import google.cloud.exceptions
import google.cloud.firestore
import google.cloud.logging
import google.cloud.tasks

app = Bottle()

logging_client = google.cloud.logging.Client()
logging_handler = logging_client.get_default_handler()
logger = logging.getLogger('Controller-Service')
logger.addHandler(logging_handler)


@app.route('/')
def start_update():
  """This route triggers the process of updating the ads and lighthouse data.
  """
  cids = []
  project_name = os.environ['GOOGLE_CLOUD_PROJECT']
  project_location = os.environ['APP_LOCATION']

  try:
    storage_client = google.cloud.firestore.Client()
    credentials_doc = (storage_client.collection('agency_ads')
                       .document('credentials').get())
    mcc_id = credentials_doc.get('mcc_id')
    developer_token = credentials_doc.get('developer_token')
    client_id = credentials_doc.get('client_id')
    client_secret = credentials_doc.get('client_secret')
    refresh_token = credentials_doc.get('refresh_token')
    ads_credentials = ('adwords:\n' +
                       f' client_customer_id: {mcc_id}\n' +
                       f' developer_token: {developer_token}\n' +
                       f' client_id: {client_id}\n' +
                       f' client_secret: {client_secret}\n' +
                       f' refresh_token: {refresh_token}')
    ads_client = adwords.AdWordsClient.LoadFromString(ads_credentials)
  except google.cloud.exceptions.NotFound:
    logger.exception('Unable to load ads credentials.')
    raise HTTPError(500, 'Unable to load Ads credentials.')

  try:
    mcc_service = ads_client.GetService('ManagedCustomerService',
                                        version='v201809')
    selector = {'fields': ['CustomerId']}
    result = mcc_service.get(selector)
    for record in result.links:
      cids.append(str(record.clientCustomerId))
  except:
    logger.exception('Exception while getting CIDs')
    raise HTTPError(500, 'Exception while getting CIDs')

  try:
    config_doc = storage_client.collection('agency_ads').document('config')
    config_doc_snapshot = config_doc.get()
    last_run_dates = config_doc_snapshot.get('last_run')
  except google.cloud.exceptions.NotFound:
    logger.exception('Exception retrieving last run dates.')
    raise HTTPError(500, 'Config document not found in firestore')
  except KeyError:
    logger.info('Last tun dates not in firestore.')
    last_run_dates = {}

  try:
    task_client = google.cloud.tasks.CloudTasksClient()
    ads_queue_path = task_client.queue_path(project_name, project_location,
                                            'ads-queue')
    today = datetime.date.today().isoformat()
    for cid in cids:
      if cid in last_run_dates:
        task_url = (f'http://ads-task-handler.{project_name}.appspot.com?' +
                    f'cid={cid}&startdate={last_run_dates[cid]}')
      else:
        task_url = (f'http://ads-task-handler.{project_name}.appspot.com' +
                    f'?cid={cid}')
      task = {
          'http_request': {
              'http_method': 'GET',
              'url': task_url
          }
      }
      task_client.create_task(ads_queue_path, task)
      config_doc.update({
          f'last_run.{cid}': today
      })
  except:
    logger.exception(f'Exception queing ads queries (url = {task_url})')
    raise HTTPError(500, 'Exception queing ads queries.')

  # polling the queue to ensure all the URLs are available before starting the
  # lighthouse tests. It would be nice to have a better, parllel way to do this.
  ads_queue_size = True
  while ads_queue_size:
    time.sleep(30)
    ads_queue_list = list(task_client.list_tasks(ads_queue_path))
    ads_queue_size = len(ads_queue_list)

  try:
    bigquery_client = google.cloud.bigquery.Client()
    url_query = f'''SELECT BaseUrl
                   FROM `{project_name}.agency_dashboard.base_urls`'''
    query_reaponse = bigquery_client.query(url_query)
  except:
    logger.exception('Exception querying for URLs')
    raise HTTPError(500, 'Exception querying for URLs')

  try:
    lh_queue_path = task_client.queue_path(project_name, project_location,
                                           'lh-queue')
    for row in query_reaponse:
      url = row['BaseUrl']
      task = {
          'http_request': {
              'http_method': 'GET',
              'url': f'http://lh_service.{project_name}.appspot.com?url={url}'}
      }
      task_client.create_task(lh_queue_path, task)
  except:
    logger.exception('Excpetion queue lh tasks.')
    raise HTTPError(500, 'Exception queuing lh tasks.')

if __name__ == "__main__":
  app.run(host='localhost', port=8084)
