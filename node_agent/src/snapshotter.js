/**
 * Snapshotter for Node.js - captures function arguments and local state
 */
class Snapshotter {
    constructor(config = {}) {
        this.config = {
            params: config.params !== false,
            fields: config.fields || [],
            locals: config.locals !== false,
            maxDepth: config.maxDepth || 5,
            maxProps: config.maxProps || 50,
        };
        this.visitedObjects = new Set();
    }

    /**
     * Capture snapshot of arguments and context
     */
    captureSnapshot(thisObj, args, locals = {}) {
        this.visitedObjects.clear();
        const snapshot = {};

        if (this.config.params && args) {
            for (let i = 0; i < args.length; i++) {
                snapshot[`arg${i}`] = this.safeSerialize(args[i], 0);
            }
        }

        if (thisObj && this.config.locals) {
            snapshot.this = this.safeSerialize(thisObj, 0);
        }

        if (locals && this.config.locals) {
            for (const [key, value] of Object.entries(locals)) {
                snapshot[key] = this.safeSerialize(value, 0);
            }
        }

        return snapshot;
    }

    /**
     * Safely serialize a value with depth and property limits
     */
    safeSerialize(obj, depth) {
        if (obj === null || obj === undefined) {
            return null;
        }

        if (depth >= this.config.maxDepth) {
            return '[depth limit reached]';
        }

        // Primitives and strings
        if (typeof obj === 'string' || typeof obj === 'number' ||
            typeof obj === 'boolean' || typeof obj === 'symbol') {
            return String(obj);
        }

        // Handle cycles
        const objId = this._getObjectId(obj);
        if (this.visitedObjects.has(objId)) {
            return '[cyclic reference]';
        }
        this.visitedObjects.add(objId);

        try {
            if (Array.isArray(obj)) {
                return this._serializeArray(obj, depth);
            } else if (obj instanceof Date) {
                return obj.toISOString();
            } else if (obj instanceof RegExp) {
                return obj.toString();
            } else if (obj instanceof Error) {
                return { message: obj.message, stack: obj.stack };
            } else if (typeof obj === 'object') {
                return this._serializeObject(obj, depth);
            }
            return String(obj);
        } finally {
            this.visitedObjects.delete(objId);
        }
    }

    _serializeArray(arr, depth) {
        const result = [];
        let count = 0;
        for (const item of arr) {
            if (count >= this.config.maxProps) {
                result.push({ __truncated__: true });
                break;
            }
            result.push(this.safeSerialize(item, depth + 1));
            count++;
        }
        return result;
    }

    _serializeObject(obj, depth) {
        const result = { __class__: obj.constructor.name };
        let count = 0;

        for (const [key, value] of Object.entries(obj)) {
            if (count >= this.config.maxProps) {
                result.__truncated__ = true;
                break;
            }
            if (!this.config.fields || this.config.fields.length === 0 ||
                this.config.fields.includes(key)) {
                result[key] = this.safeSerialize(value, depth + 1);
                count++;
            }
        }

        return result;
    }

    _getObjectId(obj) {
        // Use JSON serialization as a simple way to detect cycles
        // In production, would use WeakMap
        if (!obj.__debugin_id__) {
            obj.__debugin_id__ = Math.random().toString(36);
        }
        return obj.__debugin_id__;
    }
}

module.exports = Snapshotter;
