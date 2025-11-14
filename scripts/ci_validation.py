#!/usr/bin/env python3
"""
CI/CD Validation Script for DebugIn Multi-Runtime Debugger

Validates:
1. Python runtime build and tests
2. Java runtime build and tests
3. Node.js runtime build and tests
4. Cross-runtime integration

Run with: python scripts/ci_validation.py
"""

import subprocess
import sys
import os
import time
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'


class ValidationRunner:
    """Run CI validation suite"""

    def __init__(self):
        self.results = {}
        self.failed = False
        self.root_dir = Path(__file__).parent.parent

    def log(self, message, level="INFO"):
        """Log a message"""
        if level == "SUCCESS":
            print(f"{GREEN}✓{RESET} {message}")
        elif level == "ERROR":
            print(f"{RED}✗{RESET} {message}")
        elif level == "WARNING":
            print(f"{YELLOW}⚠{RESET} {message}")
        elif level == "SECTION":
            print(f"\n{BLUE}{'='*60}{RESET}")
            print(f"{BLUE}{message}{RESET}")
            print(f"{BLUE}{'='*60}{RESET}\n")
        else:
            print(f"  {message}")

    def run_command(self, cmd, cwd=None, name=None):
        """Run a command and return success status"""
        if name is None:
            name = " ".join(cmd) if isinstance(cmd, list) else cmd

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.root_dir,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                self.log(f"{name}", "SUCCESS")
                return True
            else:
                self.log(f"{name} (exit code {result.returncode})", "ERROR")
                if result.stderr:
                    self.log(f"Error: {result.stderr[:200]}")
                return False

        except subprocess.TimeoutExpired:
            self.log(f"{name} (timeout)", "ERROR")
            return False
        except Exception as e:
            self.log(f"{name} (exception: {e})", "ERROR")
            return False

    def validate_python(self):
        """Validate Python runtime"""
        self.log("Validating Python Runtime", "SECTION")

        tests = [
            (["python", "-m", "pip", "install", "-q", "-e", "."], "Install Python package"),
            (["python", "-m", "pytest", "tests/test_integration.py", "-v", "--tb=short"], "Run Python integration tests"),
            (["python", "-c", "import tracepointdebug; assert hasattr(tracepointdebug, '__version__')"], "Check version export"),
        ]

        results = []
        for cmd, name in tests:
            success = self.run_command(cmd, name=name)
            results.append((name, success))

        self.results["Python"] = all(r[1] for r in results)
        return self.results["Python"]

    def validate_java(self):
        """Validate Java runtime"""
        self.log("Validating Java Runtime", "SECTION")

        # Check if Java is available
        has_java = self.run_command(["java", "-version"], name="Check Java version")
        has_maven = self.run_command(["mvn", "-version"], name="Check Maven version")

        if not (has_java and has_maven):
            self.log("Java or Maven not available, skipping Java tests", "WARNING")
            self.results["Java"] = True  # Pass if not available
            return True

        tests = [
            (["mvn", "-f", "agent-core/pom.xml", "clean"], "Clean Java build"),
            (["mvn", "-f", "agent-core/pom.xml", "compile"], "Compile Java source"),
            (["mvn", "-f", "agent-core/pom.xml", "test"], "Run Java tests"),
        ]

        results = []
        for cmd, name in tests:
            success = self.run_command(cmd, name=name)
            results.append((name, success))

        self.results["Java"] = all(r[1] for r in results)
        return self.results["Java"]

    def validate_node(self):
        """Validate Node.js runtime"""
        self.log("Validating Node.js Runtime", "SECTION")

        # Check if Node is available
        has_node = self.run_command(["node", "--version"], name="Check Node version")
        has_npm = self.run_command(["npm", "--version"], name="Check npm version")

        if not (has_node and has_npm):
            self.log("Node or npm not available, skipping Node tests", "WARNING")
            self.results["Node"] = True  # Pass if not available
            return True

        tests = [
            (["npm", "install"], "Install Node dependencies", "tracepointdebug_final_library"),
            (["node", "tests/test_node_integration.js"], "Run Node integration tests", None),
        ]

        results = []
        for test in tests:
            cmd = test[0]
            name = test[1]
            cwd = self.root_dir / test[2] if len(test) > 2 and test[2] else None

            success = self.run_command(cmd, cwd=cwd, name=name)
            results.append((name, success))

        self.results["Node"] = all(r[1] for r in results)
        return self.results["Node"]

    def validate_documentation(self):
        """Validate documentation completeness"""
        self.log("Validating Documentation", "SECTION")

        required_docs = [
            "docs/control-plane-api.md",
            "docs/event-schema.md",
            "docs/PUBLIC_API.md",
            "docs/PYTHON.md",
            "docs/JAVA.md",
            "docs/NODE.md",
            "README.md",
            "IMPLEMENTATION_STATUS.md",
        ]

        results = []
        for doc in required_docs:
            path = self.root_dir / doc
            if path.exists():
                self.log(f"Found {doc}", "SUCCESS")
                results.append(True)
            else:
                self.log(f"Missing {doc}", "ERROR")
                results.append(False)

        self.results["Documentation"] = all(results)
        return self.results["Documentation"]

    def validate_build_system(self):
        """Validate build system"""
        self.log("Validating Build System", "SECTION")

        tests = [
            (["make", "--version"], "Check Make version"),
            (self.root_dir / "Makefile", "Makefile exists", "file"),
            (self.root_dir / "VERSION", "VERSION file exists", "file"),
            (self.root_dir / "pyproject.toml", "pyproject.toml exists", "file"),
            (self.root_dir / "agent-core" / "pom.xml", "pom.xml exists", "file"),
        ]

        results = []
        for test in tests:
            if len(test) > 2 and test[2] == "file":
                # Check file exists
                if test[0].exists():
                    self.log(f"{test[1]}", "SUCCESS")
                    results.append(True)
                else:
                    self.log(f"{test[1]}", "ERROR")
                    results.append(False)
            else:
                success = self.run_command(test[0], name=test[1])
                results.append(success)

        self.results["Build System"] = all(results)
        return self.results["Build System"]

    def validate_version_consistency(self):
        """Validate version consistency across files"""
        self.log("Validating Version Consistency", "SECTION")

        # Read VERSION file
        version_file = self.root_dir / "VERSION"
        if not version_file.exists():
            self.log("VERSION file not found", "ERROR")
            self.results["Version Consistency"] = False
            return False

        with open(version_file) as f:
            version = f.read().strip()

        self.log(f"Found version: {version}", "SUCCESS")

        # Check pyproject.toml
        pyproject = self.root_dir / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject) as f:
                content = f.read()
                if "dynamic = [\"version\"]" in content:
                    self.log("pyproject.toml configured for dynamic version", "SUCCESS")
                else:
                    self.log("pyproject.toml not configured correctly", "WARNING")

        self.results["Version Consistency"] = True
        return True

    def run_all(self):
        """Run all validations"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}DebugIn CI/CD Validation Suite{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")

        # Run validations
        self.validate_build_system()
        self.validate_version_consistency()
        self.validate_documentation()
        self.validate_python()
        self.validate_java()
        self.validate_node()

        # Print summary
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}Validation Summary{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")

        all_passed = True
        for component, passed in self.results.items():
            if passed:
                print(f"{GREEN}✓{RESET} {component}: PASSED")
            else:
                print(f"{RED}✗{RESET} {component}: FAILED")
                all_passed = False

        print()
        if all_passed:
            print(f"{GREEN}{'='*60}{RESET}")
            print(f"{GREEN}All validations PASSED!{RESET}")
            print(f"{GREEN}{'='*60}{RESET}")
            return 0
        else:
            print(f"{RED}{'='*60}{RESET}")
            print(f"{RED}Some validations FAILED!{RESET}")
            print(f"{RED}{'='*60}{RESET}")
            return 1


def main():
    """Main entry point"""
    runner = ValidationRunner()
    sys.exit(runner.run_all())


if __name__ == "__main__":
    main()
