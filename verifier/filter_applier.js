const fs = require('fs').promises;
const path = require('path');
const axios = require('axios');
const deepDiff = require('deep-diff');
const chalk = require('chalk');
const Table = require('cli-table3');

class SnapshotVerifier {
  constructor(options = {}) {
    this.options = {
      logDirectory: './session-logs',
      diffOutputDirectory: './diff-reports',
      ignoreHeaders: ['date', 'content-length', 'etag', 'connection'],
      ignoreFields: [],
      ...options
    };
    
    this.originalSessions = new Map();
    this.replayResults = new Map();
    
    // Ensure output directories exist
    this.ensureDirectories();
  }

  async ensureDirectories() {
    try {
      await fs.mkdir(this.options.logDirectory, { recursive: true });
      await fs.mkdir(this.options.diffOutputDirectory, { recursive: true });
    } catch (error) {
      console.error('Failed to create directories:', error);
    }
  }

  /**
   * Load a recorded session from disk
   * @param {string} sessionFilePath - Path to the session file
   * @returns {Promise<Object>} The loaded session data
   */
  async loadSession(sessionFilePath) {
    try {
      const data = await fs.readFile(sessionFilePath, 'utf8');
      const session = JSON.parse(data);
      this.originalSessions.set(session.sessionId, {
        filePath: sessionFilePath,
        data: session
      });
      return session;
    } catch (error) {
      console.error(`Failed to load session from ${sessionFilePath}:`, error);
      throw error;
    }
  }

  /**
   * Load all session files from the log directory
   * @returns {Promise<Array>} Array of loaded session IDs
   */
  async loadAllSessions() {
    try {
      const files = await fs.readdir(this.options.logDirectory);
      const sessionFiles = files.filter(file => file.startsWith('session_') && file.endsWith('.json'));
      
      const loadPromises = sessionFiles.map(file => 
        this.loadSession(path.join(this.options.logDirectory, file))
      );
      
      const sessions = await Promise.all(loadPromises);
      return sessions.map(session => session.sessionId);
    } catch (error) {
      console.error('Failed to load sessions:', error);
      throw error;
    }
  }

  /**
   * Replay a single request against the target API
   * @param {Object} request - The original request
   * @param {string} targetBaseUrl - Base URL of the target API
   * @returns {Promise<Object>} The response from the target API
   */
  async replayRequest(request, targetBaseUrl) {
    try {
      const url = new URL(request.path, targetBaseUrl).toString();
      
      const response = await axios({
        method: request.method,
        url,
        headers: request.headers,
        params: request.query,
        data: request.body,
        validateStatus: () => true // Accept any status code
      });
      
      return {
        statusCode: response.status,
        headers: response.headers,
        body: response.data
      };
    } catch (error) {
      console.error(`Failed to replay request ${request.method} ${request.path}:`, error.message);
      return {
        statusCode: 500,
        headers: {},
        body: { error: error.message },
        replayError: true
      };
    }
  }

  /**
   * Compare two response objects and return differences
   * @param {Object} original - Original response
   * @param {Object} replayed - Replayed response
   * @returns {Object} The comparison results
   */
  compareResponses(original, replayed) {
    // Normalize responses for comparison
    const normalizedOriginal = this.normalizeForComparison(original);
    const normalizedReplayed = this.normalizeForComparison(replayed);
    
    // Calculate differences
    const statusMatch = normalizedOriginal.statusCode === normalizedReplayed.statusCode;
    const headerDiffs = this.compareHeaders(normalizedOriginal.headers, normalizedReplayed.headers);
    const bodyDiffs = this.compareResponseBodies(normalizedOriginal.body, normalizedReplayed.body);
    
    return {
      statusMatch,
      headerDiffs,
      bodyDiffs,
      isCompatible: statusMatch && headerDiffs.added.length === 0 && 
                   headerDiffs.removed.length === 0 && 
                   bodyDiffs.incompatible.length === 0 &&
                   bodyDiffs.removed.length === 0
    };
  }

