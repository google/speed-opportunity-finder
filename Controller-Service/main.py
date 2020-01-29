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
"""This service drives the agency dashboard solution by triggering landing page

report requests and lighthouse audits.

This module runs as a web service and is designed to be targeted by Google Cloud
Scheduler. Using credentials stored in firestore, it first requests all of the
CIDs associated with the stored MCC ID from Ads. Using those CIDs, it creates
Cloud tasks to have landing page reports retrieved and stored in bigquery. Once
the landing page report tasks have been completed, it creates tasks to run
lighthouse audits on all of the URLs in the project's base_urls bigquery table
and have them stored in bigquery.
"""

import datetime
import logging
import os
import time
import urllib

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

project_name = os.environ['GOOGLE_CLOUD_PROJECT']
project_location = os.environ['APP_LOCATION']
today = datetime.date.today().isoformat()

ads_client = None
task_client = None
ads_queue_path = None
last_run_dates = None
config_doc = None


def queue_cids_for_mcc(mcc_id):
  """Queues the report tasks for the cids under the given mcc.

  Args:
    mcc_id:
  """
  ads_client.SetClientCustomerId(mcc_id)
  mcc_service = ads_client.GetService(
      'ManagedCustomerService', version='v201809')
  selector = {'fields': ['CustomerId', 'Name', 'CanManageClients']}
  result = mcc_service.get(selector)
  for record in result.entries:
    if record.customerId == mcc_id:
      continue
    elif record.canManageClients:
      queue_cids_for_mcc(record.customerId)
    else:
      try:
        task_url = (f'http://ads-task-handler.{project_name}.appspot.com' +
                    f'?cid={record.customerId}&' +
                    f'name={urllib.parse.quote(record.name)}')
        if record.customerId in last_run_dates:
          task_url += f'&startdate={last_run_dates[record.customerId]}'
        task = {'http_request': {'http_method': 'GET', 'url': task_url}}
      except TypeError:
        logger.exception('Error creating task_url for record %s - %s',
                         record.customerId, record.name)
        continue
      try:
        task_client.create_task(ads_queue_path, task)
        config_doc.update({f'last_run.{record.customerId}': today})
      except:
        logger.exception(f'Exception queing ads queries (url = {task_url})')
        raise


@app.route('/')
def start_update():
  """This route triggers the process of updating the ads and lighthouse data."""

  try:
    storage_client = google.cloud.firestore.Client()
    credentials_doc = (
        storage_client.collection('agency_ads').document('credentials').get())
    mcc_id = credentials_doc.get('mcc_id')
    developer_token = credentials_doc.get('developer_token')
    client_id = credentials_doc.get('client_id')
    client_secret = credentials_doc.get('client_secret')
    refresh_token = credentials_doc.get('refresh_token')
    ads_credentials = ('adwords:\n' + f' client_customer_id: {mcc_id}\n' +
                       f' developer_token: {developer_token}\n' +
                       f' client_id: {client_id}\n' +
                       f' client_secret: {client_secret}\n' +
                       f' refresh_token: {refresh_token}')
    global ads_client
    ads_client = adwords.AdWordsClient.LoadFromString(ads_credentials)
  except google.cloud.exceptions.NotFound:
    logger.exception('Unable to load ads credentials.')
    raise HTTPError(500, 'Unable to load Ads credentials.')

  try:
    global config_doc
    config_doc = storage_client.collection('agency_ads').document('config')
    config_doc_snapshot = config_doc.get()
    global last_run_dates
    last_run_dates = config_doc_snapshot.get('last_run')
  except google.cloud.exceptions.NotFound:
    logger.exception('Exception retrieving last run dates.')
    raise HTTPError(500, 'Config document not found in firestore')
  except KeyError:
    logger.info('Last tun dates not in firestore.')
    last_run_dates = {}
  if last_run_dates is None:
    config_doc.create({'last_run': {}})
    last_run_dates = {}

  try:
    global task_client
    task_client = google.cloud.tasks.CloudTasksClient()
    global ads_queue_path
    ads_queue_path = task_client.queue_path(project_name, project_location,
                                            'ads-queue')
  except:
    logger.exception('Exception creating tasks client')
    raise HTTPError(500, 'Exception creating tasks client.')

  try:
    queue_cids_for_mcc(mcc_id)
  except:
    logger.exception('Exception while queuing landing page reports')
    raise HTTPError(500, 'Exception while queuing landing page reports')

  # polling the queue to ensure all the URLs are available before starting the
  # lighthouse tests. It would be nice to have a better, parallel way to do
  # this.
  ads_queue_size = True
  while ads_queue_size:
    time.sleep(30)
    ads_queue_list = list(task_client.list_tasks(ads_queue_path))
    ads_queue_size = len(ads_queue_list)

  try:
    bigquery_client = google.cloud.bigquery.Client()
    url_query = f'''SELECT BaseUrl
                   FROM `{project_name}.agency_dashboard.base_urls`'''
    query_response = bigquery_client.query(url_query)
  except:
    logger.exception('Exception querying for URLs')
    raise HTTPError(500, 'Exception querying for URLs')

  try:
    lh_queue_path = task_client.queue_path(project_name, project_location,
                                           'lh-queue')
    for row in query_response:
      url = urllib.parse.quote(row['BaseUrl'])
      task = {
          'http_request': {
              'http_method':
                  'GET',
              'url':
                  f'http://lh-task-handler.{project_name}.appspot.com?url={url}'
          }
      }
      task_client.create_task(lh_queue_path, task)
  except:
    logger.exception('Excpetion queue lh tasks.')
    raise HTTPError(500, 'Exception queuing lh tasks.')


if __name__ == '__main__':
  app.run(host='localhost', port=8084)
