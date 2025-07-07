const crypto = require('crypto');
const fs = require('fs').promises;
const path = require('path');
const axios = require('axios');
const deepDiff = require('deep-diff');
const chalk = require('chalk');
const Table = require('cli-table3');
const isUUID = require('is-uuid');
const _ = require('lodash');

class SnapshotVerifier {
  constructor(options = {}) {
    this.options = {
      logDirectory: './session-logs',
      diffOutputDirectory: './diff-reports',
      ignoreHeaders: ['date', 'content-length', 'etag', 'connection'],
      ignoreFields: [],
      tolerances: {
        // Default tolerances
        timestampDriftSeconds: 5,           // Allow ±5s for timestamps
        ignoreUUIDs: true,                  // Ignore UUID values
        sortArrays: true,                   // Sort arrays before comparison
        arrayFields: [],                    // Fields that should always be sorted
        timestampFields: [                  // Field names that likely contain timestamps
          'timestamp', 'date', 'time', 'created', 'updated', 'at', 
          'createdAt', 'updatedAt', 'created_at', 'updated_at'
        ],
        uuidFields: ['id', 'uuid', 'guid', 'trackingId'] // Fields likely to contain UUIDs
      },
      ...options,
      // Merge nested tolerances object if provided
      tolerances: {
        ...(options.tolerances || {})
      }
    };
    
    this.originalSessions = new Map();
    this.replayResults = new Map();
    
    // Ensure output directories exist
    this.ensureDirectories();
  }

  // ... [previous methods remain unchanged] ...

  /**
   * Compare response bodies and identify field-level differences
   * Apply tolerance rules for timestamps, UUIDs, and array ordering
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
    
    // For primitive types, apply tolerance-based comparison
    if (typeof originalBody !== 'object' || originalBody === null || replayedBody === null) {
      // Apply tolerances to primitive values if applicable
      const areEquivalent = this.areValuesEquivalent('/', originalBody, replayedBody);
      
      return {
        added: [],
        removed: [],
        modified: areEquivalent ? [] : [{ 
          path: '/', 
          original: originalBody, 
          replayed: replayedBody,
          tolerated: false
        }],
        incompatible: [],
        total: areEquivalent ? 0 : 1
      };
    }
    
    // Normalize both objects with sorting and other preprocessing
    const normalizedOriginal = this.normalizeForComparison('', originalBody);
    const normalizedReplayed = this.normalizeForComparison('', replayedBody);
    
    // For objects and arrays, use deep-diff on normalized values
    try {
      const differences = deepDiff.diff(normalizedOriginal, normalizedReplayed) || [];
      
      // Process differences into categorized results
      const added = [];
      const removed = [];
      const modified = [];
      const incompatible = [];
      let toleratedChanges = 0;
      
      differences.forEach(diff => {
        const path = diff.path.join('.');
        
        // Skip ignored fields
        if (this.shouldIgnoreField(path)) {
          return;
        }
        
        // Check if this difference should be tolerated
        const shouldTolerate = this.shouldTolerateDifference(diff, path);
        
        if (shouldTolerate) {
          toleratedChanges++;
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
              replayed: diff.rhs,
              tolerated: false
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
                replayed: diff.item.rhs,
                tolerated: false
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
        tolerated: toleratedChanges,
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
        tolerated: 0,
        total: 1
      };
    }
  }

  /**
   * Normalize data for comparison - apply tolerances and sorts
   * @param {string} path - Current path in the object
   * @param {any} data - Data to normalize
   * @returns {any} Normalized data
   */
  normalizeForComparison(path, data) {
    // Handle primitive values
    if (data === null || data === undefined || typeof data !== 'object') {
      return data;
    }
    
    // Handle arrays
    if (Array.isArray(data)) {
      // Recursively normalize each element
      const normalizedArray = data.map(item => 
        this.normalizeForComparison(`${path}[]`, item)
      );
      
      // Sort array if needed
      if (this.options.tolerances.sortArrays && this.shouldSortArray(path)) {
        return this.sortArray(normalizedArray);
      }
      
      return normalizedArray;
    }
    
    // Handle objects
    const normalizedObj = {};
    
    // Process each property
    for (const [key, value] of Object.entries(data)) {
      const fullPath = path ? `${path}.${key}` : key;
      
      // Skip UUID fields if configured
      if (this.options.tolerances.ignoreUUIDs && 
          this.isLikelyUUID(key, value) && 
          !this.shouldIgnoreField(fullPath)) {
        normalizedObj[key] = "[UUID]"; // Replace with placeholder
        continue;
      }
      
      // Normalize sub-elements recursively
      normalizedObj[key] = this.normalizeForComparison(fullPath, value);
    }
    
    return normalizedObj;
  }