  /**
   * Normalize response object for consistent comparison
   * @param {Object} response - Response object
   * @returns {Object} Normalized response
   */
  normalizeForComparison(response) {
    // Deep clone the response to avoid modifications
    const normalized = JSON.parse(JSON.stringify(response));
    
    // Convert headers to lowercase for case-insensitive comparison
    if (normalized.headers) {
      const normalizedHeaders = {};
      Object.keys(normalized.headers).forEach(key => {
        const lowerKey = key.toLowerCase();
        if (!this.options.ignoreHeaders.includes(lowerKey)) {
          normalizedHeaders[lowerKey] = normalized.headers[key];
        }
      });
      normalized.headers = normalizedHeaders;
    }
    
    // Parse body if it's a JSON string
    if (typeof normalized.body === 'string' && 
        (normalized.body.startsWith('{') || normalized.body.startsWith('['))) {
      try {
        normalized.body = JSON.parse(normalized.body);
      } catch (e) {
        // Keep as string if parsing fails
      }
    }
    
    return normalized;
  }

  /**
   * Compare headers between original and replayed responses
   * @param {Object} originalHeaders - Original response headers
   * @param {Object} replayedHeaders - Replayed response headers
   * @returns {Object} Header differences
   */
  compareHeaders(originalHeaders, replayedHeaders) {
    const originalKeys = Object.keys(originalHeaders || {});
    const replayedKeys = Object.keys(replayedHeaders || {});
    
    const added = replayedKeys.filter(key => !originalKeys.includes(key));
    const removed = originalKeys.filter(key => !replayedKeys.includes(key));
    const modified = originalKeys
      .filter(key => replayedKeys.includes(key) && 
                    originalHeaders[key] !== replayedHeaders[key])
      .map(key => ({
        key,
        original: originalHeaders[key],
        replayed: replayedHeaders[key]
      }));
    
    return { 
      added,
      removed, 
      modified,
      total: added.length + removed.length + modified.length
    };
  }

