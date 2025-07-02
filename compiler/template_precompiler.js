const { compile } = require('handlebars');
const { pathToRegexp, match } = require('path-to-regexp');
const { v4: uuidv4 } = require('uuid');
const dayjs = require('dayjs');

/**
 * Template engine for generating dynamic response content
 */
class ResponseTemplate {
  /**
   * Create a new ResponseTemplate
   * @param {string|Object} template - Template string or object with placeholders
   * @param {Object} options - Template options
   */
  constructor(template, options = {}) {
    this.originalTemplate = template;
    this.options = {
      helpers: {},
      partials: {},
      ...options
    };
    
    this.compiled = null;
    this.initialize();
  }

  /**
   * Initialize the template and register default helpers
   */
  initialize() {
    // Register default helpers
    this.registerHelper('uuid', () => uuidv4());
    this.registerHelper('now', (format = 'YYYY-MM-DDTHH:mm:ss.SSSZ') => 
      dayjs().format(format)
    );
    this.registerHelper('timestamp', () => Date.now());
    this.registerHelper('random', (min, max) => {
      min = parseInt(min) || 0;
      max = parseInt(max) || 100;
      return Math.floor(Math.random() * (max - min + 1)) + min;
    });
    this.registerHelper('concat', (...args) => {
      // Remove the last argument (handlebars options object)
      args.pop();
      return args.join('');
    });
    this.registerHelper('if_eq', function(a, b, options) {
      return a === b ? options.fn(this) : options.inverse(this);
    });
    
    // Compile the template
    this.compile();
  }

  /**
   * Compile the template for rendering
   */
  compile() {
    if (typeof this.originalTemplate === 'string') {
      // It's a string template
      this.compiled = compile(this.originalTemplate);
    } else if (typeof this.originalTemplate === 'object') {
      // It's an object template - compile nested strings recursively
      this.compiled = this.compileObjectTemplate(this.originalTemplate);
    } else {
      throw new Error('Template must be a string or object');
    }
  }

  /**
   * Recursively compile an object template with nested templates
   * @param {Object} obj - Object with nested templates
   * @returns {Function} Compiled template function
   */
  compileObjectTemplate(obj) {
    const compiledObj = {};
    
    for (const [key, value] of Object.entries(obj)) {
      if (typeof value === 'string' && value.includes('{{')) {
        // It's a string template
        compiledObj[key] = compile(value);
      } else if (typeof value === 'object' && value !== null) {
        // It's a nested object
        compiledObj[key] = this.compileObjectTemplate(value);
      } else {
        // It's a static value
        compiledObj[key] = value;
      }
    }
    
    return context => {
      const result = {};
      
      for (const [key, value] of Object.entries(compiledObj)) {
        if (typeof value === 'function') {
          // It's a compiled template
          result[key] = value(context);
        } else if (typeof value === 'object' && value !== null) {
          // It's a nested object
          result[key] = value(context);
        } else {
          // It's a static value
          result[key] = value;
        }
      }
      
      return result;
    };
  }

  /**
   * Register a custom helper function
   * @param {string} name - Helper name
   * @param {Function} fn - Helper function
   */
  registerHelper(name, fn) {
    this.options.helpers[name] = fn;
    // Re-register the helper with Handlebars
    if (typeof fn === 'function') {
      require('handlebars').registerHelper(name, fn);
    }
  }

  /**
   * Register a partial template
   * @param {string} name - Partial name
   * @param {string} template - Partial template
   */
  registerPartial(name, template) {
    this.options.partials[name] = template;
    // Register the partial with Handlebars
    require('handlebars').registerPartial(name, template);
  }

  /**
   * Generate response using template and context data
   * @param {Object} context - Context data for template rendering
   * @returns {any} Rendered response
   */
  render(context = {}) {
    if (!this.compiled) {
      throw new Error('Template not compiled');
    }
    
    try {
      return this.compiled(context);
    } catch (error) {
      console.error('Error rendering template:', error);
      throw error;
    }
  }
}

/**
 * Resolves dynamic responses using request context and templates
 */
class ResponseResolver {
  /**
   * Create a new ResponseResolver
   * @param {Object} options - Resolver options
   */
  constructor(options = {}) {
    this.options = {
      defaultContext: {},
      ...options
    };
    
    this.routeTemplates = [];
    this.contextBuilders = [];
    
    // Register default context builder
    this.registerContextBuilder((req) => {
      return {
        request: {
          method: req.method,
          path: req.path,
          query: req.query,
          params: req.params || {},
          body: req.body
        },
        timestamp: Date.now(),
        random: {
          uuid: uuidv4(),
          number: Math.floor(Math.random() * 1000)
        }
      };
    });
  }

