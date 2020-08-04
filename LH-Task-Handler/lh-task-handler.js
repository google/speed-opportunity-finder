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
 * @fileoverview A Cloud Tasks task handler for the agency dashboard.
 *
 * This takes a single url as a query parameter, performs a lighthouse audit on
 * it, and then inserts the relevant metrics into bigquery.
 */

const express = require('express');
const {BigQuery} = require('@google-cloud/bigquery');
const request = require('request-promise-native');
const {Logging} = require('@google-cloud/logging');
const Firestore = require('@google-cloud/firestore');

const app = express();
app.enable('trust proxy');

const logging = new Logging(process.env.GOOGLE_CLOUD_PROJECT);
const log = logging.log('agency-lh-task');

const AUDITS = {
  'largest-contentful-paint': 'largest_contentful_paint',
  'total-blocking-time': 'total_blocking_time',
  'cumulative-layout-shift': 'cumulative_layout_shift',
  'first-contentful-paint': 'first_contentful_paint',
  'first-meaningful-paint': 'first_meaningful_paint',
  'speed-index': 'speed_index',
  'estimated-input-latency': 'estimated_input_latency',
  'total-blocking-time': 'total_blocking_time',
  'max-potential-fid': 'max_potential_fid',
  'server-response-time': 'server_response_time',
  'first-cpu-idle': 'first_cpu_idle',
  'interactive': 'interactive',
  'mainthread-work-breakdown': 'mainthread_work_breakdown',
  'bootup-time': 'bootup_time',
  'network-requests': 'network_requests',
  'network-rtt': 'network_rtt',
  'network-server-latency': 'network_server_latency',
  'total-byte-weight': 'total_byte_weight',
  'dom-size': 'dom_size',
};

/**
 * Responds to get requests to handle the case of performing a lighthouse audit
 * using the lighthouse audit service and then inserting the results into
 * bigquery.
 */
app.get('*', async (req, res, next) => {
  const testUrl = req.query.url;
  if (!testUrl) {
    log.error('Missing query parameter');
    res.status(200).json({'error': 'Missing query parameter'});
    return;
  }

  try {
    const firestore = new Firestore();
    const credentialDoc = firestore.doc('agency_ads/credentials');
    const credentialSnapshot = await credentialDoc.get();
    const psiApiKey = credentialSnapshot.get('psi_api_token');

    const apiUrl = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed';
    const stdParams = `category=performance&strategy=mobile&key=${psiApiKey}`;
    const requestUrl = `${apiUrl}?url=${testUrl}&${stdParams}`;

    let psiResult = undefined;
    const row = {};

    try {
      psiResult = await request(requestUrl, {json: true});
    } catch (error) {
      psiError = JSON.parse(error.message.slice(6));
      if ('error' in psiError) {
        const today = new Date();
        row.date = today.toISOString().slice(0, 10);
        row.url = testUrl;
        // If the page returned an error, we store the error code.
        // If PSI returns an error, we set the error code to -2 if the quota was
        // exceeeded or to -1 for everything else.
        if (psiError.error.message.includes('Status code')) {
          row.error_code = psiError.error.message
              .match(/Status code: (\d+)/)[1];
        } else if (psiError.error.code === 429) {
          row.error_code = -2;
        } else {
          row.error_code = -1;
        }
        row.error_message = psiError.error.message;

        log.error(`Lighthouse Error (${requestUrl}): ${psiError.error.message}`);
      }
    }
    if (psiResult) {
      const lhAudit = psiResult.lighthouseResult;
      row.date = lhAudit.fetchTime.slice(0, 10);
      row.url = testUrl;
      row.lhscore = lhAudit.categories.performance.score;
      for (a of Object.keys(AUDITS)) {
        try {
          row[AUDITS[a]] = lhAudit.audits[a].numericValue;
        } catch (e) {
          if (e instanceof TypeError) {
            log.error(`Problem accessing ${a} in the PSI audit object.`);
          } else {
            throw e;
          }
        }
      }
      // the individual sizes of resources
      for (part of lhAudit.audits['resource-summary'].details.items) {
        if (part.resourceType === 'total') {
          continue;
        } else {
          const rowName = part.resourceType.replace('-', '_') + '_size';
          row[rowName] = part.transferSize;
        }
      }
    }

    const bqClient = new BigQuery();
    const table = bqClient.dataset('agency_dashboard').table('lh_data');
    await table.insert(row);
    log.info(`Success for ${testUrl}`);
    res.status(201).json({'url': testUrl});
  } catch (err) {
    console.error(`LH Task ERROR: ${err.message}`);
    if ('errors' in err) {
      console.error(`ERROR CAUGHT: ${err.errors[0].row}`);
    }
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

const PORT = process.env.PORT || 8082;
app.listen(PORT, () => {
  console.log(`lh-task-handler started on port ${PORT}`);
});
