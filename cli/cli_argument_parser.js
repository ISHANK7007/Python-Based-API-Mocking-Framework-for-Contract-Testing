/**
 * Enhanced ResponseTemplate class with caching
 */
class ResponseTemplate {
  constructor(template, options = {}) {
    this.originalTemplate = template;
    this.options = {
      helpers: {},
      partials: {},
      ...options
    };
    
    this.compiled = null;
    this.templateHash = this.generateTemplateHash(template);
    
    // Initialize but don't compile yet - we'll compile on demand or during preload
  }

  /**
   * Generate a hash for template caching
   * @param {string|Object} template - Template to hash
   * @returns {string} Template hash
   */
  generateTemplateHash(template) {
    if (!template) return 'empty';
    const str = typeof template === 'string' 
      ? template 
      : JSON.stringify(template);
    
    // Simple hash function
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    return hash.toString(36);
  }

  /**
   * Initialize the template engine and register helpers
   */
  initialize() {
    if (this._initialized) return;
    
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
      args.pop(); // Remove handlebars options
      return args.join('');
    });
    this.registerHelper('if_eq', function(a, b, options) {
      return a === b ? options.fn(this) : options.inverse(this);
    });
    
    this._initialized = true;
  }

  /**
   * Compile the template for rendering
   * @returns {ResponseTemplate} this instance for chaining
   */
  compile() {
    if (this.compiled) return this; // Already compiled
    
    this.initialize();
    
    if (typeof this.originalTemplate === 'string') {
      this.compiled = compile(this.originalTemplate);
    } else if (typeof this.originalTemplate === 'object') {
      this.compiled = this.compileObjectTemplate(this.originalTemplate);
    } else {
      throw new Error('Template must be a string or object');
    }
    
    return this;
  }

  // ... rest of the class remains the same ...

  /**
   * Render the template with context
   * @param {Object} context - Context for rendering 
   * @returns {any} Rendered response
   */
  render(context = {}) {
    // Ensure template is compiled
    if (!this.compiled) {
      this.compile();
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
 * Enhanced ResponseResolver with template caching
 */
class ResponseResolver {
  constructor(options = {}) {
    this.options = {
      defaultContext: {},
      ...options
    };
    
    this.routeTemplates = [];
    this.contextBuilders = [];
    this.templateCache = new Map();
    
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
    
    // Performance metrics
    this.metrics = {
      templateCompilations: 0,
      templateRenders: 0,
      cacheHits: 0,
      cacheMisses: 0,
      totalRenderTime: 0
    };
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
    
    const responseTemplate = new ResponseTemplate(template, options);
    
    this.routeTemplates.push({
      pattern: routePattern,
      regex: routeRegex,
      match: matchFn,
      template: responseTemplate,
      method: options.method || '*',
      statusCode: options.statusCode || 200,
      headers: options.headers || { 'Content-Type': 'application/json' }
    });
    
    return this;
  }

  /**
   * Precompile all registered templates
   * @returns {ResponseResolver} this instance for chaining
   */
  precompileTemplates() {
    console.time('Template precompilation');
    
    this.routeTemplates.forEach(route => {
      route.template.compile();
      this.metrics.templateCompilations++;
    });
    
    console.timeEnd('Template precompilation');
    return this;
  }

  /**
   * Generate a cache key for a request
   * @param {Object} request - Request object
   * @param {Object} route - Route object
   * @returns {string} Cache key
   */
  generateCacheKey(request, route) {
    // Create a key based on method, path, and route pattern
    const methodKey = request.method.toUpperCase();
    const pathKey = request.path;
    const routeKey = route.pattern;
    
    return `${methodKey}-${pathKey}-${routeKey}`;
  }

  /**
   * Find a matching route template for a request with caching
   * @param {Object} request - The request object
   * @returns {Object|null} Matching route template or null
   */
  findMatchingTemplate(request) {
    // Fast path: check method-path cache first
    const fastCacheKey = `${request.method.toUpperCase()}-${request.path}`;
    if (this.templateCache.has(fastCacheKey)) {
      this.metrics.cacheHits++;
      return this.templateCache.get(fastCacheKey);
    }
    
    this.metrics.cacheMisses++;
    
    // Slow path: find matching route
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
      
      // Create the matched route with params
      const matchedRoute = { 
        ...route, 
        params
      };
      
      // Cache this result for future reuse
      this.templateCache.set(fastCacheKey, matchedRoute);
      
      // Return the matching template with params
      return matchedRoute;
    }
    
    // Cache negative result to avoid future lookups
    this.templateCache.set(fastCacheKey, null);
    return null;
  }

  /**
   * Generate a response for a request with caching
   * @param {Object} request - The request object
   * @returns {Object|null} Generated response or null if no match
   */
  resolveResponse(request) {
    const startTime = process.hrtime();
    
    // Find a matching template
    const matchingRoute = this.findMatchingTemplate(request);
    if (!matchingRoute) {
      return null;
    }
    
    // Update request with extracted params
    request.params = matchingRoute.params;
    
    // Build context for rendering
    const context = this.buildContext(request);
    
    // Track render metrics
    this.metrics.templateRenders++;
    
    // Render the template
    const responseBody = matchingRoute.template.render(context);
    
    // Calculate render time
    const endTime = process.hrtime(startTime);
    const renderTimeMs = (endTime[0] * 1000) + (endTime[1] / 1000000);
    this.metrics.totalRenderTime += renderTimeMs;
    
    // Build the full response
    return {
      statusCode: matchingRoute.statusCode,
      headers: matchingRoute.headers,
      body: responseBody
    };
  }

  /**
   * Get performance metrics
   * @returns {Object} Performance metrics
   */
  getMetrics() {
    return {
      ...this.metrics,
      averageRenderTimeMs: this.metrics.templateRenders > 0 
        ? this.metrics.totalRenderTime / this.metrics.templateRenders 
        : 0,
      cacheHitRate: (this.metrics.cacheHits + this.metrics.cacheMisses) > 0
        ? this.metrics.cacheHits / (this.metrics.cacheHits + this.metrics.cacheMisses) * 100
        : 0
    };
  }

  /**
   * Clear all caches
   * @returns {ResponseResolver} this instance for chaining
   */
  clearCaches() {
    this.templateCache.clear();
    return this;
  }
  
  // ... rest of the class remains the same ...
}

/**
 * Enhanced SnapshotVerifier with template preloading and caching
 */
class EnhancedSnapshotVerifier extends SnapshotVerifier {
  constructor(options = {}) {
    super(options);
    
    // Initialize response resolver with performance configuration
    this.responseResolver = new ResponseResolver({
      defaultContext: options.defaultContext || {},
      cacheCapacity: options.cacheCapacity || 1000
    });
    
    // Track overall metrics
    this.metrics = {
      totalReplayTime: 0,
      totalRequests: 0,
      templateCompilationTime: 0,
      sessionsProcessed: 0
    };
  }
  
  /**
   * Preload and compile templates from a contract
   * @param {Object} contract - API contract specification
   * @param {Object} options - Preload options
   * @returns {EnhancedSnapshotVerifier} this instance for chaining
   */
  async preloadTemplates(contract, options = {}) {
    if (!contract || !contract.paths) {
      console.warn('Invalid contract specification for preloading');
      return this;
    }
    
    const startTime = process.hrtime();
    console.log('Preloading and compiling templates...');
    
    // Register templates from contract
    let templateCount = 0;
    Object.entries(contract.paths).forEach(([path, methods]) => {
      Object.entries(methods).forEach(([method, operation]) => {
        // Find success responses
        const responses = operation.responses || {};
        
        Object.entries(responses).forEach(([statusCode, response]) => {
          // Only process success responses with examples or schemas
          if (statusCode.startsWith('2') && (response.examples || response.content)) {
            let template;
            
            // Extract template from examples or content
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
              templateCount++;
            }
          }
        });
      });
    });
    
    // Precompile all templates in one go
    this.responseResolver.precompileTemplates();
    
    const endTime = process.hrtime(startTime);
    const compilationTimeMs = (endTime[0] * 1000) + (endTime[1] / 1000000);
    this.metrics.templateCompilationTime = compilationTimeMs;
    
    console.log(`Preloaded ${templateCount} templates in ${compilationTimeMs.toFixed(2)}ms`);
    
    return this;
  }

  /**
   * Enhanced replay method with performance tracking
   * @param {Object} request - The request object
   * @param {string} targetBaseUrl - Base URL for the target API
   * @returns {Promise<Object>} The response
   */
  async replayRequest(request, targetBaseUrl) {
    this.metrics.totalRequests++;
    const startTime = process.hrtime();
    
    let response;
    
    // Check if we have a template for this request
    if (this.options.useDynamicResponses) {
      response = this.responseResolver.resolveResponse(request);
      
      // Fall back to standard replay if no template match
      if (!response) {
        response = await super.replayRequest(request, targetBaseUrl);
      }
    } else {
      response = await super.replayRequest(request, targetBaseUrl);
    }
    
    // Track timing
    const endTime = process.hrtime(startTime);
    const requestTimeMs = (endTime[0] * 1000) + (endTime[1] / 1000000);
    this.metrics.totalReplayTime += requestTimeMs;
    
    return response;
  }

  /**
   * Enhanced replay with templates method
   * @param {string} sessionId - ID of the session to replay
   * @param {Object} templates - Map of route patterns to templates
   * @param {Object} options - Options for replay
   * @returns {Promise<Object>} Replay results
   */
  async replayWithTemplates(sessionId, templates = {}, options = {}) {
    const startTime = process.hrtime();
    
    // Register templates if provided
    const registerStart = process.hrtime();
    Object.entries(templates).forEach(([pattern, template]) => {
      this.registerTemplate(pattern, template, 
        typeof template.options === 'object' ? template.options : {});
    });
    
    // Precompile templates for performance
    this.responseResolver.precompileTemplates();
    
    const registerEnd = process.hrtime(registerStart);
    const registerTimeMs = (registerEnd[0] * 1000) + (registerEnd[1] / 1000000);
    
    // Enable dynamic response generation
    const prevUseDynamicResponses = this.options.useDynamicResponses;
    this.options.useDynamicResponses = true;
    
    try {
      // Run the replay with dynamic responses
      const results = await this.replayAgainstContract(sessionId, options.targetBaseUrl || 'http://localhost');
      
      // Track session processing
      this.metrics.sessionsProcessed++;
      
      // Include timing and template metrics in results
      const endTime = process.hrtime(startTime);
      const totalTimeMs = (endTime[0] * 1000) + (endTime[1] / 1000000);
      
      results.performance = {
        totalTimeMs,
        templateRegistrationTimeMs: registerTimeMs,
        templateMetrics: this.responseResolver.getMetrics()
      };
      
      return results;
    } finally {
      // Restore previous setting
      this.options.useDynamicResponses = prevUseDynamicResponses;
    }
  }

  /**
   * Get overall performance metrics
   * @returns {Object} Performance metrics
   */
  getPerformanceMetrics() {
    return {
      ...this.metrics,
      averageRequestTimeMs: this.metrics.totalRequests > 0 
        ? this.metrics.totalReplayTime / this.metrics.totalRequests 
        : 0,
      templateMetrics: this.responseResolver.getMetrics()
    };
  }
}