  /**
   * Determines if a field appears to be a UUID
   * @param {string} key - Field key/name
   * @param {any} value - Field value
   * @returns {boolean} True if likely a UUID
   */
  isLikelyUUID(key, value) {
    // Check if key is in our list of UUID field names
    const isUuidField = this.options.tolerances.uuidFields.some(field => 
      key.toLowerCase().includes(field.toLowerCase())
    );
    
    // If key matches pattern and value is string, check format
    if (isUuidField && typeof value === 'string') {
      // Check if it's a valid UUID (using is-uuid library or regex)
      return isUUID.anyNonNil(value) || 
             /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i.test(value);
    }
    
    return false;
  }

  /**
   * Check if values are equivalent considering tolerances
   * @param {string} path - Field path
   * @param {any} original - Original value
   * @param {any} replayed - Replayed value
   * @returns {boolean} True if values are equivalent
   */
  areValuesEquivalent(path, original, replayed) {
    // Strict equality check
    if (original === replayed) {
      return true;
    }
    
    // If both are dates or timestamps, check with tolerance
    if (this.isLikelyTimestamp(path, original) && this.isLikelyTimestamp(path, replayed)) {
      return this.areTimestampsEquivalent(original, replayed);
    }
    
    // If both are UUIDs, consider them equivalent if UUID checking is enabled
    if (this.options.tolerances.ignoreUUIDs && 
        typeof original === 'string' && typeof replayed === 'string' &&
        this.isLikelyUUID('', original) && this.isLikelyUUID('', replayed)) {
      return true;
    }
    
    return false;
  }

  /**
   * Determines if a field is likely a timestamp
   * @param {string} path - Field path
   * @param {any} value - Field value
   * @returns {boolean} True if likely a timestamp
   */
  isLikelyTimestamp(path, value) {
    // Extract the field name from path
    const fieldName = path.split('.').pop();
    
    // Check if field name indicates a timestamp
    const isTimestampField = this.options.tolerances.timestampFields.some(field => 
      fieldName?.toLowerCase().includes(field.toLowerCase())
    );
    
    // For strings, check if it looks like an ISO date
    if (typeof value === 'string') {
      const isoDatePattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(.\d+)?Z?$/;
      return isTimestampField || isoDatePattern.test(value);
    }
    
    // For numbers, check if it's a reasonable timestamp (after 2000-01-01)
    if (typeof value === 'number') {
      const minTimestamp = 946684800000; // 2000-01-01
      return isTimestampField || (value > minTimestamp && value <= Date.now());
    }
    
    return false;
  }

  /**
   * Compare timestamps with tolerance
   * @param {any} timestamp1 - First timestamp
   * @param {any} timestamp2 - Second timestamp
   * @returns {boolean} True if timestamps are within tolerance
   */
  areTimestampsEquivalent(timestamp1, timestamp2) {
    try {
      // Convert both to milliseconds
      const time1 = this.toTimestamp(timestamp1);
      const time2 = this.toTimestamp(timestamp2);
      
      if (!time1 || !time2) {
        return false;
      }
      
      // Calculate difference in seconds
      const diffSeconds = Math.abs(time1 - time2) / 1000;
      return diffSeconds <= this.options.tolerances.timestampDriftSeconds;
    } catch (error) {
      return false;
    }
  }

