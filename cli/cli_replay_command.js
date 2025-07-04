// Replay command with strict/tolerant flags
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
      
      // Handle strict/tolerant flags - strict takes precedence if both are specified
      if (options.strict) {
        // Override tolerance settings for strict comparison
        config.tolerances = {
          timestampDriftSeconds: 0,
          ignoreUUIDs: false,
          sortArrays: false
        };
        console.log(chalk.yellow('Strict comparison mode enabled - any deviation will cause a failure'));
      } else if (options.tolerant) {
        // Ensure all tolerance features are enabled
        config.tolerances = {
          ...config.tolerances,
          timestampDriftSeconds: Math.max(config.tolerances.timestampDriftSeconds || 0, 5),
          ignoreUUIDs: true,
          sortArrays: true
        };
        console.log(chalk.blue('Tolerant comparison mode enabled - applying all tolerance rules'));
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

      // Add strict/tolerant mode info to results
      results.comparisonMode = options.strict ? 'strict' : (options.tolerant ? 'tolerant' : 'default');

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
          comparisonMode: results.comparisonMode,
          timestamp: new Date().toISOString()
        }, null, 2));
      }

      // In strict mode, fail if there are ANY differences
      if (options.strict && (
        results.summary.totalChanges > 0 || 
        results.summary.incompatible > 0 || 
        results.summary.errors > 0
      )) {
        console.error(chalk.red(`Strict comparison failed: ${results.summary.totalChanges || 0} total changes detected`));
        process.exit(1);
      }
      // Otherwise check threshold for exit code
      else {
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