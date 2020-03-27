*This is not an officially supported Google product*

Copyright 2019 Google LLC. This solution, including any related sample code or
data, is made available on an “as is,” “as available,” and “with all faults”
basis, solely for illustrative purposes, and without warranty or representation
of any kind. This solution is experimental, unsupported and provided solely for
your convenience. Your use of it is subject to your agreements with Google, as
applicable, and may constitute a beta feature as defined under those agreements.
To the extent that you make any data available to Google in connection with your
use of the solution, you represent and warrant that you have all necessary and
appropriate rights, consents and permissions to permit Google to use and process
that data.  By using any portion of this solution, you acknowledge, assume and
accept all risks, known and unknown, associated with its usage, including with
respect to your deployment of any portion of this solution in your systems, or
usage in connection with your business, if at all.

# Overview
The agency dashboard solution is a set of services to automate collecting data
used to create reports on how landing page web performance metrics impact Ads
business metrics.

The data collected comes from [Google Ads](https://ads.google.com) and the
[PageSpeed Insights
API](https://developers.google.com/speed/docs/insights/v5/get-started).
An Ads Management account (MCC) is used to determine which Ads accounts are
included in the data collection. The landing pages from the included accounts
are audited via PSI. The solution runs on Google App Engine and all of the data
is stored in BigQuery.

The BigQuery tables are meant to be used as data sources for
[DataStudio](https://datastudio.google.com/) dashboards. An example dashboard is
provided as part of the solution, but it is meant to be copied and customized
for the end client being targeted.

# Credentials
There are a number of credentials required to use the agency dashboard solution.
- Managemennt Account ID - this is the ID of the management account (MCC) that
  the solution will pull reports for.
- Client ID & Client Secret - these are the credentials created for the Cloud
  project for the Ads API. See the [Adwords API
  documentation](https://developers.google.com/adwords/api/docs/guides/authentication#installed)
  for details.
- Developer Token - this is a production developer token for the MCC you are
  using with the solution. See the [Ads
  documentation](https://developers.google.com/adwords/api/docs/guides/signup)
  for details.
- PageSpeed Insights API key - this is an API key for using pagespeed insights.
  This API runs the lighthouse test for you. See the [PageSpeed Insights
  Documentation](https://developers.google.com/speed/docs/insights/v5/get-started)
  for details.

# Installation
1. create a new Google Cloud project
1. create a new app engine application
1. enable the Google Ads API for the project
1. enable bigquery for the project
1. enable firestore in native mode for the project
1. enable cloud tasks api for the project
1. enable cloud scheduler for the project
1. enable the PageSpeed Insights API for the project
1. create an API key for the [Pagespeed Insights
   API](https://developers.google.com/speed/docs/insights/v5/get-started#key)
1. in the cloud console, clone the source repository
1. set the value of `APP_LOCATION` to the region you deployed the app to in
  the file *Controller-Service/service.yaml*
1. run the install shell script
1. enter the credentials on the *config* page of your deployed
   app. This should be located at `https://config-service.<YOUR_PROJECT>.appspot.com/config`.
1. ping the controller URL to test the set up and gather initial data (see
  Usage)
1. Set the cloud project firewall rules to only allow access to the services,
  excepting the config service, from the app itself. This will ensure outside
  actors are not using the project resources or adding unwanted data to the
  project.
1. set the cron job to gather data on a regular basis (suggested not more often
  than daily)
1. attach a Data Studio project to the bigquery tables for creating reports.
   Follow the steps below to ensure the calculated fields in the data sources
   are maintained.
    1. make a copy of the Data Studio data sources and attach them to the
     appropriate tables from your cloud project
    1. make a copy of the Data Studio report and attach it to the new data sources
     you just made.

# Usage
To test the installation (step 10 above), open the URL
`controller-service.PROJECT_ID.appspot.com/` where PROJECT_ID is the id you gave
the project when you created it. This will start the update process. The URL
will show as loading until either your browser times out or the update process
is finished. If your browser times out, the process will continue until
complete. You can monitor the progress in the Cloud Tasks dashboard of your
project. Please note that the ads_queue must be empty before the Lighthouse
tasks are added to the lh_queue. This is to ensure all URLs are available for
audit.
