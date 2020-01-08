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
 * @fileoverview A google app engine app that runs lighthouse on the provided
 * URL.
 *
 * This service takes a URL and runs a lighthouse on it. It then returns the
 * results of the audit in JSON format.
 *
 * Lighthouse audits can take a significant amount of time to run (minutes), so
 * anything using this service should be made to wait multiple minutes before
 * timing out.
 */

'use strict';

const express = require('express');
const bodyParser = require('body-parser');
const puppeteer = require('puppeteer');
const lighthouse = require( 'lighthouse');
const {GoogleAuth} = require('google-auth-library');
const {Logging} = require('@google-cloud/logging');


/**
 * Retrieves the current project ID so we don't need to hard code it.
 * @return {string} the current Google Cloud project id.
 */
async function getProjectId() {
  const auth = new GoogleAuth({scopes: 'https://www.googleapis.com/auth/cloud-platform'});
  const id = await auth.getProjectId();
  return id;
}
const projectId = getProjectId();
const logging = new Logging({projectId});
const log = logging.log('agency-lh-service');

/**
 * Launches a headless instance of Chrome
 * @return {Object} a puppeteer browser object for controlling the instance
 */
async function launchChrome() {
  const browser = await puppeteer.launch({
    headless: true,
    defaultViewport: null,
  });

  return browser;
}

const app = express();

/**
 * GET handler for running Lighthouse on the URL passed in the request
 * as a parameter
 * @param {Object} req Express request object
 * @param {Object} res Express response object
 */
app.all(/.*/, bodyParser.json(), (req, res) => {
  const testUrl = req.body.url || req.query.url;
  try {
    const checkURL = new URL(testUrl);
    if (checkURL.protocol !== 'http:' && checkURL.protocol !== 'https:') {
      throw new Error('Invalid protocol, must be http or https.');
    }
  } catch (e) {
    log.info(`Malformed request with URL ${req.originalUrl}: ${req.body}`);
    res.status(400);
    res.json({
      url: testUrl,
      message: e.message,
    });
    res.end();
  }
  launchChrome()
      .then((chrome) => {
        const opts = {};
        opts.port = (new URL(chrome.wsEndpoint())).port;
        opts.output = 'json';
        opts.skipAudits = ['screenshot-thumbnails'];
        lighthouse(testUrl, opts, null)
            .then((results) => {
              // TODO check results for an error.
              log.info(`Audit completed for ${testUrl}`);
              res.json(results.lhr);
            })
            .catch((reason) => {
              log.error(`ERROR for ${testUrl}: ${reason.message}`);
              res.status(500);
              res.json({
                error: true,
                message: reason.message,
              });
            })
            .finally(() => {
              chrome.close();
            });
      });
});

const PORT = process.env.PORT || 8081;
app.listen(PORT, () => {
  log.info(`lh-service started on port ${PORT}`);
});

module.exports = app;