  /**
   * Convert various timestamp formats to milliseconds
   * @param {any} value - Timestamp value
   * @returns {number|null} Milliseconds or null if invalid
   */
  toTimestamp(value) {
    if (value instanceof Date) {
      return value.getTime();
    }
    
    if (typeof value === 'number') {
      // If it's a Unix timestamp in seconds (before year 2100)
      if (value < 4102444800) {
        return value * 1000;
      }
      return value; // Already in milliseconds
    }
    
    if (typeof value === 'string') {
      // Try parsing as ISO date
      const date = new Date(value);
      if (!isNaN(date)) {
        return date.getTime();
      }
      
      // Try parsing as numeric string
      const num = Number(value);
      if (!isNaN(num)) {
        return this.toTimestamp(num);
      }
    }
    
    return null;
  }

  /**
   * Check if an array at given path should be sorted
   * @param {string} path - Path to the array
   * @returns {boolean} True if array should be sorted
   */
  shouldSortArray(path) {
    // Always sort if no specific array fields are provided
    if (this.options.tolerances.arrayFields.length === 0) {
      return true;
    }
    
    // Check if path is in the list of fields to sort
    return this.options.tolerances.arrayFields.some(field => 
      path === field || path.startsWith(`${field}.`) || path.startsWith(`${field}[`)
    );
  }

  /**
   * Sort array in a consistent way for comparison
   * @param {Array} array - Array to sort
   * @returns {Array} Sorted array
   */
  sortArray(array) {
    // If array is empty or has only one element, no need to sort
    if (!array || array.length <= 1) {
      return array;
    }
    
    // For primitive arrays, simple sort is enough
    if (array.every(item => typeof item !== 'object' || item === null)) {
      return [...array].sort((a, b) => {
        if (a === null) return -1;
        if (b === null) return 1;
        return String(a).localeCompare(String(b));
      });
    }
    
    // For array of objects, use a stable sort based on JSON representation
    return [...array].sort((a, b) => {
      const aStr = JSON.stringify(this.sortObjectKeys(a));
      const bStr = JSON.stringify(this.sortObjectKeys(b));
      return aStr.localeCompare(bStr);
    });
  }

  /**
   * Sort object keys for consistent comparison
   * @param {Object} obj - Object to sort keys
   * @returns {Object} New object with sorted keys
   */
  sortObjectKeys(obj) {
    if (!obj || typeof obj !== 'object') {
      return obj;
    }
    
    if (Array.isArray(obj)) {
      return obj.map(item => this.sortObjectKeys(item));
    }
    
    const sorted = {};
    Object.keys(obj).sort().forEach(key => {
      sorted[key] = this.sortObjectKeys(obj[key]);
    });
    
    return sorted;
  }

  /**
   * Determines if a difference should be tolerated based on configured rules
   * @param {Object} diff - The difference object from deep-diff
   * @param {string} path - The field path
   * @returns {boolean} True if difference should be tolerated
   */
  shouldTolerateDifference(diff, path) {
    // For 'E' (edit) differences, check if values are equivalent with tolerances
    if (diff.kind === 'E') {
      return this.areValuesEquivalent(path, diff.lhs, diff.rhs);
    }
    
    // For 'A' (array) differences with item edits
    if (diff.kind === 'A' && diff.item.kind === 'E') {
      const arrayPath = `${path}[${diff.index}]`;
      return this.areValuesEquivalent(arrayPath, diff.item.lhs, diff.item.rhs);
    }
    
    return false;
  }

