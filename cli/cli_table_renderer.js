// Replay command with tagging and filtering options
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
  .option('--filter-methods <methods>', 'Filter by HTTP methods (comma-separated: GET,POST)')
  .option('--filter-routes <routes>', 'Filter by route patterns (comma-separated)')
  .option('--filter-tags <tags>', 'Filter by interaction tags (comma-separated)')
  .option('--filter-session-tags <sessionTags>', 'Filter by session tags (comma-separated)')
  .action(async (sessionFile, options) => {
    try {
      // Start timing overall execution
      const totalStartTime = process.hrtime();
      
      // ... existing implementation ...
      
      // Initialize verifier
      const verifier = new EnhancedSnapshotVerifier({
        useDynamicResponses: options.dynamic,
        ...config
      });
      
      // Set up filtering if any filter options provided
      if (options.filterMethods || options.filterRoutes || 
          options.filterTags || options.filterSessionTags) {
        
        const filter = {};
        
        if (options.filterMethods) {
          filter.methods = options.filterMethods.split(',').map(m => m.trim());
        }
        
        if (options.filterRoutes) {
          filter.routes = options.filterRoutes.split(',').map(r => r.trim());
        }
        
        if (options.filterTags) {
          filter.tags = options.filterTags.split(',').map(t => t.trim());
        }
        
        if (options.filterSessionTags) {
          filter.sessionTags = options.filterSessionTags.split(',').map(t => t.trim());
        }
        
        verifier.setFilter(filter);
        
        if (options.verbose) {
          console.log(chalk.cyan('Applying filters:'), filter);
        }
      }
      
      // ... rest of implementation ...
      
      // Include filter information in results
      if (verifier.filter) {
        results.filter = verifier.filter;
      }
      
      // ... rest of implementation ...
      
      // Print filter summary if filtering was applied
      if (results.filteredStats && results.filteredStats.filterApplied) {
        console.log(chalk.cyan('\n=== Filter Summary ==='));
        console.log(`Original interactions: ${chalk.white(results.filteredStats.originalInteractionCount)}`);
        console.log(`Filtered interactions: ${chalk.white(results.filteredStats.filteredInteractionCount)}`);
        console.log(`Filter ratio: ${chalk.yellow((results.filteredStats.filteredInteractionCount / 
                                                 results.filteredStats.originalInteractionCount * 100).toFixed(2))}%`);
      }
      
      // ... rest of implementation ...
    } catch (error) {
      console.error(chalk.red('Error during replay:'), error);
      process.exit(1);
    }
  });

// Add a new command for tagging sessions
program
  .command('tag <sessionFile>')
  .description('Add tags to a session or update session metadata')
  .option('--tags <tags>', 'Comma-separated tags to add to the session')
  .option('--description <description>', 'Description for the session')
  .option('--metadata <json>', 'JSON string with additional metadata to add')
  .option('--output <outputFile>', 'Path to save the updated session file')
  .action(async (sessionFile, options) => {
    try {
      // Load the session file
      const sessionPath = path.resolve(sessionFile);
      let session = await loadSession(sessionPath);
      
      if (!session) {
        console.error(chalk.red(`Failed to load session: ${sessionFile}`));
        process.exit(1);
      }
      
      // Create a session recorder to use its tagging capabilities
      const recorder = new SessionRecorder({
        logDirectory: path.dirname(sessionPath)
      });
      
      // Add the session to the recorder's list
      recorder.sessions.push(session);
      
      // Add tags if provided
      if (options.tags) {
        const tags = options.tags.split(',').map(t => t.trim());
        recorder.tagSession(session.sessionId, tags);
        
        console.log(chalk.green(`Added tags to session ${session.sessionId}:`), tags);
      }
      
      // Update metadata
      const metadata = {};
      
      if (options.description) {
        metadata.description = options.description;
      }
      
      if (options.metadata) {
        try {
          const additionalMetadata = JSON.parse(options.metadata);
          Object.assign(metadata, additionalMetadata);
        } catch (error) {
          console.error(chalk.red(`Invalid JSON for metadata: ${error.message}`));
          process.exit(1);
        }
      }
      
      if (Object.keys(metadata).length > 0) {
        recorder.updateSessionMetadata(session.sessionId, metadata);
        console.log(chalk.green(`Updated metadata for session ${session.sessionId}`));
      }
      
      // Save the updated session
      const outputPath = options.output || sessionPath;
      await recorder.saveSession(session.sessionId);
      
      console.log(chalk.green(`Session saved to ${outputPath}`));
    } catch (error) {
      console.error(chalk.red('Error tagging session:'), error);
      process.exit(1);
    }
  });

