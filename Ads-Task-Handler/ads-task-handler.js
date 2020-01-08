/**
 * Copyright 2020 Google Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * @fileoverview This module downloads a landing page report from Google Ads and
 * saves the contents to bigquery.
 *
 * This module is part of the agency dashboard solution. It runs as a web
 * service targeted by Google Cloud Tasks. The route expects a GET request with
 * two query parameters:
 *  - cid: the client id of the account to request the landing page report for
 *  - startdate: the date to use as the first date in the report
 */
const express = require('express');
const parseCsv = require('csv-parse/lib/sync');
const {BigQuery} = require('@google-cloud/bigquery');
const request = require('request-promise-native');
const {Logging} = require('@google-cloud/logging');

const app = express();
app.enable('trust proxy');

const logging = new Logging(process.env.GOOGLE_CLOUD_PROJECT);
const log = logging.log('agency-ads-task');

const REPORT_COLS = {
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
  'View rate': 'VideoViewRate',
};

app.get('*', async (req, res, next) => {
  const cid = req.query.cid;
  const startDate = req.query.startdate;
  if (!cid) {
    console.error('Missing query parameter');
    res.status(400).json({'error': 'Missing query parameter'});
    return;
  }

  try {
    const projectName = process.env.GOOGLE_CLOUD_PROJECT;
    requestUrl = `http://ads-service.${projectName}.appspot.com/ads?cid=${cid}`;
    if (typeof startDate !== 'undefined') {
      requestUrl += `&startdate=${startDate}`;
    }
    const adsReport = await request(requestUrl);

    const adsReportRows = parseCsv(adsReport,
        {'columns': true, 'skip_empty_lines': true});
    if (adsReportRows.length === 0) {
      res.status(201).json({'cid': cid});
      return;
    }
    const adsRows = [];
    for (reportRow of adsReportRows) {
      const row = {};
      Object.keys(REPORT_COLS).forEach((colName) => {
        row[REPORT_COLS[colName]] = reportRow[colName];
      });
      let baseUrl = row.UnexpandedFinalUrlString;
      // removes parameters after ignore and, if the url then ends with a lone
      // ?, it too is removed.
      const ignore = baseUrl.indexOf('{ignore}');
      if (ignore !== -1) {
        baseUrl = baseUrl.slice(0, ignore);
      }
      if (baseUrl.endsWith('?')) {
        baseUrl = baseUrl.slice(0, -1);
      }
      row.BaseUrl = baseUrl;
      row.CID = cid;
      // Ads reports return percentages as strings with %, so we change them
      // back to numbers between 0 and 1
      // we also need to change -- to 0 to insert values.
      Object.keys(row).forEach((key) => {
        if (typeof row[key] === 'string' && row[key].endsWith('%')) {
          row[key] = (row[key].slice(0, -1)) / 100;
        } else if (row[key] === ' --') {
          row[key] = 0;
        }
      });

      adsRows.push(row);
    }

    const bigquery = new BigQuery();
    const table = bigquery.dataset('agency_dashboard').table('ads_data');
    await table.insert(adsRows);
    console.info(`Success for ${cid}`);

    res.status(201).json({'cid': cid});
  } catch (err) {
    if ('name' in err && err.name === 'PartialFailureError') {
      for (e of err.errors) {
        for (e2 of e.errors) {
          console.error(`BigQuery error: ${e2.message}`);
        }
      }
    }
    return next(err);
  }
});

const PORT = process.env.PORT || 8083;
app.listen(PORT, () => {
  log.info(`ads-task-handler started on port ${PORT}`);
});
