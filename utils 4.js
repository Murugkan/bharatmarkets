// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// UTILS.JS - SHARED UTILITY FUNCTIONS
// Reusable across: data.html, app-import.js, index.html
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DATA EXTRACTION (Dynamic, works with any JSON structure)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Extract array from any nested JSON structure
 * Works with: array, {data: [...]}, {stocks: [...]}, {quotes: {TICKER: {...}}}, {stocks: {TICKER: {...}}}
 */
function extractArray(data) {
    if (!data) return [];
    
    // If already an array, return it
    if (Array.isArray(data)) return data;
    
    // If object, find array or object-of-records
    if (typeof data === 'object') {
        // Check for common array keys first
        for (var key in data) {
            if (key === 'stocks' || key === 'data' || key === 'items' || key === 'records') {
                if (Array.isArray(data[key])) {
                    return data[key];
                }
            }
            // Check if value is array
            if (Array.isArray(data[key])) {
                return data[key];
            }
        }
        
        // Handle quotes object pattern (prices.json has {quotes: {TICKER: {...}}})
        if (data.quotes && typeof data.quotes === 'object') {
            var quotesArray = Object.values(data.quotes);
            if (quotesArray.length > 0) {
                return quotesArray;
            }
        }
        
        // Handle stocks object pattern (fundamentals.json has {stocks: {TICKER: {...}}})
        if (data.stocks && typeof data.stocks === 'object' && !Array.isArray(data.stocks)) {
            var stocksArray = Object.values(data.stocks);
            if (stocksArray.length > 0) {
                return stocksArray;
            }
        }
        
        // Last resort: convert any object values to array
        var allValues = Object.values(data);
        if (allValues.length > 0 && typeof allValues[0] === 'object') {
            return allValues;
        }
    }
    
    return [];
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// LOOKUP & MERGING (O(1) merge performance)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Build lookup table for O(1) merge by key
 * Handles field name variations (ticker, sym, SYM, symbol)
 */
function buildLookup(records, keyField) {
    var lookup = {};
    if (!Array.isArray(records)) return lookup;
    
    records.forEach(function(rec) {
        if (!rec) return;
        
        // Find key (try common variations)
        var key = rec[keyField] || rec.ticker || rec.sym || rec.SYM || rec.symbol;
        
        if (key) {
            lookup[key] = rec;
        }
    });
    
    return lookup;
}

/**
 * Merge all fields from source into base record
 * Skips null/undefined values, preserves nesting
 */
function mergeRecords(baseRecord, sourceRecord) {
    if (!sourceRecord) return baseRecord;
    
    for (var field in sourceRecord) {
        if (field !== 'ticker' && 
            field !== 'sym' && 
            sourceRecord[field] !== null && 
            sourceRecord[field] !== undefined) {
            baseRecord[field] = sourceRecord[field];
        }
    }
    
    return baseRecord;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// VALIDATION (Using SCHEMA and CONFIG)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Validate single field against config
 * Returns {valid: boolean, error: string}
 */
function validateField(fieldName, value, fieldConfig) {
    if (!fieldConfig) return { valid: true, error: null };
    
    // Check required
    if (fieldConfig.required && (value === null || value === undefined || value === '')) {
        return { 
            valid: false, 
            error: fieldName + ' is required' 
        };
    }
    
    // Check type
    if (value !== null && value !== undefined && value !== '') {
        if (fieldConfig.type === 'string' && typeof value !== 'string') {
            return { 
                valid: false, 
                error: fieldName + ' must be string' 
            };
        }
        if (fieldConfig.type === 'number' && typeof value !== 'number') {
            return { 
                valid: false, 
                error: fieldName + ' must be number' 
            };
        }
    }
    
    // Check min
    if (fieldConfig.min !== undefined && value < fieldConfig.min) {
        return { 
            valid: false, 
            error: fieldName + ' must be >= ' + fieldConfig.min 
        };
    }
    
    // Check enum
    if (fieldConfig.enum && value && fieldConfig.enum.indexOf(value) === -1) {
        return { 
            valid: false, 
            error: fieldName + ' must be one of: ' + fieldConfig.enum.join(', ') 
        };
    }
    
    return { valid: true, error: null };
}

/**
 * Validate entire record against schema
 * Returns {valid: boolean, errors: [{field, error}]}
 */
function validateRecord(record, schemaObj, configObj) {
    var errors = [];
    
    if (!schemaObj || !schemaObj.stocks) return { valid: true, errors: [] };
    
    var schema = schemaObj.stocks;
    var config = configObj || CONFIG;
    
    // Check required fields from schema
    if (schema.required) {
        schema.required.forEach(function(field) {
            if (!record[field] || record[field] === '') {
                errors.push({
                    field: field,
                    error: field + ' is required'
                });
            }
        });
    }
    
    // Validate each field
    for (var field in record) {
        if (field === 'ticker') {
            var tickerValidation = validateField(
                field, 
                record[field], 
                config.VALIDATION && config.VALIDATION[field]
            );
            if (!tickerValidation.valid) {
                errors.push({
                    field: field,
                    error: tickerValidation.error
                });
            }
        }
    }
    
    return {
        valid: errors.length === 0,
        errors: errors
    };
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DATABASE OPERATIONS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Open IndexedDB with config
 */
function openDB(config) {
    return new Promise(function(resolve, reject) {
        var request = indexedDB.open(config.DB.name, config.DB.version);
        
        request.onsuccess = function() {
            resolve(request.result);
        };
        
        request.onerror = function() {
            reject(new Error('Failed to open DB: ' + request.error));
        };
        
        request.onupgradeneeded = function(e) {
            var db = e.target.result;
            if (db.objectStoreNames.contains(config.DB.store)) {
                db.deleteObjectStore(config.DB.store);
            }
            db.createObjectStore(config.DB.store, { keyPath: config.DB.keyPath });
        };
    });
}

/**
 * Clear all records from IndexedDB
 */
function clearIndexedDB(config) {
    return new Promise(function(resolve, reject) {
        openDB(config).then(function(db) {
            var tx = db.transaction(config.DB.store, 'readwrite');
            var store = tx.objectStore(config.DB.store);
            var req = store.clear();
            
            req.onsuccess = function() {
                resolve(true);
            };
            
            req.onerror = function() {
                reject(new Error('Failed to clear DB'));
            };
        }).catch(reject);
    });
}

/**
 * Save records to IndexedDB
 * Returns {saved: number, errors: number}
 */
function saveToIndexedDB(records, config) {
    return new Promise(function(resolve, reject) {
        openDB(config).then(function(db) {
            var tx = db.transaction(config.DB.store, 'readwrite');
            var store = tx.objectStore(config.DB.store);
            
            var saved = 0;
            var errors = 0;
            
            records.forEach(function(record) {
                // Ensure keyPath field exists
                if (!record[config.DB.keyPath]) {
                    errors++;
                    return;
                }
                
                try {
                    store.put(record);
                    saved++;
                } catch(e) {
                    errors++;
                }
            });
            
            tx.oncomplete = function() {
                resolve({ saved: saved, errors: errors });
            };
            
            tx.onerror = function() {
                reject(new Error('Transaction failed'));
            };
        }).catch(reject);
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// FIELD RESOLUTION (Backwards compatibility)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Resolve field value handling multiple aliases
 * Used by portfolio page to handle SYM/ticker, AVG/avg, etc.
 */
function resolveField(record, fieldName, aliases) {
    if (!record) return '—';
    
    var fieldUpper = fieldName.toUpperCase();
    var possibleFields = aliases[fieldUpper] || [fieldName, fieldUpper];
    
    for (var i = 0; i < possibleFields.length; i++) {
        var f = possibleFields[i];
        if (record[f] !== undefined && record[f] !== null) {
            return record[f];
        }
    }
    
    return '—';
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// LOGGING & DEBUG
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/**
 * Unified logging function
 */
function log(level, message) {
    var ts = new Date().toLocaleTimeString();
    var prefix = {
        'info': '✅',
        'warn': '⚠️',
        'error': '❌',
        'debug': '🔍'
    }[level] || '📢';
    
    console.log('[' + ts + '] ' + prefix + ' ' + message);
}

// Export for use in all files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        extractArray: extractArray,
        buildLookup: buildLookup,
        mergeRecords: mergeRecords,
        validateField: validateField,
        validateRecord: validateRecord,
        openDB: openDB,
        clearIndexedDB: clearIndexedDB,
        saveToIndexedDB: saveToIndexedDB,
        resolveField: resolveField,
        log: log
    };
}
