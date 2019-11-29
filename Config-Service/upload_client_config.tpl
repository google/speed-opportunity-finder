<h1>Agency Dashboard Configuration</h1>
%if defined(error)
  <span style="text-align: center;">
  <p style="color: red;">There was an error with the uploaded configuration:</p>
  <p><code>{{error}}</code></p>
  <p style="color: red;">Please try again</p>
</span>
%end
<form method="POST" enctype="multipart/form-data" action="config_upload_client">
  <h2>Please upload your client configuration JSON file</h2>
  <label>
    Select the configuration file:
    <input type="file" id="client-file-picker" name="client-config" accept=".json, application/json" required>
  </label>
  <input type="submit" value="Upload file">
</form>
