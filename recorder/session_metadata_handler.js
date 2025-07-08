// Example usage:
const express = require('express');
const app = express();
const SessionRecorder = require('./SessionRecorder');

const recorder = new SessionRecorder({
  includeHeaders: true,
  includeBody: true,
  includeCookies: true
});

// Hook the recorder into the Express server
recorder.hookIntoServer(app);

// Start recording a session
recorder.startRecording('checkout-flow-test');

// Your server routes and logic
app.get('/api/products', (req, res) => {
  res.json({ products: [/* data */] });
});

// When testing is complete
app.get('/end-recording', (req, res) => {
  const session = recorder.stopRecording();
  const sessionData = recorder.exportSession(session.id, 'json');
  res.json({ message: 'Recording stopped', sessionId: session.id });
});

app.listen(3000, () => {
  console.log('Server & recorder ready on port 3000');
});