  /**
   * Compare response bodies and identify field-level differences
   * @param {Object} originalBody - Original response body
   * @param {Object} replayedBody - Replayed response body
   * @returns {Object} Body differences
   */
  compareResponseBodies(originalBody, replayedBody) {
    // Handle edge cases
    if (originalBody === undefined && replayedBody === undefined) {
      return { added: [], removed: [], modified: [], incompatible: [], total: 0 };
    }
    
    if (typeof originalBody !== typeof replayedBody) {
      return {
        added: [],
        removed: [],
        modified: [],
        incompatible: [{
          path: '/',
          reason: `Type mismatch: ${typeof originalBody} vs ${typeof replayedBody}`
        }],
        total: 1
      };
    }
    
    // For primitive types, do direct comparison
    if (typeof originalBody !== 'object' || originalBody === null || replayedBody === null) {
      const identical = originalBody === replayedBody;
      return {
        added: [],
        removed: [],
        modified: identical ? [] : [{ path: '/', original: originalBody, replayed: replayedBody }],
        incompatible: [],
        total: identical ? 0 : 1
      };
    }
    
    // For objects and arrays, use deep-diff
    try {
      const differences = deepDiff.diff(originalBody, replayedBody) || [];
      
      // Process differences into categorized results
      const added = [];
      const removed = [];
      const modified = [];
      const incompatible = [];
      
      differences.forEach(diff => {
        const path = diff.path.join('.');
        
        // Skip ignored fields
        if (this.shouldIgnoreField(path)) {
          return;
        }
        
        switch (diff.kind) {
          case 'N': // New item/property added
            added.push({
              path,
              value: diff.rhs
            });
            break;
          case 'D': // Property/item deleted
            removed.push({
              path,
              value: diff.lhs
            });
            // Removals are considered incompatible changes (breaking)
            incompatible.push({
              path,
              reason: 'Field was removed',
              value: diff.lhs
            });
            break;
          case 'E': // Property/item changed
            modified.push({
              path,
              original: diff.lhs,
              replayed: diff.rhs
            });
            // Check if this is a type change (incompatible)
            if (typeof diff.lhs !== typeof diff.rhs) {
              incompatible.push({
                path,
                reason: `Type changed from ${typeof diff.lhs} to ${typeof diff.rhs}`,
                original: diff.lhs,
                replayed: diff.rhs
              });
            }
            break;
          case 'A': // Array change
            const arrayPath = `${path}[${diff.index}]`;
            if (diff.item.kind === 'D') {
              removed.push({
                path: arrayPath,
                value: diff.item.lhs
              });
              // Consider array element removals as potentially incompatible
              incompatible.push({
                path: arrayPath,
                reason: 'Array element was removed',
                value: diff.item.lhs
              });
            } else if (diff.item.kind === 'N') {
              added.push({
                path: arrayPath,
                value: diff.item.rhs
              });
            } else if (diff.item.kind === 'E') {
              modified.push({
                path: arrayPath,
                original: diff.item.lhs,
                replayed: diff.item.rhs
              });
              // Check for type changes in array elements
              if (typeof diff.item.lhs !== typeof diff.item.rhs) {
                incompatible.push({
                  path: arrayPath,
                  reason: `Type changed from ${typeof diff.item.lhs} to ${typeof diff.item.rhs}`,
                  original: diff.item.lhs,
                  replayed: diff.item.rhs
                });
              }
            }
            break;
        }
      });

      return {
        added,
        removed,
        modified,
        incompatible,
        total: added.length + removed.length + modified.length
      };
    } catch (error) {
      console.error('Error comparing response bodies:', error);
      return {
        added: [],
        removed: [],
        modified: [],
        incompatible: [{
          path: '/',
          reason: `Comparison error: ${error.message}`
        }],
        total: 1
      };
    }
  }

  /**
   * Check if a field should be ignored in comparisons
   * @param {string} fieldPath - The dotted path to the field
   * @returns {boolean} True if field should be ignored
   */
  shouldIgnoreField(fieldPath) {
    return this.options.ignoreFields.some(pattern => {
      if (typeof pattern === 'string') {
        return fieldPath === pattern || fieldPath.startsWith(`${pattern}.`);
      } else if (pattern instanceof RegExp) {
        return pattern.test(fieldPath);
      }
      return false;
    });
  }

  /**
   * Replay a session against a newer contract/API
   * @param {string} sessionId - ID of the session to replay
   * @param {string} targetBaseUrl - Base URL of the target API
   * @returns {Promise<Object>} Replay results
   */
  async replayAgainstContract(sessionId, targetBaseUrl) {
    const sessionEntry = this.originalSessions.get(sessionId);
    if (!sessionEntry) {
      throw new Error(`Session ${sessionId} not found. Make sure to load it first.`);
    }
    
    const session = sessionEntry.data;
    const results = {
      sessionId,
      targetBaseUrl,
      startTime: new Date(),
      interactionResults: [],
      summary: {
        total: 0,
        compatible: 0,
        incompatible: 0,
        errors: 0
      }
    };
    
    // Process each interaction in the session
    for (const interaction of session.interactions) {
      const { request, response: originalResponse } = interaction;
      
      try {
        // Replay the request against the target API
        const replayedResponse = await this.replayRequest(request, targetBaseUrl);
        
        // Compare the responses
        const comparisonResult = this.compareResponses(originalResponse, replayedResponse);
        
        // Store the result
        const interactionResult = {
          request: {
            method: request.method,
            path: request.path
          },
          original: originalResponse,
          replayed: replayedResponse,
          comparison: comparisonResult,
          timestamp: new Date()
        };
        
        results.interactionResults.push(interactionResult);
        
        // Update summary stats
        results.summary.total++;
        if (comparisonResult.isCompatible) {
          results.summary.compatible++;
        } else {
          results.summary.incompatible++;
        }
      } catch (error) {
        console.error(`Error replaying interaction for ${request.method} ${request.path}:`, error);
        results.interactionResults.push({
          request: {
            method: request.method,
            path: request.path
          },
          error: error.message,
          timestamp: new Date()
        });
        results.summary.total++;
        results.summary.errors++;
      }
    }
    
    results.endTime = new Date();
    results.duration = results.endTime - results.startTime;
    
    // Calculate overall compatibility score
    results.summary.compatibilityScore = results.summary.total > 0 ?
      (results.summary.compatible / results.summary.total) * 100 : 0;
    
    // Store the results
    this.replayResults.set(sessionId, results);
    
    return results;
  }

