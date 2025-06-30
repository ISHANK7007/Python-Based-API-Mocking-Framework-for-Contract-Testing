const crypto = require('crypto');
const fs = require('fs').promises;
const path = require('path');

class SessionRecorder {
  constructor(options = {}) {
    this.sessions = [];
    this.currentSession = null;
    this.isRecording = false;
    this.options = {
      includeHeaders: true,
      includeBody: true,
      logDirectory: './session-logs',
      sensitiveHeaders: ['authorization', 'cookie', 'set-cookie'],
      sensitiveFields: ['password', 'token', 'secret', 'key', 'authorization'],
      ...options
    };
    
    // Ensure log directory exists
    this.ensureLogDirectory();
  }

  async ensureLogDirectory() {
    try {
      await fs.mkdir(this.options.logDirectory, { recursive: true });
    } catch (error) {
      console.error('Failed to create log directory:', error);
    }
  }

  startRecording(sessionName = `session-${Date.now()}`) {
    if (this.isRecording) {
      console.warn('A recording session is already in progress');
      return false;
    }

    const timestamp = new Date();
    this.currentSession = {
      id: sessionName,
      startTime: timestamp,
      timestamp: timestamp.toISOString(),
      interactions: [],
      metadata: {
        userAgent: this.getUserAgent(),
        environment: process.env.NODE_ENV || 'development'
      }
    };
    
    this.isRecording = true;
    console.log(`Started recording session: ${sessionName}`);
    return true;
  }

  stopRecording() {
    if (!this.isRecording) {
      console.warn('No recording session is in progress');
      return null;
    }

    this.currentSession.endTime = new Date();
    this.currentSession.duration = 
      this.currentSession.endTime - this.currentSession.startTime;
    
    this.sessions.push(this.currentSession);
    
    const completedSession = {...this.currentSession};
    this.currentSession = null;
    this.isRecording = false;
    
    console.log(`Stopped recording session: ${completedSession.id}`);
    return completedSession;
  }

  recordInteraction(req, res) {
    if (!this.isRecording || !this.currentSession) {
      return false;
    }

    const timestamp = new Date();
    
    // Capture request and response data
    const request = this.captureRequest(req);
    const response = this.captureResponse(res);
    
    // Generate content hash for request (used for matching during replay)
    const requestHash = this.generateContentHash({
      method: request.method,
      path: request.path,
      query: request.query,
      body: request.body
    });
    
    const interaction = {
      timestamp: timestamp.toISOString(),
      requestHash,
      request,
      response,
      duration: res.duration || null
    };

    this.currentSession.interactions.push(interaction);
    return true;
  }

  captureRequest(req) {
    const requestData = {
      method: req.method,
      path: req.path,
      query: req.query || {},
    };

    if (this.options.includeHeaders) {
      requestData.headers = this.filterSensitiveHeaders(req.headers);
    }

    if (this.options.includeBody && req.body) {
      requestData.body = this.sanitizeData(req.body);
    }

    return requestData;
  }

  captureResponse(res) {
    const responseData = {
      statusCode: res.statusCode,
      statusMessage: res.statusMessage
    };

    if (this.options.includeHeaders) {
      responseData.headers = res.getHeaders ? res.getHeaders() : res.headers;
    }

    if (this.options.includeBody && res.body) {
      responseData.body = res.body;
    }

    return responseData;
  }

  getUserAgent() {
    try {
      // This would depend on how the request object is accessed
      return 'Recorded Session';
    } catch (err) {
      return 'Unknown';
    }
  }

  filterSensitiveHeaders(headers) {
    const filteredHeaders = {...headers};
    
    this.options.sensitiveHeaders.forEach(header => {
      if (filteredHeaders[header]) {
        filteredHeaders[header] = '[REDACTED]';
      }
    });
    
    return filteredHeaders;
  }

  sanitizeData(data) {
    // Deep clone to avoid modifying the original data
    const clonedData = JSON.parse(JSON.stringify(data));
    
    const recursiveSanitize = (obj) => {
      if (!obj || typeof obj !== 'object') return;
      
      Object.keys(obj).forEach(key => {
        if (this.options.sensitiveFields.some(field => key.toLowerCase().includes(field))) {
          obj[key] = '[REDACTED]';
        } else if (typeof obj[key] === 'object') {
          recursiveSanitize(obj[key]);
        }
      });
    };
    
    recursiveSanitize(clonedData);
    return clonedData;
  }

  /**
   * Generate a deterministic content hash from request data
   * This is used for matching during replay
   */
  generateContentHash(data) {
    const stringified = typeof data === 'string' 
      ? data 
      : JSON.stringify(this.normalizeForHashing(data));
    
    return crypto
      .createHash('sha256')
      .update(stringified)
      .digest('hex');
  }

  /**
   * Normalize data for consistent hashing
   * Ensures objects with the same properties but different order generate the same hash
   */
  normalizeForHashing(data) {
    if (Array.isArray(data)) {
      return data.map(item => this.normalizeForHashing(item));
    }
    
    if (data !== null && typeof data === 'object') {
      const normalized = {};
      Object.keys(data).sort().forEach(key => {
        normalized[key] = this.normalizeForHashing(data[key]);
      });
      return normalized;
    }
    
    return data;
  }

