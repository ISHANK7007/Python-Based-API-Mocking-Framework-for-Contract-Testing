/**
 * Enhanced session format with metadata and tagging
 */
class SessionRecorder {
  // ... existing methods ...

  async saveSession(sessionId) {
    const session = this.sessions.find(s => s.id === sessionId) || 
                   (this.currentSession && this.currentSession.id === sessionId ? 
                    this.currentSession : null);
    
    if (!session) {
      throw new Error(`Session with ID ${sessionId} not found`);
    }
    
    // Create filename based on timestamp
    const timestamp = new Date(session.startTime).getTime();
    const filename = `session_${timestamp}.json`;
    const filePath = path.join(this.options.logDirectory, filename);
    
    // Ensure metadata exists
    if (!session.metadata) {
      session.metadata = {};
    }
    
    // Add default metadata if not present
    session.metadata = {
      createdAt: new Date().toISOString(),
      environment: process.env.NODE_ENV || 'development',
      tags: session.metadata.tags || [],
      description: session.metadata.description || '',
      creator: session.metadata.creator || process.env.USER || 'unknown',
      ...session.metadata
    };
    
    // Prepare the session data according to our defined format
    const sessionData = {
      sessionId: session.id,
      timestamp: session.timestamp,
      metadata: session.metadata,
      interactions: session.interactions.map(interaction => ({
        timestamp: interaction.timestamp,
        requestHash: interaction.requestHash,
        tags: interaction.tags || [],
        request: {
          method: interaction.request.method,
          path: interaction.request.path,
          headers: interaction.request.headers,
          query: interaction.request.query,
          body: interaction.request.body
        },
        response: {
          statusCode: interaction.response.statusCode,
          headers: interaction.response.headers,
          body: interaction.response.body
        }
      }))
    };
    
    try {
      await fs.writeFile(filePath, JSON.stringify(sessionData, null, 2));
      console.log(`Session saved to ${filePath}`);
      return filePath;
    } catch (error) {
      console.error('Failed to save session:', error);
      throw error;
    }
  }
  
  /**
   * Add tags to a session
   * @param {string} sessionId - ID of the session to tag
   * @param {Array<string>} tags - Tags to add
   * @returns {Object} Updated session
   */
  tagSession(sessionId, tags) {
    const session = this.sessions.find(s => s.id === sessionId) || 
                   (this.currentSession && this.currentSession.id === sessionId ? 
                    this.currentSession : null);
    
    if (!session) {
      throw new Error(`Session with ID ${sessionId} not found`);
    }
    
    // Ensure metadata exists
    if (!session.metadata) {
      session.metadata = {};
    }
    
    // Ensure tags array exists
    if (!session.metadata.tags) {
      session.metadata.tags = [];
    }
    
    // Add new tags (avoid duplicates)
    const newTags = Array.isArray(tags) ? tags : [tags];
    newTags.forEach(tag => {
      if (!session.metadata.tags.includes(tag)) {
        session.metadata.tags.push(tag);
      }
    });
    
    return session;
  }
  
  /**
   * Add metadata to a session
   * @param {string} sessionId - ID of the session
   * @param {Object} metadata - Metadata to add or update
   * @returns {Object} Updated session
   */
  updateSessionMetadata(sessionId, metadata) {
    const session = this.sessions.find(s => s.id === sessionId) || 
                   (this.currentSession && this.currentSession.id === sessionId ? 
                    this.currentSession : null);
    
    if (!session) {
      throw new Error(`Session with ID ${sessionId} not found`);
    }
    
    // Ensure metadata exists
    if (!session.metadata) {
      session.metadata = {};
    }
    
    // Update metadata
    session.metadata = {
      ...session.metadata,
      ...metadata
    };
    
    return session;
  }
  
  /**
   * Add tags to a specific interaction
   * @param {string} sessionId - ID of the session
   * @param {number} interactionIndex - Index of the interaction
   * @param {Array<string>} tags - Tags to add
   * @returns {Object} Updated interaction
   */
  tagInteraction(sessionId, interactionIndex, tags) {
    const session = this.sessions.find(s => s.id === sessionId) || 
                   (this.currentSession && this.currentSession.id === sessionId ? 
                    this.currentSession : null);
    
    if (!session) {
      throw new Error(`Session with ID ${sessionId} not found`);
    }
    
    if (!session.interactions[interactionIndex]) {
      throw new Error(`Interaction at index ${interactionIndex} not found`);
    }
    
    const interaction = session.interactions[interactionIndex];
    
    // Ensure tags array exists
    if (!interaction.tags) {
      interaction.tags = [];
    }
    
    // Add new tags (avoid duplicates)
    const newTags = Array.isArray(tags) ? tags : [tags];
    newTags.forEach(tag => {
      if (!interaction.tags.includes(tag)) {
        interaction.tags.push(tag);
      }
    });
    
    return interaction;
  }
}