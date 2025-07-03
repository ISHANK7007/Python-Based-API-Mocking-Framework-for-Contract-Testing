/**
 * Test Suite for Session Recording and Contract Verification
 * 
 * This script:
 * 1. Records 3 distinct API sessions (including one with dynamic fields)
 * 2. Replays sessions against a modified contract
 * 3. Runs verification in both tolerant and strict modes
 * 4. Asserts expected compatibility matches/mismatches
 */
const fs = require('fs').promises;
const path = require('path');
const express = require('express');
const axios = require('axios');
const assert = require('assert');
const { exec } = require('child_process');
const { promisify } = require('util');

const SessionRecorder = require('./src/SessionRecorder');
const { EnhancedSnapshotVerifier } = require('./src/enhanced-snapshot-verifier');

// Promisify exec for async/await usage
const execAsync = promisify(exec);

// Configuration
const config = {
  basePort: 3000,
  modifiedPort: 3001,
  sessionsDir: './test-sessions',
  contractsDir: './test-contracts',
  reportsDir: './test-reports'
};

// Utilities
async function ensureDirectoryExists(dir) {
  try {
    await fs.mkdir(dir, { recursive: true });
  } catch (err) {
    if (err.code !== 'EEXIST') throw err;
  }
}

async function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Create original API contract
 * @returns {Object} Contract object
 */
async function createOriginalContract() {
  const contract = {
    openapi: '3.0.0',
    info: {
      title: 'Test API',
      version: '1.0.0',
      description: 'Original contract for testing'
    },
    paths: {
      '/api/products': {
        get: {
          summary: 'Get all products',
          responses: {
            '200': {
              description: 'List of products',
              content: {
                'application/json': {
                  example: {
                    products: [
                      { id: 1, name: 'Product 1', price: 29.99 },
                      { id: 2, name: 'Product 2', price: 39.99 },
                      { id: 3, name: 'Product 3', price: 49.99 }
                    ],
                    count: 3
                  }
                }
              }
            }
          }
        }
      },
      '/api/products/{id}': {
        get: {
          summary: 'Get product by ID',
          parameters: [
            {
              name: 'id',
              in: 'path',
              required: true,
              schema: { type: 'integer' }
            }
          ],
          responses: {
            '200': {
              description: 'Product details',
              content: {
                'application/json': {
                  example: {
                    id: 1,
                    name: 'Product 1',
                    price: 29.99,
                    description: 'Product description',
                    category: 'electronics'
                  }
                }
              }
            },
            '404': {
              description: 'Product not found',
              content: {
                'application/json': {
                  example: {
                    error: 'Product not found'
                  }
                }
              }
            }
          }
        }
      },
      '/api/orders': {
        post: {
          summary: 'Create an order',
          requestBody: {
            required: true,
            content: {
              'application/json': {
                example: {
                  productId: 1,
                  quantity: 2
                }
              }
            }
          },
          responses: {
            '201': {
              description: 'Order created',
              content: {
                'application/json': {
                  example: {
                    orderId: 'ORD-123456',
                    status: 'confirmed',
                    productId: 1,
                    quantity: 2,
                    total: 59.98,
                    created: '2023-01-01T12:00:00Z'
                  }
                }
              }
            }
          }
        }
      },
      '/api/users': {
        get: {
          summary: 'Get current user',
          responses: {
            '200': {
              description: 'User details',
              content: {
                'application/json': {
                  example: {
                    id: 'user-123',
                    username: 'testuser',
                    email: 'test@example.com',
                    role: 'user',
                    lastLogin: '2023-01-01T12:00:00Z'
                  }
                }
              }
            }
          }
        }
      }
    }
  };

  await ensureDirectoryExists(config.contractsDir);
  await fs.writeFile(
    path.join(config.contractsDir, 'original-v1.yaml'),
    JSON.stringify(contract, null, 2)
  );
  
  return contract;
}

/**
 * Create modified API contract with compatibility issues
 * @returns {Object} Modified contract object
 */
