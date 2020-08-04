<!--
 Copyright 2020 Google Inc.

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
-->

<h1 style='color: #4285f4'>Speed Opportunity Finder Configuration</h1>
% if defined('error'):
  <span style="text-align: center;">
    <p style="color: red;">There was an error with the uploaded configuration:</p>
    <p><code>{{error}}</code></p>
    <p style="color: red;">Please try again</p>
  </span>
% end
% if client_config_exists:
  <span style="text-align: center;">
    <p style="font-weight: bold">Your existing credentials will be overwritten
    when submitting this form.</p>
  </span>
% end
<form method="POST" enctype="multipart/form-data" action="config_upload_client">
  <h2>Please fill in your credentials:</h2>
  <label>Ads Management Account ID:
    <input type="text" name="mcc_id" size=15 required>
  </label>
  <br>
  <label>OAuth Client ID:
    <input type="text" name="client_id" size=75 required>
  </label>
  <br>
  <label>OAuth Client Secret:
    <input type="text" name="client_secret" size=25 required>
  </label>
  <br>
  <label>Ads Developer Token:
    <input type="text" name="developer_token" size=25 required>
  </label>
  <br>
  <label>PageSpeed Insights API Key
    <input type="text" name="psi_api_token" size="45" required>
  </label>
  <br>
  <input type="submit" value="Start OAuth Flow">
</form>