  /**
   * Register a response template for a route pattern
   * @param {string} routePattern - Route pattern (e.g., '/api/users/:id')
   * @param {Object} template - Response template
   * @param {Object} options - Template options
   * @returns {ResponseResolver} this instance for chaining
   */
  registerTemplate(routePattern, template, options = {}) {
    const routeRegex = pathToRegexp(routePattern);
    const matchFn = match(routePattern, { decode: decodeURIComponent });
    
    this.routeTemplates.push({
      pattern: routePattern,
      regex: routeRegex,
      match: matchFn,
      template: new ResponseTemplate(template, options),
      method: options.method || '*',
      statusCode: options.statusCode || 200,
      headers: options.headers || { 'Content-Type': 'application/json' }
    });
    
    return this;
  }

  /**
   * Register a context builder function
   * @param {Function} builder - Function that builds context from request
   * @returns {ResponseResolver} this instance for chaining
   */
  registerContextBuilder(builder) {
    if (typeof builder === 'function') {
      this.contextBuilders.push(builder);
    }
    return this;
  }

  /**
   * Build context for template rendering
   * @param {Object} request - The request object
   * @returns {Object} Context for template rendering
   */
  buildContext(request) {
    // Start with default context
    let context = { ...this.options.defaultContext };
    
    // Apply each context builder
    for (const builder of this.contextBuilders) {
      try {
        const additionalContext = builder(request);
        context = { ...context, ...additionalContext };
      } catch (error) {
        console.error('Error in context builder:', error);
      }
    }
    
    return context;
  }

  /**
   * Find a matching route template for a request
   * @param {Object} request - The request object
   * @returns {Object|null} Matching route template or null
   */
  findMatchingTemplate(request) {
    for (const route of this.routeTemplates) {
      // Check method match
      if (route.method !== '*' && route.method.toUpperCase() !== request.method.toUpperCase()) {
        continue;
      }
      
      // Check path match
      const matchResult = route.match(request.path);
      if (!matchResult) {
        continue;
      }
      
      // Extract path parameters
      const params = matchResult.params;
      
      // Return the matching template with params
      return { 
        ...route, 
        params
      };
    }
    
    return null;
  }

  /**
   * Generate a response for a request
   * @param {Object} request - The request object
   * @returns {Object|null} Generated response or null if no match
   */
  resolveResponse(request) {
    // Find a matching template
    const matchingRoute = this.findMatchingTemplate(request);
    if (!matchingRoute) {
      return null;
    }
    
    // Update request with extracted params
    request.params = matchingRoute.params;
    
    // Build context for rendering
    const context = this.buildContext(request);
    
    // Render the template
    const responseBody = matchingRoute.template.render(context);
    
    // Build the full response
    return {
      statusCode: matchingRoute.statusCode,
      headers: matchingRoute.headers,
      body: responseBody
    };
  }

  /**
   * Extract variables from a request for response generation
   * @param {Object} request - The request object
   * @returns {Object} Variables extracted from request
   */
  extractResponseVariables(request) {
    const variables = {};
    
    // Extract path parameters
    const matchingRoute = this.findMatchingTemplate(request);
    if (matchingRoute) {
      variables.params = matchingRoute.params;
    }
    
    // Extract query parameters
    variables.query = request.query || {};
    
    // Extract body fields for POST/PUT/PATCH
    if (request.body && ['POST', 'PUT', 'PATCH'].includes(request.method.toUpperCase())) {
      variables.body = request.body;
    }
    
    // Add request metadata
    variables.request = {
      method: request.method,
      path: request.path
    };
    
    return variables;
  }
}

/**
 * Enhanced SnapshotVerifier with template-based response generation
 */
class EnhancedSnapshotVerifier extends SnapshotVerifier {
  /**
   * Create a new EnhancedSnapshotVerifier
   * @param {Object} options - Verifier options
   */
  constructor(options = {}) {
    super(options);
    
    // Initialize response resolver
    this.responseResolver = new ResponseResolver({
      defaultContext: options.defaultContext || {}
    });
  }

  /**
   * Register a response template
   * @param {string} routePattern - Route pattern (e.g., '/api/users/:id')
   * @param {Object} template - Response template
   * @param {Object} options - Template options
   * @returns {EnhancedSnapshotVerifier} this instance for chaining
   */
  registerTemplate(routePattern, template, options = {}) {
    this.responseResolver.registerTemplate(routePattern, template, options);
    return this;
  }

