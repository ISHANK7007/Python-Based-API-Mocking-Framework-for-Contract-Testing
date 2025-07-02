const fs = require('fs').promises;
const express = require('express');
const bodyParser = require('body-parser');
const { 
  ResponseTemplate, 
  ResponseResolver, 
  EnhancedSnapshotVerifier 
} = require('./enhanced-snapshot-verifier');

// Example templates for various endpoints
const templates = {
  // Template for products listing
  '/api/products': {
    products: [
      { 
        id: "{{uuid}}", 
        name: "Product 1", 
        price: "{{random 10 100}}.99", 
        inStock: true 
      },
      { 
        id: "{{uuid}}", 
        name: "Product 2", 
        price: "{{random 20 200}}.99", 
        inStock: "{{#if_eq (random 0 1) 1}}true{{else}}false{{/if_eq}}" 
      },
      { 
        id: "{{uuid}}", 
        name: "Product 3", 
        price: "{{random 30 300}}.99", 
        inStock: true 
      }
    ],
    count: 3,
    timestamp: "{{now}}"
  },
  
  // Template for single product
  '/api/products/:id': {
    id: "{{request.params.id}}",
    name: "Product {{request.params.id}}",
    price: "{{random 10 100}}.99",
    description: "This is product {{request.params.id}}",
    category: "electronics",
    inStock: true,
    lastUpdated: "{{now}}"
  },
  
  // Template for order creation
  '/api/orders': {
    orderId: "ORD-{{timestamp}}",
    status: "confirmed",
    productId: "{{request.body.productId}}",
    quantity: "{{request.body.quantity}}",
    total: "{{multiply request.body.quantity 29.99}}",
    createdAt: "{{now}}",
    estimatedDelivery: "{{addDays (now) 5}}",
    trackingId: "{{uuid}}"
  }
};

// Custom helper functions
const helpers = {
  multiply: (a, b) => a * b,
  addDays: (date, days) => {
    const d = new Date(date);
    d.setDate(d.getDate() + parseInt(days));
    return d.toISOString();
  }
};

// Main execution function
async function runVerificationWithTemplates() {
  // Load a session to verify
  const verifier = new EnhancedSnapshotVerifier({
    logDirectory: './session-logs',
    diffOutputDirectory: './diff-reports',
    useDynamicResponses: true,  // Enable dynamic responses by default
    tolerances: {
      timestampDriftSeconds: 5,
      ignoreUUIDs: true,
      sortArrays: true
    }
  });
  
  // Register custom helper functions
  Object.entries(helpers).forEach(([name, fn]) => {
    verifier.responseResolver.routeTemplates.forEach(route => {
      route.template.registerHelper(name, fn);
    });
  });
  
  // Load sessions
  const sessionIds = await verifier.loadAllSessions();
  
  if (sessionIds.length === 0) {
    console.log('No sessions found. Recording a sample session...');
    await recordSampleSession();
    // Reload sessions
    await verifier.loadAllSessions();
  }
  
  const sessionId = sessionIds[0];
  console.log(`Verifying session: ${sessionId}`);
  
  // First, run verification against real API without templates
  console.log('\n=== Verification Against Real API ===');
  const realResults = await verifier.verifyCompatibility(sessionId, 'http://localhost:3001', {
    useDynamicResponses: false
  });
  
  // Now, run verification using templates
  console.log('\n=== Verification Using Templates ===');
  const templateResults = await verifier.replayWithTemplates(sessionId, templates, {
    targetBaseUrl: 'http://localhost:3001'
  });
  
  // Compare the results
  console.log('\n=== Comparison of Results ===');
  console.log(`Real API Compatibility Score: ${realResults.compatibilityScore.toFixed(2)}%`);
  console.log(`Template-based Compatibility Score: ${templateResults.summary.compatibilityScore.toFixed(2)}%`);
  
  return {
    realResults,
    templateResults
  };
}

// Function to record a sample session for testing
async function recordSampleSession() {
  const SessionRecorder = require('./SessionRecorder');
  
  // Create Express app for testing
  const app = express();
  app.use(bodyParser.json());
  
  // Initialize recorder
  const recorder = new SessionRecorder({
    logDirectory: './session-logs'
  });
  
  // Hook recorder into server
  recorder.hookIntoServer(app);
  
  // Set up some test routes
  app.get('/api/products', (req, res) => {
    res.json({
      products: [
        { id: '1', name: 'Product 1', price: 29.99, inStock: true },
        { id: '2', name: 'Product 2', price: 39.99, inStock: false },
        { id: '3', name: 'Product 3', price: 49.99, inStock: true }
      ],
      count: 3,
      timestamp: new Date().toISOString()
    });
  });
  
  app.get('/api/products/:id', (req, res) => {
    res.json({
      id: req.params.id,
      name: `Product ${req.params.id}`,
      price: 29.99,
      description: `This is product ${req.params.id}`,
      category: 'electronics',
      inStock: true,
      lastUpdated: new Date().toISOString()
    });
  });
  
  app.post('/api/orders', (req, res) => {
    const { productId, quantity } = req.body;
    res.json({
      orderId: `ORD-${Date.now()}`,
      status: 'confirmed',
      productId,
      quantity,
      total: quantity * 29.99,
      createdAt: new Date().toISOString(),
      estimatedDelivery: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
      trackingId: `TRK-${Math.random().toString(36).substring(2, 10)}`
    });
  });
  
  // Start server
  const server = app.listen(3000, () => {
    console.log('Server for recording started on port 3000');
  });
  
  // Start recording
  recorder.startRecording('test-session');
  
  // Make API calls
  const axios = require('axios');
  
  try {
    // Get product list
    await axios.get('http://localhost:3000/api/products');
    
    // Get specific product
    await axios.get('http://localhost:3000/api/products/1');
    
    // Create order
    await axios.post('http://localhost:3000/api/orders', {
      productId: '1',
      quantity: 2
    });
    
    // Stop recording and save
    const session = recorder.stopRecording();
    await recorder.saveSession(session.id);
    console.log(`Recorded session: ${session.id}`);
  } catch (error) {
    console.error('Error making API calls:', error);
  } finally {
    // Close server
    server.close();
  }
}

// Start a "new version" API server for testing
function startNewVersionServer() {
  const app = express();
  app.use(bodyParser.json());
  
  // Set up routes with slight differences
  app.get('/api/products', (req, res) => {
    res.json({
      products: [
        { id: '1', name: 'Product 1 (New)', price: 29.99, inStock: true },
        { id: '2', name: 'Product 2 (New)', price: 39.99, inStock: false },
        { id: '3', name: 'Product 3 (New)', price: 49.99, inStock: true },
        { id: '4', name: 'Product 4 (New)', price: 59.99, inStock: true }
      ],
      // Removed the count field (breaking change)
      timestamp: new Date().toISOString()
    });
  });
  
  // Start server
  return app.listen(3001, () => {
    console.log('New version server started on port 3001');
  });
}

// Main function
async function main() {
  // Start the "new version" server
  const newServer = startNewVersionServer();
  
  try {
    // Run verification
    await runVerificationWithTemplates();
  } catch (error) {
    console.error('Verification failed:', error);
  } finally {
    // Shut down new server
    newServer.close();
  }
}

// Run the example
main().catch(console.error);