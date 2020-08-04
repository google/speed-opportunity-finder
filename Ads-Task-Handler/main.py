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
"""This service retrieves and forwards landing page reports in CSV format.

The Ads-Task-Handler downloads the landing page report for the Google Ads
account with the given CID. The report is then enriched with the name provided,
the CID, and a base URL for the landing page. The base URL is the landing page
URL stripped of parameters after {ignore} and any trailing '?' or '/'.

The enriched landing page report is then loaded into the
agency_dashboard.ads_data biqquery table of the working Google CLoud project.
"""

import csv
from datetime import datetime
import logging
import os

from bottle import Bottle
from bottle import HTTPError
from bottle import request
from googleads import adwords

from google.cloud import bigquery
from google.cloud import firestore
import google.cloud.exceptions
import google.cloud.logging

app = Bottle()

logging_client = google.cloud.logging.Client()
logging_handler = logging_client.get_default_handler()
logger = logging.getLogger('Ads-Service')
logger.setLevel(logging.INFO)
logger.addHandler(logging_handler)

# The columns of the landing page report with the name as returned by the API as
# the  key and the name used in the select statement as the value.
REPORT_COLS = {
    'Campaign ID': 'CampaignId',
    'Campaign': 'CampaignName',
    'Campaign state': 'CampaignStatus',
    'Landing page': 'UnexpandedFinalUrlString',
    'Day': 'Date',
    'Device': 'Device',
    'Active View avg. CPM': 'ActiveViewCpm',
    'Active View viewable CTR': 'ActiveViewCtr',
    'Active View viewable impressions': 'ActiveViewImpressions',
    'Active View measurable impr. / impr.': 'ActiveViewMeasurability',
    'Active View measurable cost': 'ActiveViewMeasurableCost',
    'Active View measurable impr.': 'ActiveViewMeasurableImpressions',
    'Active View viewable impr. / measurable impr.': 'ActiveViewViewability',
    'All conv.': 'AllConversions',
    'Avg. Cost': 'AverageCost',
    'Avg. CPC': 'AverageCpc',
    'Avg. CPE': 'AverageCpe',
    'Avg. CPM': 'AverageCpm',
    'Avg. CPV': 'AverageCpv',
    'Avg. position': 'AveragePosition',
    'Clicks': 'Clicks',
    'Conv. rate': 'ConversionRate',
    'Conversions': 'Conversions',
    'Total conv. value': 'ConversionValue',
    'Cost': 'Cost',
    'Cost / conv.': 'CostPerConversion',
    'Cross-device conv.': 'CrossDeviceConversions',
    'CTR': 'Ctr',
    'Engagement rate': 'EngagementRate',
    'Engagements': 'Engagements',
    'Impressions': 'Impressions',
    'Interaction Rate': 'InteractionRate',
    'Interactions': 'Interactions',
    'Interaction Types': 'InteractionTypes',
    'Mobile-friendly click rate': 'PercentageMobileFriendlyClicks',
    'Valid AMP click rate': 'PercentageValidAcceleratedMobilePagesClicks',
    'Mobile speed score': 'SpeedScore',
    'Value / conv.': 'ValuePerConversion',
    'View rate': 'VideoViewRate'
}

PROJECT_NAME = os.environ['GOOGLE_CLOUD_PROJECT']


