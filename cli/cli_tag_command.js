/**
 * Generate a text report
 * @param {Object} results - Verification results
 * @returns {string} Text report
 */
function generateTextReport(results) {
  let report = '=== API Contract Compatibility Report ===\n\n';
  
  // Add mode information
  if (results.comparisonMode) {
    const modeText = {
      'strict': 'STRICT - Exact equality required, no tolerances applied',
      'tolerant': 'TOLERANT - All tolerance rules applied (timestamps, UUIDs, array sorting)',
      'default': 'DEFAULT - Using configured tolerance settings'
    }[results.comparisonMode];
    
    report += `Comparison Mode: ${modeText}\n\n`;
  }
  
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
  
  // Rest of the function remains the same
  // ... existing code ...

  return report;
}