/**
 * @fileoverview A Cloud Tasks task handler for the agency dashboard.
 *
 * This takes a single url as a query parameter, performs a lighthouse audit on
 * it, and then inserts the relevant metrics into bigquery.
 */

const express = require('express');
const {BigQuery} = require('@google-cloud/bigquery');
const request = require('request');

const app = express();
app.enable('trust proxy');

/**
 * Inserts the performance metrics of a lighthouse audit into bigquery.
 * @param {object} lhAudit
 */
function insertLHintoBQ(lhAudit) {
  const AUDITS = {
    'first-contentful-paint': 'first_contentful_paint',
    'first-meaningful-paint': 'first_meaningful_paint',
    'speed-index': 'speed_index',
    'estimated-input-latency': 'estimated_input_latency',
    'total-blocking-time': 'total_blocking_time',
    'max-potential-fid': 'max_potential_fid',
    'time-to-first-byte': 'time_to_first_byte',
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

  const row = {
    date: lhAudit.fetchTime,
    url: lhAudit.finalUrl,
    lhscore: lhAudit.categories.performance.score,
  };
  for (a of Object.keys(AUDITS)) {
    row[AUDITS[a]] = lhAudit.audits[a].numericValue;
  }

  const bqClient = new BigQuery();
  const table = bqClient.dataset('agency_dashboard').table('lh_data');
  table.insert(row, insertHandler);

  /**
   * A callbackfor use when inserting data in the bigquery store. This is only
   * used in error cases.
   * @param {error} err the error thrown by bigquery
   * @param {object} apiResponse the full API response
   */
  function insertHandler(err, apiResponse) {
    if (err) {
      throw err;
    }
  }
}

/**
 * Responds to get requests to handle the case of performaing a lighthouse audit
 * using the lighthouse audit service and then inserting the results into
 * bigquery.
 */
app.get('*', (req, res) => {
  const testUrl = req.query.url;
  if (!testUrl) {
    res.status(400).json({'error': 'Missing query parameter'});
  }

  request('', {json: true}, (err, resp, body) => {
    if (err) {
      res.status(500).json({'error': err.body, 'cause': 'LH'});
    }
    try {
      insertLHintoBQ(body);
    } catch (e) {
      res.status(500).json({'error': e, 'cause': 'BQ'});
    }
  });

  res.status(201).json({'url': testUrl});
});

const PORT = process.env.PORT || 8081;
app.listen(PORT, () => {
  console.log(`lh-service started on port ${PORT}`);
});
