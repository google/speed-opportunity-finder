<h1>Agency Dashboard Configuration</h1>
%if defined(error)
  <span style="text-align: center;">
    <p style="color: red;">There was an error with the uploaded configuration:</p>
    <p><code>{{error}}</code></p>
    <p style="color: red;">Please try again</p>
  </span>
%end
%if client_config_exists
  <span style="text-align: center;">
    <p style="font-weight: bold">Your existing credentials will be overwritten
    when submitting this form.</p>
  </span>
%end
<form method="POST" enctype="multipart/form-data" action="config_upload_client">
  <h2>Please fill in your credentials:</h2>
  <label>Management Account ID: <input type="text" id="mcc_id" required></label>
  <label>Client ID: <input type="text" id="client_id" required></label>
  <label>Client Secret: <input type="text" id="client_secret" required></label>
  <input type="submit" value="Start OAuth Flow">
</form>