  /**
   * Save session data to disk
   * @param {string} sessionId - ID of the session to save
   * @returns {Promise<string>} Path to the saved session file
   */
  async saveSession(sessionId) {
    const session = this.sessions.find(s => s.id === sessionId) || 
                    (this.currentSession && this.currentSession.id === sessionId ? 
                     this.currentSession : null);
    
    if (!session) {
      throw new Error(`Session with ID ${sessionId} not found`);
    }
    
    // Create filename based on timestamp
    const timestamp = new Date(session.startTime).getTime();
    const filename = `session_${timestamp}.json`;
    const filePath = path.join(this.options.logDirectory, filename);
    
    // Prepare the session data according to our defined format
    const sessionData = {
      sessionId: session.id,
      timestamp: session.timestamp,
      metadata: session.metadata,
      interactions: session.interactions.map(interaction => ({
        timestamp: interaction.timestamp,
        requestHash: interaction.requestHash,
        request: {
          method: interaction.request.method,
          path: interaction.request.path,
          headers: interaction.request.headers,
          query: interaction.request.query,
          body: interaction.request.body
        },
        response: {
          statusCode: interaction.response.statusCode,
          headers: interaction.response.headers,
          body: interaction.response.body
        }
      }))
    };
    
    try {
      await fs.writeFile(filePath, JSON.stringify(sessionData, null, 2));
      console.log(`Session saved to ${filePath}`);
      return filePath;
    } catch (error) {
      console.error('Failed to save session:', error);
      throw error;
    }
  }

  /**
   * Load a session from disk
   * @param {string} filePath - Path to a session file
   * @returns {Promise<Object>} The loaded session data
   */
  async loadSession(filePath) {
    try {
      const data = await fs.readFile(filePath, 'utf8');
      const session = JSON.parse(data);
      return session;
    } catch (error) {
      console.error('Failed to load session:', error);
      throw error;
    }
  }

  /**
   * Find a matching response for a given request using content hashes
   * @param {Object} session - The session data
   * @param {Object} request - The request to match
   * @returns {Object|null} - The matching response or null
   */
  findMatchingResponse(session, request) {
    // Generate hash for the incoming request
    const requestHash = this.generateContentHash({
      method: request.method,
      path: request.path,
      query: request.query,
      body: request.body
    });
    
    // Find matching interaction by hash
    const matchingInteraction = session.interactions.find(
      interaction => interaction.requestHash === requestHash
    );
    
    return matchingInteraction ? matchingInteraction.response : null;
  }

  /**
   * Create a middleware function for replaying a session
   * @param {string} sessionFilePath - Path to the session file
   * @returns {Function} Express middleware function
   */
  createReplayMiddleware(sessionFilePath) {
    let sessionData = null;
    
    return async (req, res, next) => {
      try {
        // Lazy-load session data if not loaded yet
        if (!sessionData) {
          sessionData = await this.loadSession(sessionFilePath);
          console.log(`Loaded replay session: ${sessionData.sessionId}`);
        }
        
        // Find matching response
        const matchingResponse = this.findMatchingResponse(sessionData, {
          method: req.method,
          path: req.path,
          query: req.query,
          body: req.body
        });
        
        if (matchingResponse) {
          // Set status and headers
          res.status(matchingResponse.statusCode);
          
          if (matchingResponse.headers) {
            Object.entries(matchingResponse.headers).forEach(([key, value]) => {
              // Skip certain headers that might cause issues
              if (!['content-length', 'connection'].includes(key.toLowerCase())) {
                res.set(key, value);
              }
            });
          }
          
          // Send the recorded response body
          return res.send(matchingResponse.body);
        }
        
        // No match found, pass to next middleware
        console.warn(`No matching response found for: ${req.method} ${req.path}`);
        next();
      } catch (error) {
        console.error('Error in replay middleware:', error);
        next(error);
      }
    };
  }

  /**
   * Configure a server to replay a recorded session
   * @param {Object} server - Express server
   * @param {string} sessionFilePath - Path to the session file
   */
  replaySession(server, sessionFilePath) {
    if (!server) {
      throw new Error('Invalid server provided for session replay');
    }
    
    const replayMiddleware = this.createReplayMiddleware(sessionFilePath);
    server.use(replayMiddleware);
    
    console.log(`Session replay configured using: ${sessionFilePath}`);
    return true;
  }

  /**
   * Hook into a server to record sessions
   * @param {Object} server - Express server
   */
  hookIntoServer(server) {
    if (!server) {
      throw new Error('Invalid server provided for hooking');
    }

    // Middleware to capture requests and responses
    server.use((req, res, next) => {
      const originalSend = res.send;
      const originalJson = res.json;
      const startTime = Date.now();
      
      // Override send method to capture response
      res.send = function(body) {
        res.body = body;
        res.duration = Date.now() - startTime;
        if (this.isRecording) {
          this.recordInteraction(req, res);
        }
        return originalSend.apply(res, arguments);
      }.bind(this);
      
      // Override json method to capture JSON responses
      res.json = function(body) {
        res.body = body;
        res.duration = Date.now() - startTime;
        if (this.isRecording) {
          this.recordInteraction(req, res);
        }
        return originalJson.apply(res, arguments);
      }.bind(this);
      
      next();
    });

    console.log('SessionRecorder successfully hooked into server');
    return true;
  }
}

module.exports = SessionRecorder;