  /**
   * Generate a detailed report of differences between original and replayed responses
   * @param {string} sessionId - ID of the session to report on
   * @returns {Promise<string>} Path to the generated report file
   */
  async generateDiffReport(sessionId) {
    const results = this.replayResults.get(sessionId);
    if (!results) {
      throw new Error(`No replay results found for session ${sessionId}`);
    }
    
    const reportTimestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const reportFilename = `diff-report-${sessionId}-${reportTimestamp}.json`;
    const reportPath = path.join(this.options.diffOutputDirectory, reportFilename);
    
    // Format the report data
    const report = {
      sessionId: results.sessionId,
      targetBaseUrl: results.targetBaseUrl,
      timestamp: reportTimestamp,
      duration: results.duration,
      summary: results.summary,
      details: results.interactionResults.map(result => {
        // Filter out redundant information to make the report more focused
        return {
          request: result.request,
          statusMatch: result.comparison ? result.comparison.statusMatch : false,
          headerDiffs: result.comparison ? result.comparison.headerDiffs : null,
          bodyDiffs: result.comparison ? result.comparison.bodyDiffs : null,
          isCompatible: result.comparison ? result.comparison.isCompatible : false,
          error: result.error || null
        };
      })
    };
    
    // Write report to file
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
    return reportPath;
  }