  /**
   * Update verification report format to include tolerated changes
   * @param {Object} result - Verification result
   * @returns {Object} Updated result with tolerance information
   */
  updateVerificationSummary(result) {
    // Calculate total changes including tolerated ones
    let totalChanges = 0;
    let toleratedChanges = 0;
    
    result.interactionResults.forEach(interaction => {
      if (interaction.comparison) {
        // Count total differences
        const headerDiffs = interaction.comparison.headerDiffs.total || 0;
        const bodyDiffs = interaction.comparison.bodyDiffs.total || 0;
        const total = headerDiffs + bodyDiffs;
        
        // Count tolerated differences
        const tolerated = (interaction.comparison.bodyDiffs.tolerated || 0) +
                         (interaction.comparison.headerDiffs.tolerated || 0);
        
        totalChanges += total;
        toleratedChanges += tolerated;
        
        // Update the interaction summary
        interaction.toleratedChanges = tolerated;
        interaction.effectiveChanges = total - tolerated;
      }
    });
    
    // Update the overall summary
    result.summary.totalChanges = totalChanges;
    result.summary.toleratedChanges = toleratedChanges;
    result.summary.effectiveChanges = totalChanges - toleratedChanges;
    
    // Adjust compatibility score to account for tolerated changes
    if (result.summary.total > 0) {
      const compatibleInteractions = result.summary.compatible;
      const toleratedInteractions = result.interactionResults.filter(i => 
        i.comparison && 
        !i.comparison.isCompatible && 
        i.effectiveChanges === 0
      ).length;
      
      result.summary.effectiveCompatible = compatibleInteractions + toleratedInteractions;
      result.summary.effectiveCompatibilityScore = 
        (result.summary.effectiveCompatible / result.summary.total) * 100;
    } else {
      result.summary.effectiveCompatible = 0;
      result.summary.effectiveCompatibilityScore = 0;
    }
    
    return result;
  }

  /**
   * Enhanced version of replayAgainstContract that includes tolerance information
   * @param {string} sessionId - ID of the session to replay
   * @param {string} targetBaseUrl - Base URL of the target API
   * @returns {Promise<Object>} Replay results with tolerance information
   */
  async replayAgainstContract(sessionId, targetBaseUrl) {
    // Get basic replay results
    const results = await super.replayAgainstContract(sessionId, targetBaseUrl);
    
    // Enhance with tolerance information
    return this.updateVerificationSummary(results);
  }

