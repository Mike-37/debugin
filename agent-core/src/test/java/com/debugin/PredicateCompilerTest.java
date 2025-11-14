package com.debugin;

import com.debugin.condition.ConditionEvaluator;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Comprehensive tests for PredicateCompiler and condition evaluation.
 */
@DisplayName("Predicate Compiler Tests")
public class PredicateCompilerTest {

    @Test
    @DisplayName("Should evaluate numeric equality")
    void testNumericEquality() {
        Map<String, Object> context = new HashMap<>();
        assertTrue(ConditionEvaluator.evaluate("5 == 5", context));
        assertFalse(ConditionEvaluator.evaluate("5 == 3", context));
    }

    @Test
    @DisplayName("Should evaluate numeric inequality")
    void testNumericInequality() {
        Map<String, Object> context = new HashMap<>();
        assertTrue(ConditionEvaluator.evaluate("5 != 3", context));
        assertFalse(ConditionEvaluator.evaluate("5 != 5", context));
    }

    @Test
    @DisplayName("Should evaluate less than")
    void testLessThan() {
        Map<String, Object> context = new HashMap<>();
        assertTrue(ConditionEvaluator.evaluate("3 < 5", context));
        assertFalse(ConditionEvaluator.evaluate("5 < 3", context));
        assertFalse(ConditionEvaluator.evaluate("5 < 5", context));
    }

    @Test
    @DisplayName("Should evaluate greater than")
    void testGreaterThan() {
        Map<String, Object> context = new HashMap<>();
        assertTrue(ConditionEvaluator.evaluate("5 > 3", context));
        assertFalse(ConditionEvaluator.evaluate("3 > 5", context));
        assertFalse(ConditionEvaluator.evaluate("5 > 5", context));
    }

    @Test
    @DisplayName("Should evaluate less than or equal")
    void testLessThanOrEqual() {
        Map<String, Object> context = new HashMap<>();
        assertTrue(ConditionEvaluator.evaluate("3 <= 5", context));
        assertTrue(ConditionEvaluator.evaluate("5 <= 5", context));
        assertFalse(ConditionEvaluator.evaluate("5 <= 3", context));
    }

    @Test
    @DisplayName("Should evaluate greater than or equal")
    void testGreaterThanOrEqual() {
        Map<String, Object> context = new HashMap<>();
        assertTrue(ConditionEvaluator.evaluate("5 >= 3", context));
        assertTrue(ConditionEvaluator.evaluate("5 >= 5", context));
        assertFalse(ConditionEvaluator.evaluate("3 >= 5", context));
    }

    @Test
    @DisplayName("Should evaluate logical AND")
    void testLogicalAnd() {
        Map<String, Object> context = new HashMap<>();
        assertTrue(ConditionEvaluator.evaluate("5 > 3 && 10 > 5", context));
        assertFalse(ConditionEvaluator.evaluate("5 > 3 && 10 < 5", context));
        assertFalse(ConditionEvaluator.evaluate("5 < 3 && 10 > 5", context));
    }

    @Test
    @DisplayName("Should evaluate logical OR")
    void testLogicalOr() {
        Map<String, Object> context = new HashMap<>();
        assertTrue(ConditionEvaluator.evaluate("5 > 3 || 10 < 5", context));
        assertTrue(ConditionEvaluator.evaluate("5 < 3 || 10 > 5", context));
        assertFalse(ConditionEvaluator.evaluate("5 < 3 || 10 < 5", context));
    }

    @Test
    @DisplayName("Should evaluate variable access")
    void testVariableAccess() {
        Map<String, Object> context = new HashMap<>();
        context.put("x", 10);
        context.put("y", 20);

        assertTrue(ConditionEvaluator.evaluate("x > 5", context));
        assertTrue(ConditionEvaluator.evaluate("y == 20", context));
        assertFalse(ConditionEvaluator.evaluate("x > y", context));
    }

    @Test
    @DisplayName("Should evaluate string equality")
    void testStringEquality() {
        Map<String, Object> context = new HashMap<>();
        context.put("status", "active");

        assertTrue(ConditionEvaluator.evaluate("status == 'active'", context));
        assertFalse(ConditionEvaluator.evaluate("status == 'inactive'", context));
    }

    @Test
    @DisplayName("Should evaluate null comparisons")
    void testNullComparisons() {
        Map<String, Object> context = new HashMap<>();
        context.put("value", null);

        assertTrue(ConditionEvaluator.evaluate("value == null", context));
        assertFalse(ConditionEvaluator.evaluate("value != null", context));
    }

    @Test
    @DisplayName("Should handle undefined variables safely")
    void testUndefinedVariables() {
        Map<String, Object> context = new HashMap<>();
        // Should return false, not throw exception
        assertFalse(ConditionEvaluator.evaluate("undefined > 5", context));
    }

    @Test
    @DisplayName("Should handle complex expressions")
    void testComplexExpressions() {
        Map<String, Object> context = new HashMap<>();
        context.put("count", 10);
        context.put("max", 100);

        assertTrue(ConditionEvaluator.evaluate("count > 5 && max < 200", context));
        assertTrue(ConditionEvaluator.evaluate("count > 5 || max > 200", context));
    }

    @Test
    @DisplayName("Should handle numeric type coercion")
    void testNumericTypeCoercion() {
        Map<String, Object> context = new HashMap<>();
        context.put("intValue", 42);
        context.put("doubleValue", 42.0);

        assertTrue(ConditionEvaluator.evaluate("intValue == doubleValue", context));
    }

    @Test
    @DisplayName("Should handle expressions with numbers")
    void testNumberLiterals() {
        Map<String, Object> context = new HashMap<>();

        assertTrue(ConditionEvaluator.evaluate("42 == 42", context));
        assertTrue(ConditionEvaluator.evaluate("3.14 > 3", context));
    }

    @Test
    @DisplayName("Should handle string literals")
    void testStringLiterals() {
        Map<String, Object> context = new HashMap<>();

        assertTrue(ConditionEvaluator.evaluate("'hello' == 'hello'", context));
        assertFalse(ConditionEvaluator.evaluate("'hello' == 'world'", context));
    }

    @Test
    @DisplayName("Should be safe from eval injection")
    void testEvalSafety() {
        Map<String, Object> context = new HashMap<>();
        // Should not execute arbitrary code
        assertFalse(ConditionEvaluator.evaluate("System.exit(1) == 1", context));
        assertFalse(ConditionEvaluator.evaluate("Runtime.getRuntime().exec('rm -rf /') == 1", context));
    }

    @Test
    @DisplayName("Should handle malformed expressions")
    void testMalformedExpressions() {
        Map<String, Object> context = new HashMap<>();

        // Should return false, not crash
        assertFalse(ConditionEvaluator.evaluate(">>>invalid>>>", context));
        assertFalse(ConditionEvaluator.evaluate("5 +++ 3", context));
    }

    @Test
    @DisplayName("Should evaluate boolean literals")
    void testBooleanLiterals() {
        Map<String, Object> context = new HashMap<>();

        assertTrue(ConditionEvaluator.evaluate("true", context));
        assertFalse(ConditionEvaluator.evaluate("false", context));
    }
}
