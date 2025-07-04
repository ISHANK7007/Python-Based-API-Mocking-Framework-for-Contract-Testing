/**
 * Enhanced SnapshotVerifier with filtering capabilities
 */
class EnhancedSnapshotVerifier extends SnapshotVerifier {
  constructor(options = {}) {
    super(options);
    
    // Initialize response resolver
    this.responseResolver = new ResponseResolver({
      defaultContext: options.defaultContext || {},
      cacheCapacity: options.cacheCapacity || 1000
    });
    
    // Initialize filter
    this.filter = null;
  }
  
  /**
   * Set filter criteria for replaying interactions
   * @param {Object} filterCriteria - Filter criteria
   * @returns {EnhancedSnapshotVerifier} this instance for chaining
   */
  setFilter(filterCriteria) {
    this.filter = filterCriteria;
    return this;
  }
  
  /**
   * Check if an interaction matches filter criteria
   * @param {Object} interaction - Interaction to check
   * @returns {boolean} True if interaction matches filter
   */
  matchesFilter(interaction) {
    // If no filter set, include all interactions
    if (!this.filter) {
      return true;
    }
    
    // Method filter
    if (this.filter.methods && this.filter.methods.length > 0) {
      const methodMatches = this.filter.methods.some(m => 
        interaction.request.method.toUpperCase() === m.toUpperCase()
      );
      if (!methodMatches) {
        return false;
      }
    }
    
    // Path/route filter (supports regex patterns)
    if (this.filter.routes && this.filter.routes.length > 0) {
      const pathMatches = this.filter.routes.some(routePattern => {
        // If it's a regex pattern string (e.g. /api/.*)
        if (routePattern.startsWith('/') && routePattern.includes('*')) {
          const regexPattern = routePattern
            .replace(/\//g, '\\/') // Escape slashes
            .replace(/\*/g, '.*'); // Replace * with .*
          const regex = new RegExp(`^${regexPattern}$`);
          return regex.test(interaction.request.path);
        }
        // Simple string comparison
        return interaction.request.path.includes(routePattern);
      });
      if (!pathMatches) {
        return false;
      }
    }
    
    // Tags filter (interaction level)
    if (this.filter.tags && this.filter.tags.length > 0) {
      // If interaction has no tags, it doesn't match a tag filter
      if (!interaction.tags || interaction.tags.length === 0) {
        return false;
      }
      
      const tagMatches = this.filter.tags.some(tag => 
        interaction.tags.includes(tag)
      );
      if (!tagMatches) {
        return false;
      }
    }
    
    // All filters passed
    return true;
  }
  
  /**
   * Filter a session's interactions based on current filter
   * @param {Object} session - Session to filter
   * @returns {Object} Filtered session
   */
  filterSession(session) {
    // If no filter set, return original session
    if (!this.filter) {
      return session;
    }
    
    // Check session-level tag filter
    if (this.filter.sessionTags && this.filter.sessionTags.length > 0) {
      const sessionTags = session.metadata?.tags || [];
      const sessionTagMatches = this.filter.sessionTags.some(tag => 
        sessionTags.includes(tag)
      );
      
      // If session doesn't match tag filter, return empty session
      if (!sessionTagMatches) {
        return {
          ...session,
          interactions: []
        };
      }
    }
    
    // Filter interactions
    const filteredInteractions = session.interactions.filter(
      interaction => this.matchesFilter(interaction)
    );
    
    return {
      ...session,
      interactions: filteredInteractions,
      filtered: true,
      originalInteractionCount: session.interactions.length,
      filteredInteractionCount: filteredInteractions.length
    };
  }
  
  /**
   * Replay a session against a contract with filtering
   * @param {string} sessionId - ID of the session to replay
   * @param {string} targetBaseUrl - Base URL of the target API
   * @param {Object} options - Additional options
   * @returns {Promise<Object>} Replay results
   */
  async replayAgainstContract(sessionId, targetBaseUrl, options = {}) {
    const sessionEntry = this.originalSessions.get(sessionId);
    if (!sessionEntry) {
      throw new Error(`Session ${sessionId} not found. Make sure to load it first.`);
    }
    
    // Get the original session
    const originalSession = sessionEntry.data;
    
    // Apply filtering if needed
    const session = this.filterSession(originalSession);
    
    // Original implementation continues, but uses filtered session...
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
      },
      filter: this.filter,
      filteredStats: {
        originalInteractionCount: originalSession.interactions.length,
        filteredInteractionCount: session.interactions.length,
        filterApplied: !!this.filter
      }
    };
    
    // Process each interaction in the filtered session
    for (const interaction of session.interactions) {
      // ... rest of the implementation ...
    }
    
    // ... rest of the method ...
    
    return results;
  }
}