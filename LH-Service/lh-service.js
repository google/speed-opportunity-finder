/**
 * @fileoverview A google app engine app that runs lighthouse on the provided
 * URL.
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
