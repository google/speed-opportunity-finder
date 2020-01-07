<h1>Agency Dashboard Configuration</h1>
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
  <label>Management Account ID: 
    <input type="text" name="mcc_id" size=15 required>
  </label>
  <br>
  <label>Client ID:
    <input type="text" name="client_id" size=75 required>
  </label>
  <br>
  <label>Client Secret: 
    <input type="text" name="client_secret" size=25 required>
  </label>
  <br>
  <label>Developer Token:
    <input type="text" name="developer_token" size=25 required>
  </label>
  <br>
  <input type="submit" value="Start OAuth Flow">
</form>
