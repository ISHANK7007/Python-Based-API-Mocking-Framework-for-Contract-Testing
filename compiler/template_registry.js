#!/usr/bin/env node
const fs = require('fs').promises;
const path = require('path');
const { program } = require('commander');
const chalk = require('chalk');
const yaml = require('js-yaml');
const { table } = require('table');

const { EnhancedSnapshotVerifier } = require('./enhanced-snapshot-verifier');
const { ContractLoader } = require('./contract-loader');

// Main program definition
program
  .name('mockapi')
  .description('API mocking and verification tool')
  .version('1.0.0');

// Replay command
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
  .action(async (sessionFile, options) => {
    try {
      // Process options
      const threshold = parseFloat(options.threshold);
      if (isNaN(threshold) || threshold < 0 || threshold > 100) {
        console.error(chalk.red('Invalid threshold. Must be a number between 0 and 100.'));
        process.exit(1);
      }

      // Load configuration if specified
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
      
      // Verbose logging
      if (options.verbose) {
        console.log(chalk.cyan('Starting session replay and verification...'));
        console.log(chalk.dim('Session file:'), sessionFile);
        console.log(chalk.dim('Contract file:'), options.contract);
        console.log(chalk.dim('Configuration:'), JSON.stringify(config, null, 2));
      }

      // Load contract
      const contractLoader = new ContractLoader();
      const contract = await loadContract(options.contract, contractLoader);

      if (!contract) {
        console.error(chalk.red(`Failed to load contract: ${options.contract}`));
        process.exit(1);
      }

      // Initialize verifier
      const verifier = new EnhancedSnapshotVerifier({
        useDynamicResponses: options.dynamic,
        ...config
      });

      // Configure verifier from contract
      if (options.dynamic) {
        verifier.configureFromContract(contract);
      }

      // Load session directly from file
      const sessionPath = path.resolve(sessionFile);
      const session = await loadSession(sessionPath);

      if (!session) {
        console.error(chalk.red(`Failed to load session: ${sessionFile}`));
        process.exit(1);
      }

      // Set up mock target URL since we're using template-based verification
      const targetUrl = 'http://localhost:8000';
      
      // Process session ID and store session data
      const sessionId = session.sessionId || `session-${Date.now()}`;
      verifier.originalSessions.set(sessionId, {
        filePath: sessionPath,
        data: session
      });

      // Perform verification
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
      if (options.format === 'text' && !options.verbose) {
        printSummary(results);
      }

      // For JSON format, print JSON output
      if (options.format === 'json') {
        console.log(JSON.stringify({
          summary: results.summary,
          sessionId: sessionId,
          contractFile: options.contract,
          timestamp: new Date().toISOString()
        }, null, 2));
      }

      // Check threshold for exit code
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
    } catch (error) {
      console.error(chalk.red('Error during replay:'), error);
      process.exit(1);
    }
  });

/**
 * Load a contract file
 * @param {string} contractFile - Path to contract file
 * @param {ContractLoader} contractLoader - Contract loader
 * @returns {Promise<Object>} Loaded contract
 */
async function loadContract(contractFile, contractLoader) {
  try {
    const contractPath = path.resolve(contractFile);
    const contractContent = await fs.readFile(contractPath, 'utf8');
    const contractExt = path.extname(contractPath).toLowerCase();
    
    let contract;
    
    if (contractExt === '.json') {
      contract = JSON.parse(contractContent);
    } else if (contractExt === '.yaml' || contractExt === '.yml') {
      contract = yaml.load(contractContent);
    } else {
      throw new Error(`Unsupported contract format: ${contractExt}`);
    }
    
    // Load through ContractLoader for validation if needed
    return contractLoader.load(contract);
  } catch (error) {
    console.error(`Failed to load contract: ${error.message}`);
    return null;
  }
}

/**
 * Load a session file
 * @param {string} sessionFile - Path to session file
 * @returns {Promise<Object>} Loaded session
 */
async function loadSession(sessionFile) {
  try {
    const sessionContent = await fs.readFile(sessionFile, 'utf8');
    return JSON.parse(sessionContent);
  } catch (error) {
    console.error(`Failed to load session: ${error.message}`);
    return null;
  }
}

/**
 * Generate a text report
 * @param {Object} results - Verification results
 * @returns {string} Text report
 */