@app.route('/')
def export_landing_page_report():
  """This route triggers the download of the Ads landing page report.

  The landing page report for the client is downloaded using credentials stored
  in the project firestore datastore. The report is downloaded either for the
  last 30 days if never run before, or from the last run date to today if there
  is a date stored in firestore. The last run date is updated after the report
  is downloaded from Ads.

  Returns:
    The landing page report in CSV format

  Raises:
    HTTPError: Used to cause bottle to return a 500 error to the client.
  """
  customer_id = request.params.get('cid')
  customer_name = request.params.get('name')
  start_date = request.params.get('startdate')
  if not customer_id:
    logger.error('Client customer id (cid) not included in request')
    raise HTTPError(400,
                    'Customer client id not provided as cid query parameter.')

  storage_client = firestore.Client()

  try:
    credentials_doc = (
        storage_client.collection('agency_ads').document('credentials').get())
    developer_token = credentials_doc.get('developer_token')
    client_id = credentials_doc.get('client_id')
    client_secret = credentials_doc.get('client_secret')
    refresh_token = credentials_doc.get('refresh_token')
    ads_credentials = ('adwords:\n' + f' client_customer_id: {customer_id}\n' +
                       f' developer_token: {developer_token}\n' +
                       f' client_id: {client_id}\n' +
                       f' client_secret: {client_secret}\n' +
                       f' refresh_token: {refresh_token}')
  except google.cloud.exceptions.NotFound:
    logger.exception('Unable to load ads credentials.')
    raise HTTPError(500, 'Unable to load Ads credentials.')

  ads_client = adwords.AdWordsClient.LoadFromString(ads_credentials)
  landing_page_query = adwords.ReportQueryBuilder()
  # selecting campaign attributes, unexpanded final url, device,
  # date, and all of the landing page metrics.
  landing_page_query.Select(','.join(REPORT_COLS.values()))
  landing_page_query.From('LANDING_PAGE_REPORT')
  if not start_date:
    landing_page_query.During(date_range='YESTERDAY')
  else:
    try:
      start_date = datetime.date.fromisoformat(start_date)
      today = datetime.date.today()
    except ValueError:
      logger.info('Invalid date passed in startdate parameter.')
      raise HTTPError(400, 'Invalid date in startdate parameter.')
    if start_date == datetime.date.today():
      landing_page_query.During(date_range='TODAY')
    else:
      if today < start_date:
        logger.error('Last run date in the future (start_date: %s)', start_date)
        raise HTTPError(400,
                        'startdate in the future (start_date: %s)' % start_date)

      landing_page_query.During(
          start_date=start_date.strftime('%Y%m%d'),
          end_date=today.strftime('%Y%m%d'))

  landing_page_query = landing_page_query.Build()

  report_downloader = ads_client.GetReportDownloader(version='v201809')
  try:
    landing_page_report = (
        report_downloader.DownloadReportAsStreamWithAwql(
            landing_page_query,
            'CSV',
            skip_report_header=True,
            skip_report_summary=True))
  except Exception as e:
    logger.exception('Problem with retrieving landing page report')
    raise HTTPError(500, 'Unable to retrieve landing page report %s' % e)

  ads_cols = []
  ads_rows = []
  try:
    while True:
      report_line = landing_page_report.readline()
      if not report_line: break

      report_line = report_line.decode().replace('\n', '')
      report_row = report_line.split(',')

      if not ads_cols:
        ads_cols = report_row
        continue

      report_row = dict(zip(ads_cols, report_row))
      # replace row keys
      report_row = {REPORT_COLS[key]: val for key, val in report_row.items()}
      base_url = report_row['UnexpandedFinalUrlString']
      # removes parameters after ignore and, if the url then ends with a lone
      # ?, it too is removed.
      if '{ignore}' in base_url:
        base_url = base_url[0:base_url.index('{ignore}')]
      if base_url.endswith('?'):
        base_url = base_url[0:-1]
      report_row['BaseUrl'] = base_url
      report_row['CID'] = customer_id
      report_row['ClientName'] = customer_name
      # Ads reports return percentages as strings with %, so we change them
      # back to numbers between 0 and 1
      # we also need to change -- to 0 to insert values.
      for k, v in report_row.items():
        if v.endswith('%'):
          report_row[k] = float(v[0:-1]) / 100
        elif v.isdecimal():
          report_row[k] = float(v)
        elif v == ' --':
          report_row[k] = None

      ads_rows.append(report_row)
  except OSError as e:
    logger.exception('Problem reading the landing page report: %s', e)
    raise HTTPError(500, 'Unable to read landing page report.')
  finally:
    landing_page_report.close()

  if ads_rows:
    csv_file_name = '/tmp/ads_data.' + str(datetime.timestamp(datetime.now()))
    with open(csv_file_name, 'w', newline='') as csv_file:
      try:
        csv_writer = csv.DictWriter(csv_file, fieldnames=ads_cols)
        csv_writer.writeheader()
        csv_writer.writerows(ads_rows)
      except OSError as os_error:
        logger.exception(
            'Problem writing the landing page report to a temp file: %s', e)
        raise HTTPError(500, 'Unable to write landing page report to file.')
    try:
      bq_client = bigquery.Client()
      bq_table = bq_client.get_table(
          f'{PROJECT_NAME}.agency_dashboard.ads_data')
      bq_job_config = bigquery.LoadJobConfig()
      bq_job_config.source_format = bigquery.SourceFormat.CSV
      bq_job_config.skip_leading_rows = 1
      bq_job_config.autodetect = True
      with open(csv_file_name, 'rb') as csv_file:
        try:
          bq_job = bq_client.load_table_from_file(
              csv_file, bq_table, job_config=bq_job_config)
          bq_job_result = bq_job.result()
        except Exception as ex:
          logger.exception('Problem loading ads data into bigquery: %s', ex)
          raise ex
    except google.cloud.exceptions.GoogleCloudError as gce:
      logger.exception('Problem loading ads data into bigquery: %s',
                       gce.message)
      raise gce

if __name__ == '__main__':
  app.run(host='localhost', port=8090)
