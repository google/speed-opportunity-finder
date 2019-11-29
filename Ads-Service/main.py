# Lint as: python3
"""TODO(adamread): DO NOT SUBMIT without one-line documentation for ads-service.

TODO(adamread): DO NOT SUBMIT without a detailed description of ads-service.
"""

from bottle import Bottle
from bottle import route
from bottle import response
from bottle import HTTPError
from google.cloud import firestore
import google.cloud.exceptions
from google.cloud import error_reporting
from googleads import adwords
from datetime import date
from datetime import timedelta
from google.cloud import bigquery


app = Bottle()
logger = error_reporting.Client()

@app.route("/ads")
def export_landing_page_report():
  storage_client = firestore.Client()
  try:
    storage_collection = storage_client.collection('agency_ads')
    ads_credentials = storage_collection.document('credentials').get()
  except google.cloud.exceptions.NotFound:
    logger.report('Unable to load ads credentials.')
    logger.report_exception()
    raise HTTPError(500, 'Unable to load Ads credentials.')

  try:
    last_run_date = storage_collection.document('last_run').get()
    last_run_date = date.fromisoformat(last_run_date)
  except google.cloud.exceptions.NotFound:
    logger.report('Last run date not found in firestore document.')
    last_run_date = False

  ads_client = adwords.AdWordsClient.LoadFromString(ads_credentials)
  landing_page_query = adwords.ReportQueryBuilder()
  # selecting campaign attributes, unexpanded final url, click type, device,
  # date, and all of the landing page metrics.
  landing_page_query.Select(
      'CampaignId', 'CampaignName, CampaignStatus',
      'UnexpandedFinalUrlString', 'Date', 'Device', 'ClickType',
      'ActiveViewCpm', 'ActiveViewCtr', 'ActiveViewImpressions',
      'ActiveViewMeasurability', 'ActiveViewMeasurableCost',
      'ActiveViewMeasurableImpressions', 'ActiveViewViewability',
      'AllConversions', 'AverageCost', 'AverageCpc', 'AverageCpe',
      'AverageCpm', 'AverageCpv', 'AveragePosition', 'Clicks',
      'ConversionRate', 'Conversions', 'ConversionValue', 'Cost',
      'CostPerConversion', 'CrossDeviceConversions', 'Ctr', 'EngagementRate',
      'Engagements', 'Impressions', 'InteractionRate', 'Interactions',
      'InteractionTypes', 'PercentageMobileFriendlyClicks',
      'PercentageValidAcceleratedMobilePagesClicks', 'SpeedScore',
      'ValuePerConversion', 'VideoViewRate', 'VideoViews')
  landing_page_query.From('LANDING_PAGE_REPORT')
  if not last_run_date:
    landing_page_query.During('LAST_30_DAYS')
  else:
    today = date.today().strftime('%Y%m%d')
    start_date = (last_run_date + timedelta(days=1)).strftime('%Y%m%d')
    landing_page_query.During(start_date=start_date, end_date=today)
  landing_page_query = landing_page_query.Build()

  report_downloader = ads_client.GetReportDownloader(version='v201809')
  try:
    landing_page_report = report_downloader.DownloadReportAsStringWithAwql(landing_page_query, 'CSV')
  except Exception as e:
    logger.report('Problem with retrieving landing page report')
    logger.report_exception()
    raise HTTPError(500, 'Unable to retrieve landing page report %s' % e)
  response.set_header('Content-Type', 'text/csv')
  return landing_page_report
