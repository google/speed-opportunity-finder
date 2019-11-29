/**
 * @fileoverview Description of this file.
 */
'use strict';

const express = require('express');

const app = express();

app.all(/.*/, (req, res) => {
  res.status(200)
      .send('This is not the app you were looking for.')
      .end();
});

const PORT = process.env.PORT || 8081;
app.listen(PORT, () => {
  console.log(`Default app listening on port ${PORT}`);
});

module.exports = app;
