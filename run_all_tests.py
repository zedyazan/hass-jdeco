#!/usr/bin/env python3
"""
Quick test runner for JDECo API
"""
import subprocess
import sys

print("="*80)
print("JDECo API Test Suite Runner")
print("="*80)

# Test 1: Dummy credentials
print("\n" + "="*80)
print("PHASE 1: Testing with DUMMY credentials (connectivity test)")
print("="*80)
result1 = subprocess.run([sys.executable, "test_api.py", "testuser", "testpass"], cwd=".")
print(f"\nPhase 1 Exit Code: {result1.returncode}")

# Test 2: Real credentials
print("\n\n" + "="*80)
print("PHASE 2: Testing with REAL credentials")
print("="*80)
result2 = subprocess.run([sys.executable, "test_api.py", "0598338919", "Zed338**"], cwd=".")
print(f"\nPhase 2 Exit Code: {result2.returncode}")

print("\n\n" + "="*80)
print("ALL TESTS COMPLETED")
print("="*80)
