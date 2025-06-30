/**
 * Print a summary of the results
 * @param {Object} results - Verification results
 */
function printSummary(results) {
  console.log(chalk.bold('\n=== API Contract Compatibility Summary ==='));
  
  // Show comparison mode
  if (results.comparisonMode) {
    const modeColor = {
      'strict': chalk.red.bold,
      'tolerant': chalk.blue.bold,
      'default': chalk.white
    }[results.comparisonMode];
    
    const modeText = {
      'strict': 'STRICT MODE - Exact equality required',
      'tolerant': 'TOLERANT MODE - All tolerance rules applied',
      'default': 'DEFAULT MODE - Using configured tolerances'
    }[results.comparisonMode];
    
    console.log(modeColor(modeText));
    console.log('');
  }
  
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