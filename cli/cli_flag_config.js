class EnhancedSnapshotVerifier {
  constructor(options = {}) {
    this.options = options;
  }

  /**
   * Set comparison strictness
   * @param {boolean} strict - If true, use strict comparison with no tolerances
   * @returns {EnhancedSnapshotVerifier} this instance for chaining
   */
  setStrict(strict) {
    if (typeof strict !== 'boolean') {
      throw new Error('setStrict() expects a boolean argument');
    }

    if (strict) {
      if (!this._originalTolerances) {
        this._originalTolerances = { ...this.options.tolerances };
      }

      this.options.tolerances = {
        timestampDriftSeconds: 0,
        ignoreUUIDs: false,
        sortArrays: false,
        arrayFields: [],
        timestampFields: [],
        uuidFields: []
      };
    } else {
      if (this._originalTolerances) {
        this.options.tolerances = { ...this._originalTolerances };
        delete this._originalTolerances;
      }
    }

    return this;
  }
}