// Now let's update the CLI to support preloading and performance optimization
program
  .command('replay <sessionFile>')
  .description('Replay a recorded session against a contract')
  .requiredOption('--contract <contractFile>', 'Path to contract YAML file')
  .option('--output <outputFile>', 'Path to save detailed report')
  .option('--format <format>', 'Output format (json, text)', 'text')
  .option('--threshold <threshold>', 'Compatibility threshold percentage', '100')
  .option('--no-dynamic', 'Disable dynamic response generation')
  .option('--config <configFile>', 'Path to configuration file')
  .option('--verbose', 'Enable verbose output')
  .option('--fail-on-threshold', 'Exit with non-zero code if below threshold')
  .option('--strict', 'Strict comparison mode - fail on any deviation')
  .option('--tolerant', 'Apply all tolerance rules (timestamp rounding, UUID ignoring, etc.)')
  .option('--preload-templates', 'Preload and precompile templates before replay (improves performance)')
  .option('--performance', 'Show detailed performance metrics')
  .action(async (sessionFile, options) => {
    try {
      // Start timing overall execution
      const totalStartTime = process.hrtime();
      
      // Process options
      const threshold = parseFloat(options.threshold);
      if (isNaN(threshold) || threshold < 0 || threshold > 100) {
        console.error(chalk.red('Invalid threshold. Must be a number between 0 and 100.'));
        process.exit(1);
      }

      // Load configuration
      let config = {
        tolerances: {
          timestampDriftSeconds: 5,
          ignoreUUIDs: true,
          sortArrays: true
        }
      };
      
      if (options.config) {
        try {
          const configContent = await fs.readFile(options.config, 'utf8');
          const configExt = path.extname(options.config).toLowerCase();
          
          if (configExt === '.json') {
            config = { ...config, ...JSON.parse(configContent) };
          } else if (configExt === '.yaml' || configExt === '.yml') {
            config = { ...config, ...yaml.load(configContent) };
          } else {
            console.error(chalk.yellow(`Unsupported config format: ${configExt}. Using defaults.`));
          }
        } catch (error) {
          console.error(chalk.yellow(`Failed to load config file: ${error.message}. Using defaults.`));
        }
      }
      
      // Handle strict/tolerant flags
      if (options.strict) {
        config.tolerances = {
          timestampDriftSeconds: 0,
          ignoreUUIDs: false,
          sortArrays: false
        };
        console.log(chalk.yellow('Strict comparison mode enabled - any deviation will cause a failure'));
      } else if (options.tolerant) {
        config.tolerances = {
          ...config.tolerances,
          timestampDriftSeconds: Math.max(config.tolerances.timestampDriftSeconds || 0, 5),
          ignoreUUIDs: true,
          sortArrays: true
        };
        console.log(chalk.blue('Tolerant comparison mode enabled - applying all tolerance rules'));
      }
      
      if (options.verbose) {
        console.log(chalk.cyan('Starting session replay and verification...'));
        console.log(chalk.dim('Session file:'), sessionFile);
        console.log(chalk.dim('Contract file:'), options.contract);
        console.log(chalk.dim('Configuration:'), JSON.stringify(config, null, 2));
      }

      // Load contract - timing this step
      console.time('Contract loading');
      const contractLoader = new ContractLoader();
      const contract = await loadContract(options.contract, contractLoader);
      console.timeEnd('Contract loading');

      if (!contract) {
        console.error(chalk.red(`Failed to load contract: ${options.contract}`));
        process.exit(1);
      }

      // Initialize verifier
      const verifier = new EnhancedSnapshotVerifier({
        useDynamicResponses: options.dynamic,
        ...config
      });

      // Preload templates if requested - this is the optimization for performance
      if (options.preloadTemplates) {
        console.time('Template preloading');
        await verifier.preloadTemplates(contract);
        console.timeEnd('Template preloading');
      } else if (options.dynamic) {
        // Configure verifier from contract without preloading
        verifier.configureFromContract(contract);
      }

      // Load session directly from file
      console.time('Session loading');
      const sessionPath = path.resolve(sessionFile);
      const session = await loadSession(sessionPath);
      console.timeEnd('Session loading');

      if (!session) {
        console.error(chalk.red(`Failed to load session: ${sessionFile}`));
        process.exit(1);
      }

      // Set up mock target URL
      const targetUrl = 'http://localhost:8000';
      
      // Process session ID and store session data
      const sessionId = session.sessionId || `session-${Date.now()}`;
      verifier.originalSessions.set(sessionId, {
        filePath: sessionPath,
        data: session
      });

      // Perform verification
      console.time('Verification');
      let results;
      
      if (options.dynamic) {
        // Using template-based verification
        console.log(chalk.cyan('Verifying using templates from contract...'));
        results = await verifier.replayWithTemplates(sessionId, {}, {
          targetBaseUrl: targetUrl
        });
      } else {
        // Using direct verification
        console.log(chalk.cyan('Verifying against external API...'));
        results = await verifier.verifyCompatibility(sessionId, targetUrl, {
          generateReport: true,
          printSummary: options.format === 'text'
        });
      }
      console.timeEnd('Verification');

      // Add strict/tolerant mode info to results
      results.comparisonMode = options.strict ? 'strict' : (options.tolerant ? 'tolerant' : 'default');
      
      // Add performance metrics if requested
      if (options.performance) {
        const performanceMetrics = verifier.getPerformanceMetrics();
        const totalEndTime = process.hrtime(totalStartTime);
        const totalExecutionTimeMs = (totalEndTime[0] * 1000) + (totalEndTime[1] / 1000000);
        
        results.performanceMetrics = {
          ...performanceMetrics,
          totalExecutionTimeMs,
          preloadingEnabled: !!options.preloadTemplates
        };
        
        // Print performance information
        console.log(chalk.cyan('\n=== Performance Metrics ==='));
        console.log(`Total execution time: ${chalk.yellow(totalExecutionTimeMs.toFixed(2))} ms`);
        console.log(`Template compilation time: ${chalk.yellow(performanceMetrics.templateCompilationTime.toFixed(2))} ms`);
        console.log(`Average request time: ${chalk.yellow(performanceMetrics.averageRequestTimeMs.toFixed(2))} ms`);
        console.log(`Template cache hit rate: ${chalk.yellow(performanceMetrics.templateMetrics.cacheHitRate.toFixed(2))}%`);
        console.log(`Templates compiled: ${chalk.yellow(performanceMetrics.templateMetrics.templateCompilations)}`);
        console.log(`Templates rendered: ${chalk.yellow(performanceMetrics.templateMetrics.templateRenders)}`);
      }

      // Generate and save report if output file specified
      if (options.output) {
        const reportPath = path.resolve(options.output);
        const reportDir = path.dirname(reportPath);
        
        // Ensure directory exists
        await fs.mkdir(reportDir, { recursive: true });
        
        // Generate report
        const reportContent = options.format === 'json' 
          ? JSON.stringify(results, null, 2)
          : generateTextReport(results);
        
        await fs.writeFile(reportPath, reportContent);
        console.log(chalk.green(`Report saved to: ${reportPath}`));
      }

      // If not printing summary automatically, show summary for text format
      if (options.format === 'text' && !results.summaryPrinted) {
        printSummary(results);
      }

      // For JSON format, print JSON output
      if (options.format === 'json') {
        // Limit the output to summary information
        console.log(JSON.stringify({
          summary: results.summary,
          sessionId: sessionId,
          contractFile: options.contract,
          comparisonMode: results.comparisonMode,
          timestamp: new Date().toISOString(),
          performanceMetrics: results.performanceMetrics
        }, null, 2));
      }

      // Check for failures based on mode
      if (options.strict && (
        results.summary.totalChanges > 0 || 
        results.summary.incompatible > 0 || 
        results.summary.errors > 0
      )) {
        console.error(chalk.red(`Strict comparison failed: ${results.summary.totalChanges || 0} total changes detected`));
        process.exit(1);
      } else {
        const score = results.summary.effectiveCompatibilityScore || results.summary.compatibilityScore;
        const thresholdMet = score >= threshold;
        
        if (options.failOnThreshold && !thresholdMet) {
          console.error(chalk.red(`Compatibility threshold not met: ${score.toFixed(2)}% < ${threshold}%`));
          process.exit(1);
        } else if (!thresholdMet) {
          console.warn(chalk.yellow(`Compatibility threshold not met: ${score.toFixed(2)}% < ${threshold}%`));
        } else {
          console.log(chalk.green(`Compatibility threshold met: ${score.toFixed(2)}% >= ${threshold}%`));
        }
      }
    } catch (error) {
      console.error(chalk.red('Error during replay:'), error);
      process.exit(1);
    }
  });