function generateTextReport(results) {
  let report = '=== API Contract Compatibility Report ===\n\n';
  
  // Add summary
  report += 'Summary:\n';
  report += `Total Interactions: ${results.summary.total}\n`;
  report += `Compatible: ${results.summary.compatible}\n`;
  report += `Incompatible: ${results.summary.incompatible}\n`;
  report += `Errors: ${results.summary.errors || 0}\n`;
  report += `Compatibility Score: ${results.summary.compatibilityScore.toFixed(2)}%\n`;
  
  if (results.summary.toleratedChanges !== undefined) {
    report += `\nTolerance Information:\n`;
    report += `Total Changes: ${results.summary.totalChanges || 0}\n`;
    report += `Tolerated Changes: ${results.summary.toleratedChanges || 0}\n`;
    report += `Effective Changes: ${results.summary.effectiveChanges || 0}\n`;
    report += `Effective Compatibility Score: ${results.summary.effectiveCompatibilityScore.toFixed(2)}%\n`;
  }
  
  // Add details
  report += '\nEndpoint Details:\n';
  
  const tableData = [
    ['Endpoint', 'Status', 'Total Diffs', 'Compatible']
  ];
  
  results.interactionResults.forEach(result => {
    if (result.error) {
      tableData.push([
        `${result.request.method} ${result.request.path}`,
        'ERROR',
        '-',
        'No'
      ]);
      return;
    }
    
    const totalDiffs = (result.comparison.headerDiffs.total || 0) + 
                      (result.comparison.bodyDiffs.total || 0);
    
    tableData.push([
      `${result.request.method} ${result.request.path}`,
      result.comparison.statusMatch ? 
        `${result.replayed.statusCode}` : 
        `${result.original.statusCode} → ${result.replayed.statusCode}`,
      totalDiffs.toString(),
      result.comparison.isCompatible ? 'Yes' : 'No'
    ]);
  });
  
  report += table(tableData);
  
  // Add incompatibilities
  const incompatibilities = results.interactionResults
    .filter(result => !result.error && !result.comparison.isCompatible)
    .flatMap(result => {
      const endpoint = `${result.request.method} ${result.request.path}`;
      const issues = [];
      
      if (!result.comparison.statusMatch) {
        issues.push(`${endpoint} - Status code changed: ${result.original.statusCode} → ${result.replayed.statusCode}`);
      }
      
      result.comparison.bodyDiffs.removed.forEach(field => {
        issues.push(`${endpoint} - Removed field: ${field.path}`);
      });
      
      result.comparison.bodyDiffs.incompatible
        .filter(diff => diff.reason && diff.reason.includes('Type changed'))
        .forEach(field => {
          issues.push(`${endpoint} - ${field.reason} at ${field.path}`);
        });
      
      return issues;
    });
  
  if (incompatibilities.length > 0) {
    report += '\nIncompatibilities:\n';
    incompatibilities.forEach((issue, index) => {
      report += `${index + 1}. ${issue}\n`;
    });
  }
  
  return report;
}

/**
 * Print a summary of the results
 * @param {Object} results - Verification results
 */
function printSummary(results) {
  console.log(chalk.bold('\n=== API Contract Compatibility Summary ==='));
  
  const summary = results.summary;
  console.log(`Total Interactions: ${chalk.white(summary.total)}`);
  console.log(`Compatible: ${chalk.green(summary.compatible)}`);
  console.log(`Incompatible: ${chalk.red(summary.incompatible)}`);
  if (summary.errors) {
    console.log(`Errors: ${chalk.yellow(summary.errors)}`);
  }
  
  // Show tolerance information if available
  if (summary.toleratedChanges !== undefined) {
    console.log(`\nTotal Changes: ${chalk.white(summary.totalChanges || 0)}`);
    console.log(`Tolerated Changes: ${chalk.blue(summary.toleratedChanges || 0)}`);
    console.log(`Effective Changes: ${chalk.red(summary.effectiveChanges || 0)}`);
  }
  
  const rawScore = summary.compatibilityScore;
  const effectiveScore = summary.effectiveCompatibilityScore !== undefined ? 
    summary.effectiveCompatibilityScore : rawScore;
  
  const scoreColor = effectiveScore >= 90 ? 'green' : effectiveScore >= 75 ? 'yellow' : 'red';
  
  console.log(`\nCompatibility Score: ${chalk[scoreColor](effectiveScore.toFixed(2) + '%')}`);
  
  if (summary.incompatible > 0) {
    console.log(chalk.yellow('\nIncompatibilities found. See detailed report for more information.'));
  }
}

// Required by the CLI tool to load contracts
class ContractLoader {
  /**
   * Loads and validates a contract
   * @param {Object} contract - Contract object
   * @returns {Object} Validated contract
   */
  load(contract) {
    // Here you would normally validate the contract structure
    // For now, we'll just return it as is
    return contract;
  }
}

// Parse command-line arguments
program.parse(process.argv);

// If no arguments, show help
if (process.argv.length <= 2) {
  program.help();
}