// Example configuration with tolerances
const verifier = new SnapshotVerifier({
  logDirectory: './session-logs',
  diffOutputDirectory: './diff-reports',
  tolerances: {
    timestampDriftSeconds: 5,     // Allow ±5s timestamp variation
    ignoreUUIDs: true,            // Ignore UUIDs in comparison
    sortArrays: true,             // Sort arrays before comparison
    arrayFields: [                // Specific array fields to sort
      'products', 
      'items', 
      'results'
    ],
    timestampFields: [            // Fields likely to contain timestamps
      'timestamp', 'date', 'time', 'created', 'updated', 
      'createdAt', 'updatedAt', 'created_at', 'updated_at'
    ],
    uuidFields: [                 // Fields likely to contain UUIDs
      'id', 'uuid', 'guid', 'trackingId', 'requestId'
    ]
  }
});

// Usage is the same as before
await verifier.loadAllSessions();
const results = await verifier.verifyCompatibility('product-api-v1', 'http://localhost:3001');

// The results now include information about tolerated differences
console.log(`Regular compatibility score: ${results.summary.compatibilityScore.toFixed(2)}%`);
console.log(`Effective compatibility score: ${results.summary.effectiveCompatibilityScore.toFixed(2)}%`);
console.log(`Total changes: ${results.summary.totalChanges}`);
console.log(`Tolerated changes: ${results.summary.toleratedChanges}`);