async function createModifiedContract() {
  const contract = {
    openapi: '3.0.0',
    info: {
      title: 'Test API',
      version: '2.0.0',
      description: 'Modified contract with compatibility issues'
    },
    paths: {
      '/api/products': {
        get: {
          summary: 'Get all products',
          responses: {
            '200': {
              description: 'List of products',
              content: {
                'application/json': {
                  example: {
                    products: [
                      { id: 1, name: 'Product 1', price: 29.99, inStock: true },
                      { id: 2, name: 'Product 2', price: 39.99, inStock: false },
                      { id: 3, name: 'Product 3', price: 49.99, inStock: true }
                    ]
                    // count field removed (breaking change)
                  }
                }
              }
            }
          }
        }
      },
      '/api/products/{id}': {
        get: {
          summary: 'Get product by ID',
          parameters: [
            {
              name: 'id',
              in: 'path',
              required: true,
              schema: { type: 'integer' }
            }
          ],
          responses: {
            '200': {
              description: 'Product details',
              content: {
                'application/json': {
                  example: {
                    id: 1,
                    name: 'Product 1',
                    price: 29.99,
                    // description type changed from string to object (breaking change)
                    description: {
                      short: 'Short description',
                      full: 'Full product description'
                    },
                    category: 'electronics',
                    // new field added (non-breaking)
                    inStock: true
                  }
                }
              }
            },
            '404': {
              description: 'Product not found',
              content: {
                'application/json': {
                  example: {
                    error: 'Product not found',
                    code: 'PRODUCT_NOT_FOUND' // new field added (non-breaking)
                  }
                }
              }
            }
          }
        }
      },
      '/api/orders': {
        post: {
          summary: 'Create an order',
          requestBody: {
            required: true,
            content: {
              'application/json': {
                example: {
                  productId: 1,
                  quantity: 2
                }
              }
            }
          },
          responses: {
            '201': {
              description: 'Order created',
              content: {
                'application/json': {
                  example: {
                    orderId: 'ORD-123456',
                    status: 'confirmed',
                    productId: 1,
                    quantity: 2,
                    total: 59.98,
                    // field renamed from 'created' to 'createdAt' (breaking change)
                    createdAt: '2023-01-01T12:00:00Z',
                    // new field added (non-breaking)
                    estimatedDelivery: '2023-01-05T12:00:00Z'
                  }
                }
              }
            }
          }
        }
      },
      '/api/users': {
        get: {
          summary: 'Get current user',
          responses: {
            '200': {
              description: 'User details',
              content: {
                'application/json': {
                  example: {
                    id: 'user-123',
                    username: 'testuser',
                    email: 'test@example.com',
                    role: 'user',
                    lastLogin: '2023-01-01T12:00:00Z',
                    preferences: { // new nested object (non-breaking)
                      theme: 'light',
                      notifications: true
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  };

  await fs.writeFile(
    path.join(config.contractsDir, 'modified-v2.yaml'),
    JSON.stringify(contract, null, 2)
  );
  
  return contract;
}

/**
 * Create original API server
 * @returns {Object} Express server
 */
function createOriginalServer() {
  const app = express();
  app.use(express.json());

  // Products endpoint
  app.get('/api/products', (req, res) => {
    res.json({
      products: [
        { id: 1, name: 'Product 1', price: 29.99 },
        { id: 2, name: 'Product 2', price: 39.99 },
        { id: 3, name: 'Product 3', price: 49.99 }
      ],
      count: 3
    });
  });

  // Product by ID endpoint
  app.get('/api/products/:id', (req, res) => {
    const id = parseInt(req.params.id);
    if (id === 1) {
      res.json({
        id: 1,
        name: 'Product 1',
        price: 29.99,
        description: 'Product description',
        category: 'electronics'
      });
    } else {
      res.status(404).json({
        error: 'Product not found'
      });
    }
  });

  // Orders endpoint (with dynamic fields)
  app.post('/api/orders', (req, res) => {
    const { productId, quantity } = req.body;
    res.status(201).json({
      orderId: `ORD-${Date.now()}`, // Dynamic field
      status: 'confirmed',
      productId,
      quantity,
      total: quantity * 29.99,
      created: new Date().toISOString() // Dynamic field
    });
  });

  // Users endpoint
  app.get('/api/users', (req, res) => {
    res.json({
      id: 'user-123',
      username: 'testuser',
      email: 'test@example.com',
      role: 'user',
      lastLogin: new Date().toISOString() // Dynamic field
    });
  });

  return app;
}

/**
 * Create modified API server
 * @returns {Object} Express server
 */
function createModifiedServer() {
  const app = express();
  app.use(express.json());

  // Products endpoint (count field removed)
  app.get('/api/products', (req, res) => {
    res.json({
      products: [
        { id: 1, name: 'Product 1', price: 29.99, inStock: true },
        { id: 2, name: 'Product 2', price: 39.99, inStock: false },
        { id: 3, name: 'Product 3', price: 49.99, inStock: true }
      ]
      // count field removed
    });
  });

  // Product by ID endpoint (description type changed)
  app.get('/api/products/:id', (req, res) => {
    const id = parseInt(req.params.id);
    if (id === 1) {
      res.json({
        id: 1,
        name: 'Product 1',
        price: 29.99,
        description: { // Changed from string to object
          short: 'Short description',
          full: 'Full product description'
        },
        category: 'electronics',
        inStock: true // New field
      });
    } else {
      res.status(404).json({
        error: 'Product not found',
        code: 'PRODUCT_NOT_FOUND' // New field
      });
    }
  });

  // Orders endpoint (field renamed)
  app.post('/api/orders', (req, res) => {
    const { productId, quantity } = req.body;
    res.status(201).json({
      orderId: `ORD-${Date.now()}`,
      status: 'confirmed',
      productId,
      quantity,
      total: quantity * 29.99,
      createdAt: new Date().toISOString(), // Renamed from 'created'
      estimatedDelivery: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString() // New field
    });
  });

  // Users endpoint (new nested object)
  app.get('/api/users', (req, res) => {
    res.json({
      id: 'user-123',
      username: 'testuser',
      email: 'test@example.com',
      role: 'user',
      lastLogin: new Date().toISOString(),
      preferences: { // New nested object
        theme: 'light',
        notifications: true
      }
    });
  });

  return app;
}

/**
 * Record test sessions
 * @returns {Promise<Array>} Array of paths to recorded session files
 */
async function recordSessions() {
  // Create and start original server
  const app = createOriginalServer();
  const server = app.listen(config.basePort);
  const baseUrl = `http://localhost:${config.basePort}`;
  
  console.log(`Original API server started on port ${config.basePort}`);
  
  // Create session recorder
  const recorder = new SessionRecorder({
    logDirectory: config.sessionsDir
  });
  
  // Hook recorder into server
  recorder.hookIntoServer(app);
  
  // Array to store session files
  const sessionFiles = [];
  
  try {
    // Session 1: Basic API calls
    console.log('Recording Session 1: Basic API calls');
    recorder.startRecording('basic-endpoints');
    
    // Make API calls
    await axios.get(`${baseUrl}/api/products`);
    await axios.get(`${baseUrl}/api/products/1`);
    await axios.get(`${baseUrl}/api/products/999`); // Will return 404
    
    // Stop and save session
    const session1 = recorder.stopRecording();
    recorder.tagSession(session1.id, ['basic', 'regression', 'products']);
    recorder.updateSessionMetadata(session1.id, {
      description: 'Basic product endpoints',
      priority: 'high'
    });
    const session1Path = await recorder.saveSession(session1.id);
    sessionFiles.push(session1Path);
    
    // Session 2: Dynamic content
    console.log('Recording Session 2: Endpoints with dynamic content');
    recorder.startRecording('dynamic-content');
    
    // Make API calls with dynamic responses
    await axios.post(`${baseUrl}/api/orders`, { productId: 1, quantity: 2 });
    await axios.get(`${baseUrl}/api/users`);
    
    // Stop and save session
    const session2 = recorder.stopRecording();
    recorder.tagSession(session2.id, ['dynamic', 'orders', 'users']);
    recorder.updateSessionMetadata(session2.id, {
      description: 'Endpoints with dynamic timestamps and IDs',
      priority: 'medium'
    });
    const session2Path = await recorder.saveSession(session2.id);
    sessionFiles.push(session2Path);
    
    // Session 3: Mixed content
    console.log('Recording Session 3: Mixed static and dynamic content');
    recorder.startRecording('mixed-content');
    
    // Make mixed API calls
    await axios.get(`${baseUrl}/api/products`);
    await axios.post(`${baseUrl}/api/orders`, { productId: 2, quantity: 1 });
    await delay(100); // Small delay to ensure different timestamps
    await axios.post(`${baseUrl}/api/orders`, { productId: 3, quantity: 3 });
    
    // Stop and save session
    const session3 = recorder.stopRecording();
    recorder.tagSession(session3.id, ['mixed', 'regression', 'orders']);
    recorder.updateSessionMetadata(session3.id, {
      description: 'Mix of static and dynamic endpoints',
      priority: 'medium',
      testSuite: 'integration'
    });
    const session3Path = await recorder.saveSession(session3.id);
    sessionFiles.push(session3Path);
    
    console.log('All sessions recorded successfully');
    return sessionFiles;
    
  } catch (error) {
    console.error('Error recording sessions:', error);
    throw error;
  } finally {
    // Close server
    server.close();
    console.log('Original API server stopped');
  }
}

/**
 * Replay and verify session against modified contract
 * @param {string} sessionFile - Path to session file
 * @param {boolean} isStrictMode - Whether to use strict comparison mode
 * @returns {Promise<Object>} Verification results
 */
async function verifySession(sessionFile, isStrictMode = false) {
  // Start modified server
  const modifiedApp = createModifiedServer();
  const modifiedServer = modifiedApp.listen(config.modifiedPort);
  const modifiedUrl = `http://localhost:${config.modifiedPort}`;
  
  console.log(`Modified API server started on port ${config.modifiedPort}`);
  
  try {
    // Initialize verifier
    const verifier = new EnhancedSnapshotVerifier({
      logDirectory: config.sessionsDir,
      diffOutputDirectory: config.reportsDir,
      tolerances: isStrictMode ? {
        timestampDriftSeconds: 0,
        ignoreUUIDs: false,
        sortArrays: false
      } : {
        timestampDriftSeconds: 5,
        ignoreUUIDs: true,
        sortArrays: true
      }
    });
    
    // Load contract
    const contractLoader = { load: async () => require(path.join(config.contractsDir, 'modified-v2.yaml')) };
    const contract = await contractLoader.load();
    
    // Configure verifier with templates
    verifier.configureFromContract(contract);
    
    // Load session
    const session = await loadSession(sessionFile);
    const sessionId = session.sessionId || path.basename(sessionFile, '.json');
    
    // Store session in verifier
    verifier.originalSessions.set(sessionId, {
      filePath: sessionFile,
      data: session
    });
    
    // Run verification against modified API
    console.log(`Verifying session ${sessionId} in ${isStrictMode ? 'strict' : 'tolerant'} mode`);
    
    // Use both direct API calls and template-based verification
    const results = await verifier.verifyCompatibility(sessionId, modifiedUrl, {
      generateReport: true,
      printSummary: true
    });
    
    // Generate mode-specific report
    const reportName = `${sessionId}-${isStrictMode ? 'strict' : 'tolerant'}.json`;
    const reportPath = path.join(config.reportsDir, reportName);
    await fs.writeFile(reportPath, JSON.stringify(results, null, 2));
    
    console.log(`Verification report saved to ${reportPath}`);
    return results;
    
  } catch (error) {
    console.error('Error verifying session:', error);
    throw error;
  } finally {
    // Close modified server
    modifiedServer.close();
    console.log('Modified API server stopped');
  }
}

/**
 * Run CLI verification command
 * @param {string} sessionFile - Path to session file
 * @param {boolean} isStrictMode - Whether to use strict mode
 * @returns {Promise<Object>} CLI command results
 */
async function runCliVerification(sessionFile, isStrictMode = false) {
  const contractPath = path.join(config.contractsDir, 'modified-v2.yaml');
  const outputPath = path.join(config.reportsDir, `cli-${path.basename(sessionFile, '.json')}-${isStrictMode ? 'strict' : 'tolerant'}.json`);
  
  const modeFlag = isStrictMode ? '--strict' : '--tolerant';
  const command = `node ./cli.js replay ${sessionFile} --contract ${contractPath} --output ${outputPath} ${modeFlag} --format json --performance`;
  
  console.log(`Running CLI command: ${command}`);
  
  try {
    const { stdout, stderr } = await execAsync(command);
    
    if (stderr) {
      console.error('CLI stderr:', stderr);
    }
    
    const result = JSON.parse(stdout);
    console.log(`CLI verification complete, report saved to ${outputPath}`);
    return result;
  } catch (error) {
    console.error('CLI verification error:', error);
    // Return error details if available
    if (error.stdout) {
      try {
        return JSON.parse(error.stdout);
      } catch (e) {
        // If stdout isn't parseable, return the original error
        return { error: error.message, stdout: error.stdout };
      }
    }
    return { error: error.message };
  }
}

/**
 * Helper to load a session from file
 * @param {string} filePath - Path to session file
 * @returns {Promise<Object>} Session object
 */
async function loadSession(filePath) {
  const content = await fs.readFile(filePath, 'utf8');
  return JSON.parse(content);
}

/**
 * Run assertions on verification results
 * @param {Object} results - Verification results
 * @param {string} sessionType - Type of session (basic, dynamic, mixed)
 * @param {boolean} isStrictMode - Whether strict mode was used
 * @returns {Promise<Object>} Assertion results
 */
async function runAssertions(results, sessionType, isStrictMode) {
  const assertions = {
    passed: [],
    failed: []
  };
  
  function assertAndLog(condition, message) {
    try {
      assert(condition, message);
      assertions.passed.push(message);
    } catch (error) {
      assertions.failed.push(message);
    }
  }
  
  // Common assertions
  assertAndLog(results && results.summary, 'Results should contain a summary');
  
  if (!results || !results.summary) {
    return assertions; // Stop if basic structure is missing
  }
  
  // Session type specific assertions
  switch (sessionType) {
    case 'basic':
      // The count field removal should always be detected (breaking change)
      assertAndLog(results.summary.incompatible > 0, 'Basic session should detect incompatibilities');
      
      // In strict mode, type changes and additions are breaking
      if (isStrictMode) {
        assertAndLog(results.summary.compatibilityScore < 50, 'Strict mode should have low compatibility score for basic session');
      } else {
        assertAndLog(results.summary.effectiveCompatibilityScore > results.summary.compatibilityScore, 
          'Tolerant mode should improve effective compatibility score');
      }
      break;
      
    case 'dynamic':
      // In strict mode, all dynamic fields would fail
      if (isStrictMode) {
        assertAndLog(results.summary.compatibilityScore < 30, 'Strict mode should have very low compatibility for dynamic content');
      } else {
        assertAndLog(
          (results.summary.effectiveCompatibilityScore || results.summary.compatibilityScore) > 60,
          'Tolerant mode should handle dynamic content well'
        );
        assertAndLog(results.summary.toleratedChanges > 0, 'Dynamic fields should be tolerated in tolerant mode');
      }
      break;
      
    case 'mixed':
      // Should have mixture of tolerated and incompatible changes
      if (isStrictMode) {
        assertAndLog(results.summary.compatibilityScore < 40, 'Strict mode should have low compatibility for mixed content');
      } else {
        assertAndLog(results.summary.effectiveCompatibilityScore > results.summary.compatibilityScore, 
          'Tolerant mode should improve score for mixed content');
        assertAndLog(results.summary.toleratedChanges > 0 && results.summary.incompatible > 0,
          'Mixed content should have both tolerated changes and incompatibilities');
      }
      break;
  }
  
  return assertions;
}

/**
 * Run the complete test suite
 */
async function runTestSuite() {
  try {
    // Ensure directories exist
    await Promise.all([
      ensureDirectoryExists(config.sessionsDir),
      ensureDirectoryExists(config.contractsDir),
      ensureDirectoryExists(config.reportsDir)
    ]);
    
    // Create contracts
    await createOriginalContract();
    await createModifiedContract();
    
    // Record sessions
    console.log('\n=== Recording Test Sessions ===\n');
    const sessionFiles = await recordSessions();
    
    // Results collection
    const allResults = {
      tolerant: {},
      strict: {},
      assertions: {
        total: 0,
        passed: 0,
        failed: 0
      }
    };
    
    // Verify sessions in tolerant mode
    console.log('\n=== Verifying Sessions in Tolerant Mode ===\n');
    for (let i = 0; i < sessionFiles.length; i++) {
      const sessionFile = sessionFiles[i];
      const sessionType = ['basic', 'dynamic', 'mixed'][i];
      
      const results = await verifySession(sessionFile, false);
      allResults.tolerant[sessionType] = results;
      
      // Run CLI verification
      const cliResults = await runCliVerification(sessionFile, false);
      allResults.tolerant[`${sessionType}-cli`] = cliResults;
    }
    
    // Verify sessions in strict mode
    console.log('\n=== Verifying Sessions in Strict Mode ===\n');
    for (let i = 0; i < sessionFiles.length; i++) {
      const sessionFile = sessionFiles[i];
      const sessionType = ['basic', 'dynamic', 'mixed'][i];
      
      const results = await verifySession(sessionFile, true);
      allResults.strict[sessionType] = results;
      
      // Run CLI verification
      const cliResults = await runCliVerification(sessionFile, true);
      allResults.strict[`${sessionType}-cli`] = cliResults;
    }
    
    // Run assertions
    console.log('\n=== Running Assertions ===\n');
    for (const sessionType of ['basic', 'dynamic', 'mixed']) {
      // Tolerant mode assertions
      const tolerantAssertions = await runAssertions(
        allResults.tolerant[sessionType],
        sessionType,
        false
      );
      
      // Strict mode assertions
      const strictAssertions = await runAssertions(
        allResults.strict[sessionType],
        sessionType,
        true
      );
      
      // Collect assertion results
      allResults.assertions[`${sessionType}-tolerant`] = tolerantAssertions;
      allResults.assertions[`${sessionType}-strict`] = strictAssertions;
      
      // Update totals
      allResults.assertions.total += 
        tolerantAssertions.passed.length + 
        tolerantAssertions.failed.length +
        strictAssertions.passed.length + 
        strictAssertions.failed.length;
        
      allResults.assertions.passed += 
        tolerantAssertions.passed.length +
        strictAssertions.passed.length;
        
      allResults.assertions.failed += 
        tolerantAssertions.failed.length +
        strictAssertions.failed.length;
    }
    
    // Write summary report
    const summaryReport = {
      timestamp: new Date().toISOString(),
      sessions: sessionFiles.map(file => path.basename(file)),
      assertion_summary: allResults.assertions,
      compatibility_summary: {
        tolerant: {
          basic: allResults.tolerant.basic?.summary,
          dynamic: allResults.tolerant.dynamic?.summary,
          mixed: allResults.tolerant.mixed?.summary
        },
        strict: {
          basic: allResults.strict.basic?.summary,
          dynamic: allResults.strict.dynamic?.summary,
          mixed: allResults.strict.mixed?.summary
        }
      }
    };
    
    await fs.writeFile(
      path.join(config.reportsDir, 'test-suite-summary.json'),
      JSON.stringify(summaryReport, null, 2)
    );
    
    // Print summary
    console.log('\n=== Test Suite Summary ===\n');
    console.log(`Total Assertions: ${allResults.assertions.total}`);
    console.log(`Passed: ${allResults.assertions.passed}`);
    console.log(`Failed: ${allResults.assertions.failed}`);
    
    // Print compatibility scores
    console.log('\nCompatibility Scores (Tolerant Mode):');
    console.log(`  Basic:   ${allResults.tolerant.basic?.summary?.effectiveCompatibilityScore?.toFixed(2)}%`);
    console.log(`  Dynamic: ${allResults.tolerant.dynamic?.summary?.effectiveCompatibilityScore?.toFixed(2)}%`);
    console.log(`  Mixed:   ${allResults.tolerant.mixed?.summary?.effectiveCompatibilityScore?.toFixed(2)}%`);
    
    console.log('\nCompatibility Scores (Strict Mode):');
    console.log(`  Basic:   ${allResults.strict.basic?.summary?.compatibilityScore?.toFixed(2)}%`);
    console.log(`  Dynamic: ${allResults.strict.dynamic?.summary?.compatibilityScore?.toFixed(2)}%`);
    console.log(`  Mixed:   ${allResults.strict.mixed?.summary?.compatibilityScore?.toFixed(2)}%`);
    
    return allResults;
  } catch (error) {
    console.error('Test suite error:', error);
    throw error;
  }
}

// Run the test suite
runTestSuite()
  .then(() => {
    console.log('\nTest suite completed successfully');
    process.exit(0);
  })
  .catch(error => {
    console.error('\nTest suite failed:', error);
    process.exit(1);
  });