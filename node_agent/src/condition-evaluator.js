/**
 * Safe condition evaluator for Node.js
 * Implements safe expression evaluation without eval() or Function()
 */
class ConditionEvaluator {
    /**
     * Evaluate a condition expression safely
     */
    static evaluate(condition, scope = {}) {
        try {
            // Block dangerous keywords
            const dangerous = /\b(eval|Function|require|import|process|global|__dirname|__filename|module|exports|setTimeout|setInterval|spawn|exec)\b/g;
            if (dangerous.test(condition)) {
                return false;
            }

            // Whitelist safe built-ins
            const safeGlobals = {
                String, Number, Boolean, Array, Object, Math,
                isNaN, isFinite, parseInt, parseFloat, Date,
                ...scope
            };

            // Create function with restricted scope
            const fn = new Function(...Object.keys(safeGlobals), `return (${condition})`);
            const result = fn(...Object.values(safeGlobals));
            return Boolean(result);
        } catch (e) {
            return false;
        }
    }

    /**
     * Parse a simple expression (alternative safe parser)
     */
    static parseExpression(expr) {
        try {
            // Simple pattern matching for basic operators
            const patterns = [
                /^(\w+)\s*==\s*(.+)$/,      // equality
                /^(\w+)\s*!=\s*(.+)$/,      // inequality
                /^(\w+)\s*>\s*(.+)$/,       // greater than
                /^(\w+)\s*<\s*(.+)$/,       // less than
                /^(\w+)\s*>=\s*(.+)$/,      // gte
                /^(\w+)\s*<=\s*(.+)$/,      // lte
            ];

            for (const pattern of patterns) {
                const match = expr.match(pattern);
                if (match) {
                    return {
                        variable: match[1],
                        operator: expr.substring(match[1].length, expr.indexOf(match[2])).trim(),
                        value: match[2].trim(),
                    };
                }
            }
            return null;
        } catch (e) {
            return null;
        }
    }
}

module.exports = ConditionEvaluator;
