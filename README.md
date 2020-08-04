# Landing Page Speed Opportunity Finder

**This is not an officially supported Google product**

Copyright 2019 Google LLC. This solution, including any related sample code or 
data, is made available on an “as is,” “as available,” and “with all faults” 
basis, solely for illustrative purposes, and without warranty or representation 
of any kind. This solution is experimental, unsupported and provided solely for 
your convenience. Your use of it is subject to your agreements with Google, as 
applicable, and may constitute a beta feature as defined under those agreements. 
To the extent that you make any data available to Google in connection with your 
use of the solution, you represent and warrant that you have all necessary and 
appropriate rights, consents and permissions to permit Google to use and process
that data. By using any portion of this solution, you acknowledge, assume and 
accept all risks, known and unknown, associated with its usage, including with 
respect to your deployment of any portion of this solution in your systems, or
usage in connection with your business, if at all.

## Overview

The speed opportunity finder solution is a set of services to automate the 
collection of data used to create reports on how landing page web performance
metrics impact Ads business metrics.

The data collected comes from Google Ads and the PageSpeed Insights API. An Ads 
Management account (MCC) is used to determine which Ads accounts are included in
the data collection. The landing pages from the included accounts are audited 
via PageSpeed Insights (PSI). The solution runs on Google App Engine and all of 
the data is stored in BigQuery.

The BigQuery tables are meant to be used as data sources for DataStudio 
dashboards. An example dashboard is provided as part of the solution, but it is 
meant to be copied and customized for the end client being targeted.

## Installation
There are three major steps to installing the Speed Opportunity Finder:

1. [Deploy the solution](https://google.github.io/speed-opportunity-finder/deploy.html) to Google App Engine.
1. [Gather the required credentials](https://google.github.io/speed-opportunity-finder/credentials.html).
1. [Complete the deployment](https://google.github.io/speed-opportunity-finder/deploy.html#finish-deployment)

Please look over the [credentials page](https://google.github.io/speed-opportunity-finder/credentials.html)
before starting the deployment. The requirements for a Ads API devloper key may 
result in a delay before the tool can be deployed.

## Updating to Lighthouse v6

Lighthouse v6 introduced the Core Web Vitals metrics and made a breaking change
to the report ([Release notes](https://github.com/GoogleChrome/lighthouse/releases/tag/v6.0.0)). 

To check if your deployment needs to be updated, check the lh_data bigquery 
table schma for a column named `time_to_first_byte`. If the column is present,
you need to follow the following steps to update your deployment before 
deploying the latest version of the tool. If the column is missing, you're 
already up to date.

To update an exising deployment to Lighthouse v6:
1. Add the following columns to the lh_data table schema:
  1. `{"name": "largest_contentful_paint","type":"FLOAT","mode":"NULLABLE"}`
  1. `{"name":"cumulative_layout_shift","type":"FLOAT","mode":"NULLABLE"}`
1. Ensure your Speed Opportuniy Finder project is the active project in your
console using `gcloud config set project <YOUR PROJECT ID>`
1. Run the following command to update the name of time_to_first_byte: 
```
    bq query \
    --destination_table agency_dashboard.lh_data \
    --replace \
    --use_legacy_sql=false \
    'SELECT
      * EXCEPT(time_to_first_byte),
      time_to_first_byte AS server_response_time
    FROM
      agency_dashboard.lh_data'
```
1. Update the name of the column in your datastudio data sources by reconnecting
the data source.
