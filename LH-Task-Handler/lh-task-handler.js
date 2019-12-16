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

const app = express();
app.enable('trust proxy');

const logging = new Logging(process.env.GOOGLE_CLOUD_PROJECT);
const log = logging.log('agency-lh-task');

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

/**
 * Responds to get requests to handle the case of performaing a lighthouse audit
 * using the lighthouse audit service and then inserting the results into
 * bigquery.
 */
app.get('*', async (req, res, next) => {
  const testUrl = req.query.url;
  if (!testUrl) {
    log.error('Missing query parameter');
    res.status(400).json({'error': 'Missing query parameter'});
    return;
  }

  try {
    const projectName = process.env.GOOGLE_CLOUD_PROJECT;
    const lhAudit = await request(
        `http://lh-service.${projectName}.appspot.com/lh?url=${testUrl}`,
        {json: true});

    log.info(lhAudit);
    const row = {
      date: lhAudit.fetchTime,
      url: lhAudit.finalUrl,
      lhscore: lhAudit.categories.performance.score,
    };
    if (row.date.endsWith('Z')) {
      row.date = row.date.slice(0, -1);
    }
    for (a of Object.keys(AUDITS)) {
      row[AUDITS[a]] = lhAudit.audits[a].numericValue;
    }

    const bqClient = new BigQuery();
    const table = bqClient.dataset('agency_dashboard').table('lh_data');
    await table.insert(row);
    log.info(`Success for ${testUrl}`);
    res.status(201).json({'url': testUrl});
  } catch (err) {
    const foo = err.errors[0].row;
    console.error(`ERROR CAUGHT: ${foo}`);
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
