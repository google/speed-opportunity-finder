# Lint as: python3
"""This service retrieves and forwards landing page reports in CSV format.

The Ads service provides a way to fetch Ads landing page reports and return them
in CSV format to the caller. The credentials used must be saved previously in
the app engine project's firestore datastore using the agency-ads collection,
config document, and credentials field. The last_run field is also used to store
the last date the report was fetched.
"""

import datetime
import logging

from bottle import Bottle
from bottle import HTTPError
from bottle import request
from bottle import response
from googleads import adwords

from google.cloud import firestore
import google.cloud.exceptions
import google.cloud.logging

app = Bottle()

logging_client = google.cloud.logging.Client()
logging_handler = logging_client.get_default_handler()
logger = logging.getLogger('Ads-Service')
logger.setLevel(logging.INFO)
logger.addHandler(logging_handler)


@app.route('/ads')
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
  customer_id = request.query.get('cid')
  if not customer_id:
    logger.error('Client customer id (cid) not included in request')
    raise HTTPError(400,
                    'Customer client id not provided as cid query parameter.')

  storage_client = firestore.Client()

  try:
    credentials_doc = (storage_client.collection('agency_ads')
                       .document('credentials').get())
    developer_token = credentials_doc.get('developer_token')
    client_id = credentials_doc.get('client_id')
    client_secret = credentials_doc.get('client_secret')
    refresh_token = credentials_doc.get('refresh_token')
    ads_credentials = ('adwords:\n' +
                       f' client_customer_id: {customer_id}\n'
                       f' developer_token: {developer_token}\n' +
                       f' client_id: {client_id}\n' +
                       f' client_secret: {client_secret}\n' +
                       f' refresh_token: {refresh_token}')
  except google.cloud.exceptions.NotFound:
    logger.exception('Unable to load ads credentials.')
    raise HTTPError(500, 'Unable to load Ads credentials.')

  try:
    config_doc = (storage_client.collection('agency_ads')
                  .document('config').get())
    last_run_date = config_doc.get('last_run')
    last_run_date = datetime.date.fromisoformat(last_run_date)
  except KeyError:
    logger.info('Last run date not found in firestore document.')
    last_run_date = False

  ads_client = adwords.AdWordsClient.LoadFromString(ads_credentials)
  landing_page_query = adwords.ReportQueryBuilder()
  # selecting campaign attributes, unexpanded final url, device,
  # date, and all of the landing page metrics.
  landing_page_query.Select(
      'CampaignId', 'CampaignName, CampaignStatus',
      'UnexpandedFinalUrlString', 'Date', 'Device', 'ActiveViewCpm',
      'ActiveViewCtr', 'ActiveViewImpressions', 'ActiveViewMeasurability',
      'ActiveViewMeasurableCost', 'ActiveViewMeasurableImpressions',
      'ActiveViewViewability', 'AllConversions', 'AverageCost', 'AverageCpc',
      'AverageCpe', 'AverageCpm', 'AverageCpv', 'AveragePosition', 'Clicks',
      'ConversionRate', 'Conversions', 'ConversionValue', 'Cost',
      'CostPerConversion', 'CrossDeviceConversions', 'Ctr', 'EngagementRate',
      'Engagements', 'Impressions', 'InteractionRate', 'Interactions',
      'InteractionTypes', 'PercentageMobileFriendlyClicks',
      'PercentageValidAcceleratedMobilePagesClicks', 'SpeedScore',
      'ValuePerConversion', 'VideoViewRate', 'VideoViews')
  landing_page_query.From('LANDING_PAGE_REPORT')
  if not last_run_date:
    landing_page_query.During('LAST_30_DAYS')
  elif last_run_date == datetime.date.today():
    landing_page_query.During(date_range='TODAY')
  else:
    start_date = (last_run_date + datetime.timedelta(days=1)).strftime('%Y%m%d')
    today = datetime.date.today().strftime('%Y%m%d')
    if today < start_date:
      logger.error('Last run date either today or corrupt (start_date: %s)',
                   start_date)
      raise HTTPError(500,
                      ('Last run date today or corrupt' +
                       '(start_date: %s)' % start_date))
    else:
      landing_page_query.During(start_date=start_date, end_date=today)
  landing_page_query = landing_page_query.Build()

  report_downloader = ads_client.GetReportDownloader(version='v201809')
  try:
    landing_page_report = (report_downloader.DownloadReportAsStringWithAwql(
        landing_page_query, 'CSV', skip_report_header=True,
        skip_report_summary=True))
  except Exception as e:
    logger.exception('Problem with retrieving landing page report')
    raise HTTPError(500, 'Unable to retrieve landing page report %s' % e)

  (storage_client.collection('agency_ads').document('config')
   .update({'last_run': datetime.date.today().isoformat()}))

  response.set_header('Content-Type', 'text/csv')
  return landing_page_report