  /**
   * Print a summary of compatibility status to the console
   * @param {string} sessionId - ID of the session to summarize
   */
  printSummary(sessionId) {
    const results = this.replayResults.get(sessionId);
    if (!results) {
      console.error(`No replay results found for session ${sessionId}`);
      return;
    }
    
    console.log('\n' + chalk.bold('=== Contract Compatibility Report ==='));
    console.log(`Session ID: ${chalk.cyan(sessionId)}`);
    console.log(`Target API: ${chalk.cyan(results.targetBaseUrl)}`);
    console.log(`Timestamp: ${chalk.cyan(new Date(results.startTime).toISOString())}`);
    console.log(`Duration: ${chalk.cyan(results.duration + 'ms')}`);
    
    console.log('\n' + chalk.bold('Summary:'));
    const summary = results.summary;
    console.log(`Total Interactions: ${chalk.white(summary.total)}`);
    console.log(`Compatible: ${chalk.green(summary.compatible)}`);
    console.log(`Incompatible: ${chalk.red(summary.incompatible)}`);
    console.log(`Errors: ${chalk.yellow(summary.errors)}`);
    
    const scoreColor = summary.compatibilityScore >= 90 ? 'green' : 
                     summary.compatibilityScore >= 75 ? 'yellow' : 'red';
    console.log(`Compatibility Score: ${chalk[scoreColor](summary.compatibilityScore.toFixed(2) + '%')}`);
    
    // Create a table for endpoint-level results
    const table = new Table({
      head: [
        chalk.bold('Endpoint'),
        chalk.bold('Status'),
        chalk.bold('Header Diffs'),
        chalk.bold('Body Diffs'),
        chalk.bold('Compatible')
      ],
      colWidths: [40, 10, 15, 15, 15]
    });
    
    results.interactionResults.forEach(result => {
      if (result.error) {
        table.push([
          `${result.request.method} ${result.request.path}`,
          chalk.red('ERROR'),
          '-',
          '-',
          chalk.red('✘')
        ]);
        return;
      }
      
      const isCompatible = result.comparison.isCompatible;
      const statusMatch = result.comparison.statusMatch;
      const headerDiffs = result.comparison.headerDiffs;
      const bodyDiffs = result.comparison.bodyDiffs;
      
      table.push([
        `${result.request.method} ${result.request.path}`,
        statusMatch ? chalk.green(result.replayed.statusCode) : 
                    chalk.red(`${result.original.statusCode} → ${result.replayed.statusCode}`),
        headerDiffs.total > 0 ? chalk.yellow(headerDiffs.total) : chalk.green('0'),
        bodyDiffs.total > 0 ? chalk.yellow(bodyDiffs.total) : chalk.green('0'),
        isCompatible ? chalk.green('✓') : chalk.red('✘')
      ]);
    });
    
    console.log('\n' + chalk.bold('Endpoint Details:'));
    console.log(table.toString());
    
    // Display most significant issues
    if (summary.incompatible > 0) {
      console.log('\n' + chalk.bold('Major Compatibility Issues:'));
      let issueCount = 0;
      
      results.interactionResults.forEach(result => {
        if (result.error || !result.comparison || result.comparison.isCompatible) {
          return;
        }
        
        const endpoint = `${result.request.method} ${result.request.path}`;
        
        // Status code changes
        if (!result.comparison.statusMatch) {
          console.log(`${chalk.red('✘')} ${chalk.cyan(endpoint)} - Status code changed: ` +
                    `${chalk.red(result.original.statusCode)} → ${chalk.yellow(result.replayed.statusCode)}`);
          issueCount++;
        }
        
        // Removed fields in response (breaking changes)
        result.comparison.bodyDiffs.removed.forEach(field => {
          console.log(`${chalk.red('✘')} ${chalk.cyan(endpoint)} - Removed field: ${chalk.red(field.path)}`);
          issueCount++;
        });
        
        // Type changes (incompatible)
        result.comparison.bodyDiffs.incompatible
          .filter(diff => diff.reason && diff.reason.includes('Type changed'))
          .forEach(field => {
            console.log(`${chalk.red('✘')} ${chalk.cyan(endpoint)} - ${chalk.red(field.reason)} at ${field.path}`);
            issueCount++;
          });
        
        if (issueCount >= 10) {
          console.log(chalk.yellow('... and more issues (see detailed report)'));
          return;
        }
      });
    }
    
    console.log('\n' + chalk.bold(`Detailed report saved to: ${chalk.cyan(results.reportPath)}`));
  }

  /**
   * Verify compatibility between an original session and a target API
   * @param {string} sessionId - ID of the session to verify
   * @param {string} targetBaseUrl - Base URL of the target API
   * @param {Object} options - Options for verification
   * @returns {Promise<Object>} Verification results
   */
  async verifyCompatibility(sessionId, targetBaseUrl, options = {}) {
    const verifyOpts = {
      threshold: 100, // 100% compatibility by default
      generateReport: true,
      printSummary: true,
      ...options
    };
    
    // Replay the session against the target API
    const results = await this.replayAgainstContract(sessionId, targetBaseUrl);
    
    // Generate a detailed report
    if (verifyOpts.generateReport) {
      const reportPath = await this.generateDiffReport(sessionId);
      results.reportPath = reportPath;
    }
    
    // Print summary to console
    if (verifyOpts.printSummary) {
      this.printSummary(sessionId);
    }
    
    // Check if compatibility meets the threshold
    const { compatibilityScore } = results.summary;
    const meetsThreshold = compatibilityScore >= verifyOpts.threshold;
    
    return {
      sessionId,
      targetBaseUrl,
      compatibilityScore,
      meetsThreshold,
      threshold: verifyOpts.threshold,
      reportPath: results.reportPath
    };
  }