// Add a command for interacting with session metadata
program
  .command('session <action>')
  .description('Session management commands')
  .option('--file <sessionFile>', 'Path to session file')
  .option('--dir <directory>', 'Directory with session files')
  .option('--tags <tags>', 'Filter by tags (comma-separated)')
  .option('--format <format>', 'Output format (json, text)', 'text')
  .action(async (action, options) => {
    try {
      switch (action) {
        case 'list':
          await listSessions(options);
          break;
        case 'show':
          await showSession(options);
          break;
        default:
          console.error(chalk.red(`Unknown session action: ${action}`));
          process.exit(1);
      }
    } catch (error) {
      console.error(chalk.red(`Error in session command: ${error.message}`));
      process.exit(1);
    }
  });

/**
 * List all sessions in a directory with optional tag filtering
 * @param {Object} options - Command options
 */
async function listSessions(options) {
  const dir = options.dir || './session-logs';
  
  try {
    const files = await fs.readdir(dir);
    const sessionFiles = files.filter(file => file.startsWith('session_') && file.endsWith('.json'));
    
    const sessions = [];
    
    for (const file of sessionFiles) {
      const filePath = path.join(dir, file);
      try {
        const session = await loadSession(filePath);
        
        // Filter by tags if specified
        if (options.tags) {
          const filterTags = options.tags.split(',').map(t => t.trim());
          const sessionTags = session.metadata?.tags || [];
          
          const hasMatchingTags = filterTags.some(tag => sessionTags.includes(tag));
          if (!hasMatchingTags) continue;
        }
        
        sessions.push({
          id: session.sessionId,
          file: file,
          timestamp: session.timestamp,
          tags: session.metadata?.tags || [],
          description: session.metadata?.description || '',
          interactions: session.interactions.length
        });
      } catch (error) {
        console.warn(chalk.yellow(`Skipping invalid session file: ${file}`));
      }
    }
    
    if (options.format === 'json') {
      console.log(JSON.stringify(sessions, null, 2));
    } else {
      console.log(chalk.cyan('\n=== Sessions ==='));
      
      if (sessions.length === 0) {
        console.log(chalk.yellow('No sessions found'));
        return;
      }
      
      const table = new Table({
        head: [
          chalk.bold('ID'),
          chalk.bold('File'),
          chalk.bold('Timestamp'),
          chalk.bold('Tags'),
          chalk.bold('Interactions')
        ],
        colWidths: [30, 30, 25, 25, 15]
      });
      
      sessions.forEach(session => {
        table.push([
          session.id,
          session.file,
          session.timestamp,
          session.tags.join(', '),
          session.interactions
        ]);
      });
      
      console.log(table.toString());
    }
  } catch (error) {
    console.error(chalk.red(`Error listing sessions: ${error.message}`));
  }
}

/**
 * Show details of a specific session
 * @param {Object} options - Command options
 */
async function showSession(options) {
  if (!options.file) {
    console.error(chalk.red('--file option is required for show command'));
    process.exit(1);
  }
  
  try {
    const sessionPath = path.resolve(options.file);
    const session = await loadSession(sessionPath);
    
    if (!session) {
      console.error(chalk.red(`Failed to load session: ${options.file}`));
      process.exit(1);
    }
    
    if (options.format === 'json') {
      // Filter out interaction bodies to reduce output
      const filteredSession = {
        ...session,
        interactions: session.interactions.map(interaction => ({
          timestamp: interaction.timestamp,
          tags: interaction.tags || [],
          request: {
            method: interaction.request.method,
            path: interaction.request.path,
          },
          response: {
            statusCode: interaction.response.statusCode
          }
        }))
      };
      
      console.log(JSON.stringify(filteredSession, null, 2));
    } else {
      console.log(chalk.cyan('\n=== Session Details ==='));
      console.log(chalk.bold('ID:'), session.sessionId);
      console.log(chalk.bold('Timestamp:'), session.timestamp);
      console.log(chalk.bold('Tags:'), session.metadata?.tags?.join(', ') || 'none');
      console.log(chalk.bold('Description:'), session.metadata?.description || 'none');
      
      console.log(chalk.bold('\nMetadata:'));
      Object.entries(session.metadata || {}).forEach(([key, value]) => {
        if (key !== 'tags' && key !== 'description') {
          console.log(`  ${key}: ${typeof value === 'object' ? JSON.stringify(value) : value}`);
        }
      });
      
      console.log(chalk.bold(`\nInteractions (${session.interactions.length}):`));
      
      const table = new Table({
        head: [
          chalk.bold('#'),
          chalk.bold('Method'),
          chalk.bold('Path'),
          chalk.bold('Status'),
          chalk.bold('Tags')
        ],
        colWidths: [5, 10, 60, 10, 20]
      });
      
      session.interactions.forEach((interaction, index) => {
        table.push([
          index + 1,
          interaction.request.method,
          interaction.request.path,
          interaction.response.statusCode,
          (interaction.tags || []).join(', ')
        ]);
      });
      
      console.log(table.toString());
    }
  } catch (error) {
    console.error(chalk.red(`Error showing session: ${error.message}`));
    process.exit(1);
  }
}