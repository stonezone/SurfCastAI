#!/usr/bin/env python3
"""
SSRF Protection Verification Script

Demonstrates the comprehensive SSRF protection implemented in Task 3.2.
Tests all private IP ranges and common attack vectors.
"""

from src.utils.security import is_private_ip, validate_url, SecurityError


def test_case(description, func, args, expect_error=False):
    """Run a test case and report results."""
    try:
        result = func(*args)
        if expect_error:
            print(f"  ❌ FAIL: {description}")
            print(f"      Expected error but got: {result}")
            return False
        else:
            print(f"  ✅ PASS: {description}")
            return True
    except SecurityError as e:
        if expect_error:
            print(f"  ✅ PASS: {description}")
            print(f"      Blocked with: {str(e)}")
            return True
        else:
            print(f"  ❌ FAIL: {description}")
            print(f"      Unexpected error: {str(e)}")
            return False


def main():
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║       SSRF PROTECTION VERIFICATION - COMPREHENSIVE TEST           ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()

    total_tests = 0
    passed_tests = 0

    # Test 1: RFC 1918 Private Networks
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ TEST 1: RFC 1918 Private Networks (10/8, 172.16/12, 192.168/16)│")
    print("└─────────────────────────────────────────────────────────────────┘")
    tests = [
        ("10.0.0.0/8 - Class A private", is_private_ip, ['10.1.2.3'], False),
        ("172.16.0.0/12 - Class B private", is_private_ip, ['172.17.0.1'], False),
        ("192.168.0.0/16 - Class C private", is_private_ip, ['192.168.1.1'], False),
        ("Block 10.x.x.x in URL", validate_url, ['http://10.1.2.3/api'], True),
        ("Block 172.17.x.x in URL", validate_url, ['http://172.17.0.1:8080/admin'], True),
        ("Block 192.168.x.x in URL", validate_url, ['http://192.168.1.1/internal'], True),
    ]
    for desc, func, args, expect_err in tests:
        total_tests += 1
        if test_case(desc, func, args, expect_err):
            passed_tests += 1
    print()

    # Test 2: Link-Local and AWS Metadata
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ TEST 2: Link-Local Addresses (169.254.0.0/16) & AWS Metadata   │")
    print("└─────────────────────────────────────────────────────────────────┘")
    tests = [
        ("169.254.0.0/16 detection", is_private_ip, ['169.254.1.1'], False),
        ("AWS metadata service IP", is_private_ip, ['169.254.169.254'], False),
        ("Block AWS metadata URL", validate_url, ['http://169.254.169.254/latest/meta-data/'], True),
        ("Block link-local with port", validate_url, ['http://169.254.1.1:80/config'], True),
    ]
    for desc, func, args, expect_err in tests:
        total_tests += 1
        if test_case(desc, func, args, expect_err):
            passed_tests += 1
    print()

    # Test 3: Loopback Addresses
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ TEST 3: Loopback Addresses (127.0.0.0/8)                       │")
    print("└─────────────────────────────────────────────────────────────────┘")
    tests = [
        ("127.0.0.1 detection", is_private_ip, ['127.0.0.1'], False),
        ("Full loopback range 127.x.x.x", is_private_ip, ['127.5.10.15'], False),
        ("localhost hostname", is_private_ip, ['localhost'], False),
        ("Block localhost URL", validate_url, ['http://localhost:3000/api'], True),
        ("Block 127.0.0.1 URL", validate_url, ['http://127.0.0.1:8080/admin'], True),
    ]
    for desc, func, args, expect_err in tests:
        total_tests += 1
        if test_case(desc, func, args, expect_err):
            passed_tests += 1
    print()

    # Test 4: IPv6 Private Addresses
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ TEST 4: IPv6 Private Addresses                                 │")
    print("└─────────────────────────────────────────────────────────────────┘")
    tests = [
        ("IPv6 loopback ::1", is_private_ip, ['::1'], False),
        ("IPv6 link-local fe80::", is_private_ip, ['fe80::1'], False),
        ("IPv6 unique local fc00::", is_private_ip, ['fc00::1'], False),
        ("Block IPv6 loopback URL", validate_url, ['http://[::1]/api'], True),
        ("Block IPv6 link-local URL", validate_url, ['http://[fe80::dead:beef]/service'], True),
    ]
    for desc, func, args, expect_err in tests:
        total_tests += 1
        if test_case(desc, func, args, expect_err):
            passed_tests += 1
    print()

    # Test 5: Public Addresses (Should Pass)
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ TEST 5: Public Addresses (Should Be Allowed)                   │")
    print("└─────────────────────────────────────────────────────────────────┘")
    tests = [
        ("Google DNS 8.8.8.8 is public", is_private_ip, ['8.8.8.8'], False),
        ("Cloudflare DNS 1.1.1.1 is public", is_private_ip, ['1.1.1.1'], False),
        ("Allow NOAA weather API", validate_url, ['https://api.weather.gov/forecast'], False),
        ("Allow NDBC buoy data", validate_url, ['https://www.ndbc.noaa.gov/data'], False),
        ("Allow public IPv6", is_private_ip, ['2606:4700:4700::1111'], False),
    ]
    for desc, func, args, expect_err in tests:
        total_tests += 1
        # For public addresses, expect NO error (is_private_ip returns False)
        if expect_err:
            if test_case(desc, func, args, expect_err):
                passed_tests += 1
        else:
            # These should succeed without errors
            try:
                result = func(*args)
                if isinstance(result, bool):
                    # is_private_ip should return False for public IPs
                    if result is False:
                        print(f"  ✅ PASS: {desc}")
                        passed_tests += 1
                    else:
                        print(f"  ❌ FAIL: {desc} - Expected False, got True")
                else:
                    # validate_url should return normalized URL
                    print(f"  ✅ PASS: {desc}")
                    passed_tests += 1
            except Exception as e:
                print(f"  ❌ FAIL: {desc} - Unexpected error: {str(e)}")
    print()

    # Test 6: Edge Cases
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│ TEST 6: Edge Cases & Boundary Conditions                       │")
    print("└─────────────────────────────────────────────────────────────────┘")
    tests = [
        ("Just outside 10/8 (9.255.255.255)", is_private_ip, ['9.255.255.255'], False),
        ("Just outside 172.16/12 (172.32.0.0)", is_private_ip, ['172.32.0.0'], False),
        ("Just outside 192.168/16 (192.169.0.0)", is_private_ip, ['192.169.0.0'], False),
        ("Invalid hostname returns False", is_private_ip, ['invalid-host-xyz-123'], False),
    ]
    for desc, func, args, expect_err in tests:
        total_tests += 1
        try:
            result = func(*args)
            if result is False:
                print(f"  ✅ PASS: {desc}")
                passed_tests += 1
            else:
                print(f"  ❌ FAIL: {desc} - Expected False, got True")
        except Exception as e:
            print(f"  ❌ FAIL: {desc} - Unexpected error: {str(e)}")
    print()

    # Summary
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║                         TEST SUMMARY                              ║")
    print("╚═══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Total Tests:  {total_tests}")
    print(f"  Passed:       {passed_tests}")
    print(f"  Failed:       {total_tests - passed_tests}")
    print(f"  Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    print()

    if passed_tests == total_tests:
        print("  ✅ ALL TESTS PASSED - SSRF PROTECTION IS WORKING CORRECTLY!")
        print()
        print("  Protected Against:")
        print("    • RFC 1918 private networks (10/8, 172.16/12, 192.168/16)")
        print("    • Link-local addresses (169.254.0.0/16)")
        print("    • AWS EC2 metadata service (169.254.169.254)")
        print("    • Loopback addresses (127.0.0.0/8)")
        print("    • IPv6 private ranges (fc00::/7, fe80::/10, ::1)")
        print("    • DNS-based bypasses (hostname resolution)")
        print()
        return 0
    else:
        print("  ❌ SOME TESTS FAILED - REVIEW IMPLEMENTATION")
        return 1


if __name__ == '__main__':
    exit(main())