  /**
   * Batch verify multiple sessions against a target API
   * @param {Array<string>} sessionIds - Array of session IDs to verify
   * @param {string} targetBaseUrl - Base URL of the target API
   * @param {Object} options - Options for verification
   * @returns {Promise<Object>} Batch verification results
   */
  async batchVerify(sessionIds, targetBaseUrl, options = {}) {
    const batchResults = {
      targetBaseUrl,
      timestamp: new Date(),
      results: [],
      summary: {
        total: sessionIds.length,
        passed: 0,
        failed: 0,
        overallScore: 0
      }
    };
    
    // Default options
    const verifyOpts = {
      threshold: 100,
      generateReport: true,
      printSummary: false, // Don't print individual summaries in batch mode
      ...options
    };
    
    // Process each session
    for (const sessionId of sessionIds) {
      try {
        const result = await this.verifyCompatibility(sessionId, targetBaseUrl, {
          ...verifyOpts,
          printSummary: false
        });
        
        batchResults.results.push(result);
        
        if (result.meetsThreshold) {
          batchResults.summary.passed++;
        } else {
          batchResults.summary.failed++;
        }
      } catch (error) {
        console.error(`Error verifying session ${sessionId}:`, error);
        batchResults.results.push({
          sessionId,
          error: error.message,
          meetsThreshold: false
        });
        batchResults.summary.failed++;
      }
    }
    
    // Calculate overall compatibility score
    const totalScore = batchResults.results
      .filter(result => result.compatibilityScore !== undefined)
      .reduce((sum, result) => sum + result.compatibilityScore, 0);
    
    const validResults = batchResults.results.filter(result => result.compatibilityScore !== undefined).length;
    batchResults.summary.overallScore = validResults > 0 ? (totalScore / validResults) : 0;
    
    // Print batch summary
    if (options.printBatchSummary !== false) {
      this.printBatchSummary(batchResults);
    }
    
    return batchResults;
  }

  /**
   * Print a summary of batch verification results
   * @param {Object} batchResults - Batch verification results
   */
  printBatchSummary(batchResults) {
    console.log('\n' + chalk.bold('=== Batch Contract Verification Summary ==='));
    console.log(`Target API: ${chalk.cyan(batchResults.targetBaseUrl)}`);
    console.log(`Timestamp: ${chalk.cyan(batchResults.timestamp.toISOString())}`);
    
    const summary = batchResults.summary;
    console.log(`\nTotal Sessions: ${chalk.white(summary.total)}`);
    console.log(`Passed: ${chalk.green(summary.passed)}`);
    console.log(`Failed: ${chalk.red(summary.failed)}`);
    
    const scoreColor = summary.overallScore >= 90 ? 'green' : 
                     summary.overallScore >= 75 ? 'yellow' : 'red';
    console.log(`Overall Score: ${chalk[scoreColor](summary.overallScore.toFixed(2) + '%')}`);
    
    // Create a table for session-level results
    const table = new Table({
      head: [
        chalk.bold('Session ID'),
        chalk.bold('Score'),
        chalk.bold('Threshold'),
        chalk.bold('Status')
      ],
      colWidths: [40, 15, 15, 15]
    });
    
    batchResults.results.forEach(result => {
      if (result.error) {
        table.push([
          result.sessionId,
          chalk.red('ERROR'),
          chalk.cyan(result.threshold || '-'),
          chalk.red('✘')
        ]);
        return;
      }
      
      const scoreColor = result.compatibilityScore >= 90 ? 'green' : 
                       result.compatibilityScore >= 75 ? 'yellow' : 'red';
      
      table.push([
        result.sessionId,
        chalk[scoreColor](result.compatibilityScore.toFixed(2) + '%'),
        chalk.cyan(result.threshold + '%'),
        result.meetsThreshold ? chalk.green('✓') : chalk.red('✘')
      ]);
    });
    
    console.log('\nSession Results:');
    console.log(table.toString());
  }
}

module.exports = SnapshotVerifier;