  /**
   * Print enhanced summary with tolerance information
   * @param {string} sessionId - ID of the session to summarize
   */
  printSummary(sessionId) {
    const results = this.replayResults.get(sessionId);
    if (!results) {
      console.error(`No replay results found for session ${sessionId}`);
      return;
    }
    
    console.log('\n' + chalk.bold('=== Contract Compatibility Report with Tolerances ==='));
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
    
    // Show tolerance information
    console.log(`\n${chalk.bold('Tolerance Information:')}`);
    console.log(`Total Changes: ${chalk.white(summary.totalChanges || 0)}`);
    console.log(`Tolerated Changes: ${chalk.blue(summary.toleratedChanges || 0)}`);
    console.log(`Effective Changes: ${chalk.red(summary.effectiveChanges || 0)}`);
    
    const rawScore = summary.compatibilityScore;
    const effectiveScore = summary.effectiveCompatibilityScore || rawScore;
    
    const rawScoreColor = rawScore >= 90 ? 'green' : rawScore >= 75 ? 'yellow' : 'red';
    const effectiveScoreColor = effectiveScore >= 90 ? 'green' : effectiveScore >= 75 ? 'yellow' : 'red';
    
    console.log(`\nRaw Compatibility Score: ${chalk[rawScoreColor](rawScore.toFixed(2) + '%')}`);
    console.log(`Effective Compatibility Score: ${chalk[effectiveScoreColor](effectiveScore.toFixed(2) + '%')}`);
    
    // Create enhanced table for endpoint-level results
    const table = new Table({
      head: [
        chalk.bold('Endpoint'),
        chalk.bold('Status'),
        chalk.bold('Total Diffs'),
        chalk.bold('Tolerated'),
        chalk.bold('Effective'),
        chalk.bold('Compatible')
      ],
      colWidths: [40, 10, 12, 12, 12, 15]
    });
    
    results.interactionResults.forEach(result => {
      if (result.error) {
        table.push([
          `${result.request.method} ${result.request.path}`,
          chalk.red('ERROR'),
          '-',
          '-',
          '-',
          chalk.red('✘')
        ]);
        return;
      }
      
      const isCompatible = result.comparison.isCompatible;
      const statusMatch = result.comparison.statusMatch;
      const totalDiffs = (result.comparison.headerDiffs.total || 0) + 
                        (result.comparison.bodyDiffs.total || 0);
      const toleratedChanges = result.toleratedChanges || 0;
      const effectiveChanges = totalDiffs - toleratedChanges;
      const effectivelyCompatible = effectiveChanges === 0;
      
      table.push([
        `${result.request.method} ${result.request.path}`,
        statusMatch ? chalk.green(result.replayed.statusCode) : 
                    chalk.red(`${result.original.statusCode} → ${result.replayed.statusCode}`),
        totalDiffs > 0 ? chalk.yellow(totalDiffs) : chalk.green('0'),
        toleratedChanges > 0 ? chalk.blue(toleratedChanges) : '0',
        effectiveChanges > 0 ? chalk.red(effectiveChanges) : chalk.green('0'),
        isCompatible ? chalk.green('✓') : 
          effectivelyCompatible ? chalk.blue('✓*') : chalk.red('✘')
      ]);
    });
    
    console.log('\n' + chalk.bold('Endpoint Details:'));
    console.log(table.toString());
    console.log(chalk.blue('✓*') + ' - Compatible with tolerances applied');
    
    // Display tolerated differences
    if (summary.toleratedChanges > 0) {
      console.log('\n' + chalk.bold('Tolerated Changes:'));
      let toleratedCount = 0;
      
      results.interactionResults.forEach(result => {
        if (!result.comparison || result.toleratedChanges <= 0) {
          return;
        }
        
        const endpoint = `${result.request.method} ${result.request.path}`;
        
        // Show timestamp drifts
        result.comparison.bodyDiffs.modified
          .filter(diff => this.isLikelyTimestamp(diff.path, diff.original) || 
                       this.isLikelyTimestamp(diff.path, diff.replayed))
          .forEach(diff => {
            if (this.areTimestampsEquivalent(diff.original, diff.replayed)) {
              console.log(`${chalk.blue('↔')} ${chalk.cyan(endpoint)} - Timestamp drift within ${
                this.options.tolerances.timestampDriftSeconds}s at ${diff.path}:`);
              console.log(`   ${chalk.dim(diff.original)} → ${chalk.dim(diff.replayed)}`);
              toleratedCount++;
            }
          });
        
        // Show UUID changes
        if (this.options.tolerances.ignoreUUIDs) {
          result.comparison.bodyDiffs.modified
            .filter(diff => this.isLikelyUUID('', diff.original) || this.isLikelyUUID('', diff.replayed))
            .forEach(diff => {
              console.log(`${chalk.blue('🆔')} ${chalk.cyan(endpoint)} - UUID changed at ${diff.path}:`);
              console.log(`   ${chalk.dim(diff.original)} → ${chalk.dim(diff.replayed)}`);
              toleratedCount++;
            });
        }
        
        // Array ordering differences are harder to display meaningfully in console
        
        if (toleratedCount >= 10) {
          console.log(chalk.yellow('... and more tolerated changes (see detailed report)'));
          return;
        }
      });
    }
    
    // Display major compatibility issues
    if (summary.incompatible > 0) {
      console.log('\n' + chalk.bold('Major Compatibility Issues:'));
      let issueCount = 0;
      
      results.interactionResults.forEach(result => {
        if (result.error || !result.comparison || result.comparison.isCompatible) {
          return;
        }
        
        // Skip if all changes were tolerated
        if (result.effectiveChanges === 0) {
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
    
    // Add tolerance configuration information
    console.log('\n' + chalk.bold('Tolerance Configuration:'));
    console.log(`- Timestamp Drift: ±${this.options.tolerances.timestampDriftSeconds}s`);
    console.log(`- Ignore UUIDs: ${this.options.tolerances.ignoreUUIDs ? 'Yes' : 'No'}`);
    console.log(`- Sort Arrays: ${this.options.tolerances.sortArrays ? 'Yes' : 'No'}`);
  }
}

module.exports = SnapshotVerifier;