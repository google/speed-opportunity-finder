#!/bin/bash

# Copyright 2020 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Installation script for the agency dashboard solution. Please see the included
# README file for more information.

set -eu

#######################################
# Prints the standard error message and exits.
#######################################
function err() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: Error $*. Please check the output
above this and address the issue before trying again." >&2
  exit 1
}

#######################################
# Enables the Google cloud services required for the solution.
#######################################
function enable_gcloud_services() {
  declare -a gcloud_services
  gcloud_services=("bigquery" "googleads" "cloudtasks" "firestore")
  gcloud_services+=("pagespeedonline")
  
  local gservice
  for gservice in "${gcloud_services[@]}"; do
    if ! gcloud services enable "${gservice}".googleapis.com; then
      err "enabling ${gservice}"
    fi
  done
}

#######################################
# Deploys the solution's service to app engine.
#
# The default service must be deployed first.
#######################################
function deploy_solution_services() {
  declare -a solution_services
  solution_services=("Ads-Task-Handler" "Config-Service" "Controller-Service")
  solution_services+=("LH-Task-Handler")

  if ! gcloud app describe; then
    if ! gcloud app create; then
      echo "This solution requires an app engine project. Please create one." >&2
      exit 1
    fi
  fi
  if ! gcloud app deploy -q Default-Service/service.yaml; then
    err "deploying Default-Service"
  fi
  # the location chosen for the service is needed as a environment variable
  # in the controller service to add tasks to the task queues.
  if ! grep -qF 'APP_LOCATION' Controller-Service/service.yaml; then
    app_location="$(gcloud tasks locations list | awk 'FNR==2 {print $1}')"
    echo "  APP_LOCATION: ${app_location}" >> Controller-Service/service.yaml
  fi

  local service
  for service in "${solution_services[@]}"; do

    if ! gcloud app deploy -q "${service}"/service.yaml; then
      err "deploying ${service} service"
    fi
  done
}

#######################################
# Creates the bigquery tables and views required for the solution.
#######################################
function create_bq_tables() {
  declare -a solution_tables
  solution_tables=("ads_data" "lh_data")

  local bq_datasets
  bq_datasets=$(bq ls)

  if ! [[ "${bq_datasets}" =~ agency_dashboard ]]; then
    if ! bq mk --dataset \
        --description "Agency dashboard data" \
        "${project_id}":agency_dashboard; then
      err "creating bigquery dataset"
    fi
  fi

  local bq_tables
  bq_tables=$(bq ls agency_dashboard)

  local table
  for table in "${solution_tables[@]}"; do
    if ! [[ "${bq_tables}" =~ $table ]]; then
      if ! bq mk --table agency_dashboard."${table}" schemas/"${table}".json; then
        err "creating bigquery table ${table}"
      fi
    fi
  done

  if ! [[ "${bq_tables}" =~ "base_urls" ]]; then
    if ! bq mk --use_legacy_sql=false --view \
        "SELECT DISTINCT BaseUrl FROM \`${project_id}.agency_dashboard.ads_data\` \
         WHERE Cost > 0 \
         AND Date = (SELECT MAX(Date) FROM \`${project_id}.agency_dashboard.ads_data\`)" \
         agency_dashboard.base_urls; then
      err "creating bigquery view"
    fi
  fi
}

#######################################
# Deploys the configuration files for the solution.
#
# The dispatch rules must be deployed before the scheduler rules so that the
# controller endpoint exists.
#######################################
function deploy_config_files() {
  if ! gcloud app deploy -q queue.yaml; then
    err "deploying task queues"
  fi

  if ! gcloud app deploy -q dispatch.yaml; then
    err "deploying the dispatch rules"
  fi

  if ! gcloud app deploy -q cron.yaml; then
    err "deploying scheduled jobs"
  fi
}

function main() {
  local script_location
  local changed_dir
  script_location="${0%/*}"
  if [[ "${0}" != "${script_location}" ]] && [[ -n "${script_location}" ]]; then
    cd "${script_location}" || (echo "Could not cd to script location"; return 1)
    changed_dir=$(true)
  fi
  #get the project ID and set the default project
  read -rp 'Please enter your Google Cloud Project ID: ' project_id
  if [[ -z "$project_id" ]]; then
    echo "A project ID is required to continue." >&2
    exit 1
  fi
  if ! gcloud config set project "$project_id"; then
    err "setting the default cloud project"
  fi

  echo "Enabling Google cloud services"
  enable_gcloud_services
  echo "Deploying solution app engine services"
  deploy_solution_services
  echo "Creating bigquery tables"
  create_bq_tables
  echo "Deploying final configuration files"
  deploy_config_files

  if [[ "${changed_dir}" ]]; then
    cd - || echo "Could not change back to original dir."
  fi
}

main "$@"