  /**
   * Register a context builder function
   * @param {Function} builder - Function that builds context from request
   * @returns {EnhancedSnapshotVerifier} this instance for chaining
   */
  registerContextBuilder(builder) {
    this.responseResolver.registerContextBuilder(builder);
    return this;
  }

  /**
   * Override replay method to use templates when applicable
   * @param {Object} request - The request object
   * @param {string} targetBaseUrl - Base URL for the target API
   * @returns {Promise<Object>} The response
   */
  async replayRequest(request, targetBaseUrl) {
    // Check if we have a template for this request
    const templateResponse = this.responseResolver.resolveResponse(request);
    
    // If we have a template and dynamic response generation is enabled, use it
    if (templateResponse && this.options.useDynamicResponses) {
      return templateResponse;
    }
    
    // Otherwise, fall back to the standard replay method
    return super.replayRequest(request, targetBaseUrl);
  }

  /**
   * Replay a session with template-based response generation
   * @param {string} sessionId - ID of the session to replay
   * @param {Object} templates - Map of route patterns to templates
   * @param {Object} options - Options for replay
   * @returns {Promise<Object>} Replay results
   */
  async replayWithTemplates(sessionId, templates = {}, options = {}) {
    // Register templates
    Object.entries(templates).forEach(([pattern, template]) => {
      this.registerTemplate(pattern, template, 
        typeof template.options === 'object' ? template.options : {});
    });
    
    // Enable dynamic response generation
    const prevUseDynamicResponses = this.options.useDynamicResponses;
    this.options.useDynamicResponses = true;
    
    try {
      // Run the replay with dynamic responses
      return await this.replayAgainstContract(sessionId, options.targetBaseUrl || 'http://localhost');
    } finally {
      // Restore previous setting
      this.options.useDynamicResponses = prevUseDynamicResponses;
    }
  }

  /**
   * Configure templates from a contract specification
   * @param {Object} contract - API contract specification
   * @returns {EnhancedSnapshotVerifier} this instance for chaining
   */
  configureFromContract(contract) {
    if (!contract || !contract.paths) {
      console.warn('Invalid contract specification');
      return this;
    }
    
    // Process each path and method in the contract
    Object.entries(contract.paths).forEach(([path, methods]) => {
      Object.entries(methods).forEach(([method, operation]) => {
        // Find success responses
        const responses = operation.responses || {};
        Object.entries(responses).forEach(([statusCode, response]) => {
          // Only process success responses with examples or schemas
          if (statusCode.startsWith('2') && (response.examples || response.content)) {
            let template;
            
            // Check for examples
            if (response.examples) {
              const firstExample = Object.values(response.examples)[0];
              if (typeof firstExample === 'object') {
                template = firstExample;
              } else if (typeof firstExample === 'string') {
                try {
                  template = JSON.parse(firstExample);
                } catch (e) {
                  template = { value: firstExample };
                }
              }
            }
            // Check for content with examples
            else if (response.content && response.content['application/json']) {
              const content = response.content['application/json'];
              if (content.example) {
                template = content.example;
              } else if (content.examples) {
                const firstExample = Object.values(content.examples)[0];
                template = firstExample.value || firstExample;
              }
            }
            
            // Register the template if found
            if (template) {
              this.registerTemplate(path, template, {
                method,
                statusCode: parseInt(statusCode),
                headers: { 'Content-Type': 'application/json' }
              });
            }
          }
        });
      });
    });
    
    return this;
  }

  /**
   * Generate a detailed report that includes template usage information
   * @param {string} sessionId - ID of the session to report on
   * @returns {Promise<string>} Path to the generated report file
   */
  async generateDiffReport(sessionId) {
    // Get the standard report path
    const reportPath = await super.generateDiffReport(sessionId);
    
    // Enhance the report with template usage information
    const results = this.replayResults.get(sessionId);
    if (results) {
      const templateUsage = {
        dynamicResponsesEnabled: this.options.useDynamicResponses || false,
        templatesRegistered: this.responseResolver.routeTemplates.length,
        templatesUsed: 0
      };
      
      // Count how many responses were generated from templates
      results.interactionResults.forEach(result => {
        if (result.usedTemplate) {
          templateUsage.templatesUsed++;
        }
      });
      
      // Update the report file with template usage
      try {
        const reportData = require(reportPath);
        reportData.templateUsage = templateUsage;
        await fs.writeFile(reportPath, JSON.stringify(reportData, null, 2));
      } catch (error) {
        console.error('Failed to update report with template usage:', error);
      }
    }
    
    return reportPath;
  }
}

module.exports = {
  ResponseTemplate,
  ResponseResolver,
  EnhancedSnapshotVerifier
};