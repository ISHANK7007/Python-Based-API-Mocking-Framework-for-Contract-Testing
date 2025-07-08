const express = require('express');
const bodyParser = require('body-parser');
const SessionRecorder = require('./SessionRecorder');
const SnapshotVerifier = require('./SnapshotVerifier');

// Create a function to set up and record API interactions
async function recordSessions() {
  // Create Express app for the base version
  const app = express();
  app.use(bodyParser.json());
  
  // Initialize the recorder
  const recorder = new SessionRecorder({
    logDirectory: './session-logs'
  });
  
  // Hook recorder into the server
  recorder.hookIntoServer(app);
  
  // Set up API routes for v1
  app.get('/api/products', (req, res) => {
    const products = [
      { id: 1, name: 'Product 1', price: 29.99, category: 'electronics' },
      { id: 2, name: 'Product 2', price: 39.99, category: 'electronics' },
      { id: 3, name: 'Product 3', price: 49.99, category: 'home' }
    ];
    res.json({ products, count: products.length });
  });
  
  app.get('/api/products/:id', (req, res) => {
    const id = parseInt(req.params.id);
    if (id === 1) {
      res.json({ 
        id: 1, 
        name: 'Product 1', 
        price: 29.99, 
        category: 'electronics',
        description: 'This is product 1'
      });
    } else {
      res.status(404).json({ error: 'Product not found' });
    }
  });
  
  app.post('/api/orders', (req, res) => {
    const { productId, quantity } = req.body;
    res.json({
      orderId: `ORD-${Date.now()}`,
      status: 'confirmed',
      productId,
      quantity,
      total: quantity * 29.99,
      created: new Date().toISOString()
    });
  });
  
  // Start the server
  const server = app.listen(3000, () => {
    console.log('Base version API running on port 3000');
  });
  
  // Start recording a session
  recorder.startRecording('product-api-v1');
  
  // Simulate API calls
  console.log('Making API calls...');
  
  // ... make API calls here using axios or fetch ...
  
  // Stop recording and save session
  const session = recorder.stopRecording();
  const filePath = await recorder.saveSession(session.id);
  console.log(`Session recorded and saved to ${filePath}`);
  
  // Shut down server after recording
  server.close();
  
  return filePath;
}

// Function to set up a 'new version' of the API for testing
function createNewVersionApi() {
  const app = express();
  app.use(bodyParser.json());
  
  // Set up API routes for v2 (with some changes)
  app.get('/api/products', (req, res) => {
    const products = [
      { id: 1, name: 'Product 1', price: 29.99, category: 'electronics', inStock: true },
      { id: 2, name: 'Product 2', price: 39.99, category: 'electronics', inStock: false },
      { id: 3, name: 'Product 3', price: 49.99, category: 'home', inStock: true },
      { id: 4, name: 'Product 4', price: 59.99, category: 'home', inStock: true }
    ];
    // Removed count field (breaking change)
    res.json({ products });
  });
  
  app.get('/api/products/:id', (req, res) => {
    const id = parseInt(req.params.id);
    if (id === 1) {
      res.json({ 
        id: 1, 
        name: 'Product 1', 
        price: 29.99, 
        category: 'electronics',
        // Changed type of description (breaking change)
        description: { short: 'This is product 1', long: 'Detailed description...' },
        inStock: true
      });
    } else {
      // Changed status code (breaking change)
      res.status(400).json({ error: 'Invalid product ID', code: 'INVALID_ID' });
    }
  });
  
  app.post('/api/orders', (req, res) => {
    const { productId, quantity } = req.body;
    res.json({
      orderId: `ORD-${Date.now()}`,
      status: 'confirmed',
      productId,
      quantity,
      total: quantity * 29.99,
      // Renamed field from 'created' to 'createdAt' (breaking change)
      createdAt: new Date().toISOString(),
      // Added new field (non-breaking)
      estimatedDelivery: '2023-12-25'
    });
  });
  
  return app.listen(3001, () => {
    console.log('New version API running on port 3001');
  });
}

// Main verification function
async function verifyApiCompatibility() {
  try {
    // Record sessions with the base version
    const sessionFilePath = await recordSessions();
    
    // Start the new version of the API
    const newVersionServer = createNewVersionApi();
    
    // Initialize the verifier
    const verifier = new SnapshotVerifier({
      logDirectory: './session-logs',
      diffOutputDirectory: './diff-reports'
    });
    
    // Load all sessions (or you could load specific ones)
    const sessionIds = await verifier.loadAllSessions();
    
    // Verify compatibility
    const targetBaseUrl = 'http://localhost:3001';
    const results = await verifier.batchVerify(sessionIds, targetBaseUrl, {
      threshold: 90, // Allow 10% differences
      printBatchSummary: true
    });
    
    // Individual detailed analysis
    if (sessionIds.length > 0) {
      console.log('\nDetailed analysis of first session:');
      await verifier.verifyCompatibility(sessionIds[0], targetBaseUrl, {
        generateReport: true,
        printSummary: true
      });
    }
    
    // Shutdown new version server
    newVersionServer.close();
    
    return results;
  } catch (error) {
    console.error('Error verifying API compatibility:', error);
    throw error;
  }
}

// Run the verification
verifyApiCompatibility()
  .then(results => {
    console.log('Verification complete');
    process.exit(0);
  })
  .catch(error => {
    console.error('Verification failed:', error);
    process.exit(1);
  });