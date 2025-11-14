package com.debugin.condition;

import java.util.*;
import java.util.regex.Pattern;

/**
 * Safe condition expression evaluator for Java
 *
 * Evaluates simple conditions like:
 * - args[0] > 100
 * - this.userId == "admin"
 * - value != null
 * - enabled && status
 */
public class ConditionEvaluator {
    private static final Set<String> ALLOWED_KEYWORDS = new HashSet<>(Arrays.asList(
        "true", "false", "null", "this", "args", "locals",
        "String", "Integer", "Long", "Double", "Float", "Boolean"
    ));

    /**
     * Evaluate a condition expression
     *
     * @param condition Condition expression
     * @param context Evaluation context with args, this, locals
     * @return true if condition evaluates to true, false otherwise
     */
    public static boolean evaluate(String condition, Map<String, Object> context) {
        if (condition == null || condition.trim().isEmpty()) {
            return true; // No condition = always true
        }

        try {
            return evaluateExpression(condition, context);
        } catch (Exception e) {
            System.err.println("[DebugIn] Condition evaluation error: " + e.getMessage());
            return false;
        }
    }

    /**
     * Evaluate comparison expressions
     */
    private static boolean evaluateExpression(String expr, Map<String, Object> context) {
        expr = expr.trim();

        // Handle boolean literals
        if ("true".equals(expr)) return true;
        if ("false".equals(expr)) return false;

        // Handle logical operators
        if (expr.contains("&&")) {
            String[] parts = expr.split("&&");
            for (String part : parts) {
                if (!evaluateExpression(part, context)) {
                    return false;
                }
            }
            return true;
        }

        if (expr.contains("||")) {
            String[] parts = expr.split("\\|\\|");
            for (String part : parts) {
                if (evaluateExpression(part, context)) {
                    return true;
                }
            }
            return false;
        }

        // Handle comparisons
        return evaluateComparison(expr, context);
    }

    /**
     * Evaluate comparison expressions (==, !=, <, >, <=, >=)
     */
    private static boolean evaluateComparison(String expr, Map<String, Object> context) {
        // Try each comparison operator
        String[] operators = {"==", "!=", "<=", ">=", "<", ">"};

        for (String op : operators) {
            if (expr.contains(op)) {
                String[] parts = expr.split(Pattern.quote(op), 2);
                if (parts.length == 2) {
                    Object left = evaluateValue(parts[0].trim(), context);
                    Object right = evaluateValue(parts[1].trim(), context);

                    return compareValues(left, right, op);
                }
            }
        }

        // If no operator found, try to evaluate as a boolean value
        Object value = evaluateValue(expr, context);
        return value instanceof Boolean ? (Boolean) value : value != null;
    }

    /**
     * Evaluate a value expression (variable, literal, method call)
     */
    private static Object evaluateValue(String expr, Map<String, Object> context) {
        expr = expr.trim();

        // Boolean literals
        if ("true".equals(expr)) return true;
        if ("false".equals(expr)) return false;
        if ("null".equals(expr)) return null;

        // String literals
        if ((expr.startsWith("\"") && expr.endsWith("\"")) ||
            (expr.startsWith("'") && expr.endsWith("'"))) {
            return expr.substring(1, expr.length() - 1);
        }

        // Numeric literals
        try {
            if (expr.contains(".")) {
                return Double.parseDouble(expr);
            } else {
                return Long.parseLong(expr);
            }
        } catch (NumberFormatException e) {
            // Not a number
        }

        // Variable access: args[0], this.field, locals.var
        if (expr.startsWith("args[") && expr.endsWith("]")) {
            try {
                int index = Integer.parseInt(expr.substring(5, expr.length() - 1));
                Object argsObj = context.get("args");
                if (argsObj instanceof Object[]) {
                    Object[] args = (Object[]) argsObj;
                    if (index >= 0 && index < args.length) {
                        return args[index];
                    }
                }
            } catch (Exception e) {
                // Invalid index
            }
        }

        if (expr.startsWith("this.")) {
            Object thisObj = context.get("this");
            if (thisObj instanceof Map) {
                return ((Map<?, ?>) thisObj).get(expr.substring(5));
            }
        }

        if (expr.startsWith("locals.")) {
            Object localsObj = context.get("locals");
            if (localsObj instanceof Map) {
                return ((Map<?, ?>) localsObj).get(expr.substring(7));
            }
        }

        // Direct context lookup
        return context.get(expr);
    }

    /**
     * Compare two values using an operator
     */
    private static boolean compareValues(Object left, Object right, String op) {
        // Handle null cases
        if (left == null || right == null) {
            if ("==".equals(op)) {
                return left == right;
            } else if ("!=".equals(op)) {
                return left != right;
            }
            return false;
        }

        // Convert to comparable types
        try {
            double leftNum = getNumericValue(left);
            double rightNum = getNumericValue(right);

            switch (op) {
                case "==":
                    return leftNum == rightNum;
                case "!=":
                    return leftNum != rightNum;
                case "<":
                    return leftNum < rightNum;
                case ">":
                    return leftNum > rightNum;
                case "<=":
                    return leftNum <= rightNum;
                case ">=":
                    return leftNum >= rightNum;
                default:
                    return false;
            }
        } catch (Exception e) {
            // Fall back to string comparison
            String leftStr = String.valueOf(left);
            String rightStr = String.valueOf(right);

            if ("==".equals(op)) {
                return leftStr.equals(rightStr);
            } else if ("!=".equals(op)) {
                return !leftStr.equals(rightStr);
            }

            return false;
        }
    }

    /**
     * Convert object to numeric value
     */
    private static double getNumericValue(Object obj) {
        if (obj instanceof Number) {
            return ((Number) obj).doubleValue();
        }
        if (obj instanceof String) {
            return Double.parseDouble((String) obj);
        }
        if (obj instanceof Boolean) {
            return ((Boolean) obj) ? 1.0 : 0.0;
        }
        throw new NumberFormatException("Cannot convert to number: " + obj);
    }
}
