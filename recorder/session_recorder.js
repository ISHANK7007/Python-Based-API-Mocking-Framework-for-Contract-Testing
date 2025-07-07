class SessionRecorder {
  constructor(options = {}) {
    this.sessions = [];
    this.currentSession = null;
    this.isRecording = false;
    this.options = {
      includeHeaders: true,
      includeBody: true,
      includeCookies: true,
      ...options
    };
  }

  startRecording(sessionName = `session-${Date.now()}`) {
    if (this.isRecording) {
      console.warn('A recording session is already in progress');
      return false;
    }

    this.currentSession = {
      id: sessionName,
      startTime: new Date(),
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
    
    const interaction = {
      timestamp,
      request: this.captureRequest(req),
      response: this.captureResponse(res),
      duration: res.duration || null,
      context: this.captureContext()
    };

    this.currentSession.interactions.push(interaction);
    return true;
  }

  captureRequest(req) {
    const requestData = {
      method: req.method,
      url: req.url,
      path: req.path,
      query: req.query || {}
    };

    if (this.options.includeHeaders) {
      requestData.headers = this.filterSensitiveHeaders(req.headers);
    }

    if (this.options.includeBody && req.body) {
      requestData.body = this.sanitizeData(req.body);
    }

    if (this.options.includeCookies && req.cookies) {
      requestData.cookies = this.filterSensitiveCookies(req.cookies);
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
      responseData.body = this.sanitizeData(res.body);
    }

    return responseData;
  }

  captureContext() {
    return {
      timestamp: new Date(),
      environment: process.env.NODE_ENV || 'development',
      custom: this.options.contextProvider ? this.options.contextProvider() : {}
    };
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
    const sensitiveHeaders = ['authorization', 'cookie', 'set-cookie'];
    
    sensitiveHeaders.forEach(header => {
      if (filteredHeaders[header]) {
        filteredHeaders[header] = '[REDACTED]';
      }
    });
    
    return filteredHeaders;
  }

  filterSensitiveCookies(cookies) {
    const filteredCookies = {...cookies};
    const sensitiveCookies = ['session', 'auth', 'token'];
    
    Object.keys(filteredCookies).forEach(cookie => {
      if (sensitiveCookies.some(sensitive => cookie.toLowerCase().includes(sensitive))) {
        filteredCookies[cookie] = '[REDACTED]';
      }
    });
    
    return filteredCookies;
  }

  sanitizeData(data) {
    // Deep clone to avoid modifying the original data
    const clonedData = JSON.parse(JSON.stringify(data));
    const sensitiveFields = ['password', 'token', 'secret', 'key', 'authorization'];
    
    const recursiveSanitize = (obj) => {
      if (!obj || typeof obj !== 'object') return;
      
      Object.keys(obj).forEach(key => {
        if (sensitiveFields.some(field => key.toLowerCase().includes(field))) {
          obj[key] = '[REDACTED]';
        } else if (typeof obj[key] === 'object') {
          recursiveSanitize(obj[key]);
        }
      });
    };
    
    recursiveSanitize(clonedData);
    return clonedData;
  }

  exportSession(sessionId, format = 'json') {
    const session = this.sessions.find(s => s.id === sessionId) || 
                    (this.currentSession && this.currentSession.id === sessionId ? 
                     this.currentSession : null);
    
    if (!session) {
      console.error(`Session with ID ${sessionId} not found`);
      return null;
    }
    
    switch (format.toLowerCase()) {
      case 'json':
        return JSON.stringify(session, null, 2);
      case 'har':
        return this.convertToHAR(session);
      default:
        console.error(`Unsupported export format: ${format}`);
        return null;
    }
  }

  convertToHAR(session) {
    // Basic HAR (HTTP Archive) format conversion
    const har = {
      log: {
        version: '1.2',
        creator: {
          name: 'SessionRecorder',
          version: '1.0'
        },
        pages: [{
          startedDateTime: session.startTime.toISOString(),
          id: session.id,
          title: `Session ${session.id}`,
          pageTimings: {
            onContentLoad: -1,
            onLoad: -1
          }
        }],
        entries: []
      }
    };

    session.interactions.forEach((interaction, index) => {
      har.log.entries.push({
        pageref: session.id,
        startedDateTime: interaction.timestamp.toISOString(),
        time: interaction.duration || 0,
        request: {
          method: interaction.request.method,
          url: interaction.request.url,
          httpVersion: 'HTTP/1.1',
          cookies: [],
          headers: Object.entries(interaction.request.headers || {}).map(([name, value]) => ({ name, value })),
          queryString: Object.entries(interaction.request.query || {}).map(([name, value]) => ({ name, value: String(value) })),
          postData: interaction.request.body ? {
            mimeType: interaction.request.headers['content-type'] || 'application/json',
            text: typeof interaction.request.body === 'object' ? 
                  JSON.stringify(interaction.request.body) : String(interaction.request.body)
          } : undefined,
          headersSize: -1,
          bodySize: -1
        },
        response: {
          status: interaction.response.statusCode,
          statusText: interaction.response.statusMessage,
          httpVersion: 'HTTP/1.1',
          cookies: [],
          headers: Object.entries(interaction.response.headers || {}).map(([name, value]) => ({ name, value })),
          content: {
            size: -1,
            mimeType: interaction.response.headers['content-type'] || 'application/json',
            text: typeof interaction.response.body === 'object' ? 
                  JSON.stringify(interaction.response.body) : String(interaction.response.body || '')
          },
          redirectURL: '',
          headersSize: -1,
          bodySize: -1
        },
        cache: {},
        timings: {
          send: 0,
          wait: interaction.duration || 0,
          receive: 0
        }
      });
    });

    return JSON.stringify(har, null, 2);
  }

  // Method to hook into a mock server
  hookIntoServer(server) {
    if (!server) {
      console.error('Invalid server provided for hooking');
      return false;
    }

    // The implementation details will depend on the mock server being used
    // For example, with Express:
    server.use((req, res, next) => {
      const originalSend = res.send;
      const startTime = Date.now();
      
      res.send = function(body) {
        res.body = body;
        res.duration = Date.now() - startTime;
        if (this.isRecording) {
          this.recordInteraction(req, res);
        }
        return originalSend.apply(res, arguments);
      }.bind(this);
      
      next();
    });

    console.log('SessionRecorder successfully hooked into server');
    return true;
  }
}

module.exports = SessionRecorder;