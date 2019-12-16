/**
 * @fileoverview Description of this file.
 */
const express = require('express');
const parseCsv = require('csv-parse');
const {BigQuery} = require('@google-cloud/bigquery');
const request = require('request-promise-native');
const {Logging} = require('@google-cloud/logging');

const app = express();
app.enable('trust proxy');

const logging = new Logging(process.env.GOOGLE_CLOUD_PROJECT);
const log = logging.log('agency-ads-task');


app.get('*', async (req, res, next) => {
  const cid = req.query.cid;
  if (!cid) {
    log.error('Missing query parameter');
    res.status(400).json({'error': 'Missing query parameter'});
    return;
  }

  try {
    const projectName = process.env.GOOGLE_CLOUD_PROJECT;
    const adsReport = await request(
        `http://ads-service.${projectName}.appspot.com/ads?cid=${cid}`);
    const adsRows = parseCsv(adsReport,
        {'columns': true, 'skip_empty_lines': true});
    log.debug(`${adsRows}`);

    for (row of adsRows) {
      let baseUrl = row.UnexpandedFinalUrlString;
      // removes parameters after ignore and, if the url then ends with a lone
      // ?, it too is removed.
      const ignore = reportUrl.indexOf('{ignore}');
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
      for (key of Object.keys(row)) {
        if (typeof row[key] === 'string' &&row[key].endsWith('?')) {
          row[key] = (row[key].slice(0, -1)) / 100;
        }
      }
    }

    const bigquery = new BigQuery();
    const table = bigquery.dataset('agency_dashboard').table('ads_data');
    await table.insert(reportRows, insertHandler);
    log.info(`Success for ${cid}`);

    res.status(201).json({'cid': cid});
  } catch (err) {
    if ('name' in err && err.name === 'PartialFailureError') {
      for (e of err.errors) {
        for (e2 of e.errors) {
          log.error(`BigQuery error: ${e2.message}`);
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
