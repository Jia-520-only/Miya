# -*- coding: ascii -*-
"""
Miya AI End-to-End Test Scenarios
================================
"""

import asyncio
import json
import time
from pathlib import Path

# Test configuration
TEST_CONFIG = {
    "test_timeout": 60,
    "mock_external_services": True,
    "performance_benchmark": True,
}


class E2ETestRunner:
    """End-to-End Test Runner"""

    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
        self.performance_metrics = {}

    async def run_test(self, test_name: str, test_func, benchmark: bool = False):
        """Run a single test case"""
        start_time = time.time()

        try:
            print(f"[TEST] Running: {test_name}")
            await asyncio.wait_for(test_func(), timeout=TEST_CONFIG["test_timeout"])

            elapsed = time.time() - start_time
            self.passed += 1

            result = {"name": test_name, "status": "PASS", "duration": elapsed}

            if benchmark:
                self.performance_metrics[test_name] = elapsed

            self.test_results.append(result)
            print(f"[PASS] {test_name} - passed ({elapsed:.2f}s)\n")

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            self.failed += 1
            self.test_results.append({"name": test_name, "status": "TIMEOUT", "duration": elapsed})
            print(f"[TIMEOUT] {test_name} - timeout ({elapsed:.2f}s)\n")

        except Exception as e:
            elapsed = time.time() - start_time
            self.failed += 1
            self.test_results.append({"name": test_name, "status": f"FAIL: {str(e)}", "duration": elapsed})
            print(f"[FAIL] {test_name} - failed: {str(e)} ({elapsed:.2f}s)\n")

    def print_summary(self):
        """Print test summary"""
        total = self.passed + self.failed
        print("=" * 70)
        print(f"[SUMMARY] E2E Tests: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"[WARN] {self.failed} tests failed")
        print("=" * 70)

        if self.performance_metrics:
            print("\n[PERFORMANCE] Metrics:")
            for test_name, duration in sorted(self.performance_metrics.items()):
                print(f"  {test_name}: {duration:.3f}s")

        print("\n[RESULTS] Details:")
        for result in self.test_results:
            print(f"  {result['name']}: {result['status']} ({result['duration']:.3f}s)")


# ==================== Performance Tests ====================


async def test_config_cache_basic():
    """Test config cache basic functionality"""
    import tempfile

    from core.config_cache import ConfigCacheLayer

    cache = ConfigCacheLayer(max_size=100, default_ttl=60.0)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as f:
        json.dump({"emotion": "happy", "confidence": 0.8}, f)
        config_path = Path(f.name)

    try:
        await cache.load_config(config_path)
        stats = cache.get_stats()
        assert stats["loads"] >= 1, "Should have loaded config from file"
    finally:
        config_path.unlink(missing_ok=True)

    print("  [OK] Config cache basic functionality")


async def test_config_cache_performance():
    """Test config cache performance"""
    import tempfile

    from core.config_cache import ConfigCacheLayer

    cache = ConfigCacheLayer(max_size=1000, default_ttl=300.0)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as f:
        json.dump({"value": time.time()}, f)
        config_path = Path(f.name)

    try:
        await cache.load_config(config_path)

        read_start = time.time()
        for i in range(1000):
            await cache.load_config(config_path)
        read_duration = time.time() - read_start

        assert read_duration < 0.1, f"Read performance too slow: {read_duration:.3f}s"

    finally:
        config_path.unlink(missing_ok=True)

    print(f"  [OK] Config cache performance (1000 reads: {read_duration:.4f}s)")


async def test_event_batcher_basic():
    """Test event batcher basic functionality"""
    from core.event_batcher import BatchConfig, EventBatcher

    batcher = EventBatcher(BatchConfig(max_batch_size=10, max_batch_delay=1.0, min_batch_size=3))

    events_received = []

    async def subscriber(event):
        events_received.append(event)

    batcher.subscribe("test_event", subscriber)

    for i in range(5):
        await batcher.publish_event("test_event", {"data": f"Event {i}"})

    await asyncio.sleep(2)

    assert len(events_received) > 0, "Should receive batched events"

    await batcher.shutdown()

    print("  [OK] Event batcher basic functionality")


async def test_event_batcher_performance():
    """Test event batcher performance"""
    from core.event_batcher import BatchConfig, EventBatcher

    batcher = EventBatcher(BatchConfig(max_batch_size=100, max_batch_delay=0.5, min_batch_size=10))

    async def subscriber(event):
        pass

    for i in range(10):
        batcher.subscribe("test_event", subscriber)

    start = time.time()
    for i in range(1000):
        await batcher.publish_event("test_event", {"data": f"Event {i}"})
    publish_duration = time.time() - start

    await asyncio.sleep(2)

    assert publish_duration < 2.0, f"Publish performance too slow: {publish_duration:.3f}s"

    await batcher.shutdown()

    print(f"  [OK] Event batcher performance (1000 events: {publish_duration:.4f}s)")


async def test_db_connection_pool_basic():
    """Test database connection pool basic functionality"""
    import tempfile

    from core.db_connection_pool import PoolConfig, SQLiteConnectionPool

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name

    try:
        pool = SQLiteConnectionPool(db_path, PoolConfig(min_connections=2, max_connections=5))

        await pool.initialize()

        conn = await pool.get_connection()
        assert conn is not None, "Should get connection"

        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result is not None, "Query should return result"

        await pool.return_connection(conn)

        stats = pool.get_stats()
        assert stats["total_connections"] >= 2, "Should have at least 2 connections"

        await pool.shutdown()

    finally:
        Path(db_path).unlink(missing_ok=True)

    print("  [OK] Database connection pool basic functionality")


# ==================== Security Tests ====================


async def test_config_encryption_basic():
    """Test config encryption basic functionality"""
    import tempfile

    from core.config_encryption import ConfigEncryption

    with tempfile.NamedTemporaryFile(delete=False) as f:
        key_file = Path(f.name)

    try:
        encryption = ConfigEncryption(key_file=key_file)

        original = "my_secret_password_123"
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original, "Decrypted value should match original"

        config = {"username": "admin", "password": "secret123", "api_key": "abc123def456"}

        encrypted_config = encryption.encrypt_config(config)
        assert "password" not in str(encrypted_config), "Password should be encrypted"

        decrypted_config = encryption.decrypt_config(encrypted_config)
        assert decrypted_config["password"] == config["password"], "Decrypted password should be correct"

    finally:
        key_file.unlink(missing_ok=True)

    print("  [OK] Config encryption basic functionality")


async def test_access_control_basic():
    """Test access control basic functionality"""
    import tempfile

    from core.access_control import APIKeyManager, Permission, Role

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
        storage_path = f.name

    try:
        manager = APIKeyManager(storage_path)

        key_id, secret_key = manager.generate_key(name="Test Key", role=Role.USER, expires_in_days=30)

        api_key = manager.validate_key(secret_key)
        assert api_key is not None, "Key validation should succeed"
        assert api_key.name == "Test Key", "Key name should match"

        has_read = manager.has_permission(api_key, Permission.CONFIG_READ)
        assert has_read, "User should have read config permission"

        revoked = manager.revoke_key(key_id)
        assert revoked, "Key revocation should succeed"

        api_key = manager.validate_key(secret_key)
        assert api_key is None, "Revoked key should not validate"

    finally:
        Path(storage_path).unlink(missing_ok=True)

    print("  [OK] Access control basic functionality")


async def test_audit_logger_basic():
    """Test audit logger basic functionality"""
    import tempfile

    from core.audit_logger import AuditEventLevel, AuditEventType, AuditLogger

    with tempfile.TemporaryDirectory() as log_dir:
        logger = AuditLogger(log_dir=log_dir)

        logger.log_event(
            event_type=AuditEventType.SYSTEM_STARTUP, level=AuditEventLevel.INFO, message="System startup test"
        )

        logger.log_event(
            event_type=AuditEventType.API_KEY_CREATE,
            level=AuditEventLevel.INFO,
            user_id="test_user",
            message="Create API key test",
        )

        logger.log_event(
            event_type=AuditEventType.IOT_COMMAND_SEND,
            level=AuditEventLevel.WARNING,
            user_id="test_user",
            message="Send IoT command test",
        )

        events = logger.query_events(limit=10)
        assert len(events) >= 3, "Should have at least 3 events"

        stats = logger.get_stats()
        assert stats["total_events"] >= 3, "Stats should show at least 3 events"

    print("  [OK] Audit logger basic functionality")


# ==================== Monitoring Tests ====================


async def test_monitoring_basic():
    """Test monitoring system basic functionality"""
    from core.monitoring import MonitoringSystem

    monitoring = MonitoringSystem(check_interval=5.0)

    monitoring.collector.record("test.metric", 75.0)

    from core.monitoring import AlertRule, AlertSeverity

    monitoring.alert_engine.add_rule(
        AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            metric_name="test.metric",
            condition="gt",
            threshold=70.0,
            severity=AlertSeverity.WARNING,
            duration=1.0,
        )
    )

    monitoring.alert_engine.check_rules()

    active_alerts = monitoring.alert_engine.get_active_alerts()
    assert len(active_alerts) > 0, "Should have active alerts"

    dashboard = monitoring.get_dashboard_data()
    assert "metrics" in dashboard, "Dashboard should include metrics"
    assert "alerts" in dashboard, "Dashboard should include alerts"

    print("  [OK] Monitoring system basic functionality")


async def test_alert_notification():
    """Test alert notification"""
    from core.monitoring import AlertRule, AlertSeverity, MonitoringSystem

    monitoring = MonitoringSystem(check_interval=5.0)

    monitoring.notification_service.add_webhook("http://localhost:8080/mock_webhook")

    monitoring.collector.record("test.metric", 90.0)

    monitoring.alert_engine.add_rule(
        AlertRule(
            rule_id="test_alert",
            name="Test Alert",
            metric_name="test.metric",
            condition="gt",
            threshold=80.0,
            severity=AlertSeverity.ERROR,
            duration=1.0,
        )
    )

    monitoring.alert_engine.check_rules()
    await asyncio.sleep(0.5)

    print("  [OK] Alert notification")


# ==================== Integration Tests ====================


async def test_config_hot_reload_with_cache():
    """Test config hot reload with cache integration"""
    import tempfile

    from core.config_cache import ConfigCacheLayer
    from core.config_encryption import ConfigEncryption

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as f:
        json.dump({"happy": 0.8, "sad": 0.1}, f)
        config_path = Path(f.name)

    with tempfile.NamedTemporaryFile(delete=False) as key_f:
        key_file = Path(key_f.name)

    try:
        cache = ConfigCacheLayer(max_size=100)
        ConfigEncryption(key_file=key_file)

        config1 = await cache.load_config(config_path)
        assert config1 is not None, "Should load config"
        assert config1.get("happy") == 0.8, "Config should contain happy key"

        config2 = await cache.load_config(config_path)
        assert config2 is not None, "Should get from cache"
        assert config2.get("sad") == 0.1, "Config should contain sad key"

        stats = cache.get_stats()
        assert stats["hits"] >= 1, "Should have cache hits"

    finally:
        config_path.unlink(missing_ok=True)
        key_file.unlink(missing_ok=True)

    print("  [OK] Config hot reload with cache integration")


async def test_api_security_flow():
    """Test API security flow"""
    import tempfile

    from core.access_control import APIKeyManager, Permission, Role
    from core.audit_logger import AuditEventType, AuditLogger

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
        storage_path = f.name

    with tempfile.TemporaryDirectory() as log_dir:
        try:
            key_manager = APIKeyManager(storage_path)
            audit_logger = AuditLogger(log_dir=log_dir)

            key_id, secret_key = key_manager.generate_key(name="Security Test Key", role=Role.USER)

            audit_logger.log_event(
                event_type=AuditEventType.API_KEY_CREATE,
                user_id="test_user",
                api_key_id=key_id,
                message="API key creation",
            )

            api_key = key_manager.validate_key(secret_key)
            assert api_key is not None, "API key validation should succeed"

            has_permission = key_manager.has_permission(api_key, Permission.CONFIG_READ)
            assert has_permission, "Should have read config permission"

            key_manager.log_access(
                key_id=key_id, endpoint="/api/config", method="GET", status_code=200, response_time_ms=50.5
            )

            events = audit_logger.query_events(event_type=AuditEventType.API_KEY_CREATE, limit=10)
            assert len(events) > 0, "Should have audit events"

            key_stats = key_manager.get_stats()
            audit_stats = audit_logger.get_stats()

            assert key_stats["total_keys"] >= 1, "Should have API keys"
            assert audit_stats["total_events"] >= 1, "Should have audit events"

        finally:
            Path(storage_path).unlink(missing_ok=True)

    print("  [OK] API security flow")


async def test_performance_benchmark():
    """Performance benchmark test"""
    import tempfile

    from core.config_cache import ConfigCacheLayer
    from core.event_batcher import BatchConfig, EventBatcher

    results = {}

    cache = ConfigCacheLayer(max_size=1000)

    temp_files = []
    for i in range(100):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
        json.dump({"key": f"value_{i}", "index": i}, f)
        f.close()
        temp_files.append(Path(f.name))

    try:
        start = time.time()
        for i in range(100):
            await cache.load_config(temp_files[i])
        load_duration = time.time() - start
        results["cache_load_100"] = load_duration

        start = time.time()
        for i in range(10000):
            await cache.load_config(temp_files[i % 100])
        read_duration = time.time() - start
        results["cache_read_10000"] = read_duration
    finally:
        for fp in temp_files:
            fp.unlink(missing_ok=True)

    batcher = EventBatcher(BatchConfig(max_batch_size=100, max_batch_delay=0.1, min_batch_size=10))

    async def subscriber(event):
        pass

    for _ in range(5):
        batcher.subscribe("test", subscriber)

    start = time.time()
    for i in range(1000):
        await batcher.publish_event("test", {"data": i})
    publish_duration = time.time() - start
    results["event_publish_1000"] = publish_duration

    await asyncio.sleep(1)
    await batcher.shutdown()

    assert results["cache_load_100"] < 1.0, "Cache load too slow"
    assert results["cache_read_10000"] < 0.5, "Cache read too slow"
    assert results["event_publish_1000"] < 2.0, "Event publish too slow"

    print("  [OK] Performance benchmark:")
    print(f"    - Cache load 100: {results['cache_load_100']:.4f}s")
    print(f"    - Cache read 10000: {results['cache_read_10000']:.4f}s")
    print(f"    - Event publish 1000: {results['event_publish_1000']:.4f}s")


# ==================== Main Test Flow ====================


async def run_all_e2e_tests():
    """Run all end-to-end tests"""
    print("\n" + "=" * 70)
    print("[START] Miya AI End-to-End Test Suite")
    print("=" * 70 + "\n")

    runner = E2ETestRunner()

    print("[MODULE 1] Performance Optimization")
    print("-" * 70)
    await runner.run_test("Config cache basic", test_config_cache_basic)
    await runner.run_test("Config cache performance", test_config_cache_performance, benchmark=True)
    await runner.run_test("Event batcher basic", test_event_batcher_basic)
    await runner.run_test("Event batcher performance", test_event_batcher_performance, benchmark=True)
    await runner.run_test("DB connection pool basic", test_db_connection_pool_basic)

    print("\n[MODULE 2] Security Measures")
    print("-" * 70)
    await runner.run_test("Config encryption basic", test_config_encryption_basic)
    await runner.run_test("Access control basic", test_access_control_basic)
    await runner.run_test("Audit logger basic", test_audit_logger_basic)

    print("\n[MODULE 3] Monitoring and Alerts")
    print("-" * 70)
    await runner.run_test("Monitoring system basic", test_monitoring_basic)
    await runner.run_test("Alert notification", test_alert_notification)

    print("\n[MODULE 4] System Integration")
    print("-" * 70)
    await runner.run_test("Config hot reload with cache", test_config_hot_reload_with_cache)
    await runner.run_test("API security flow", test_api_security_flow)

    print("\n[MODULE 5] Performance Benchmark")
    print("-" * 70)
    await runner.run_test("Performance benchmark", test_performance_benchmark, benchmark=True)

    runner.print_summary()

    return {
        "total": runner.passed + runner.failed,
        "passed": runner.passed,
        "failed": runner.failed,
        "results": runner.test_results,
        "performance_metrics": runner.performance_metrics,
    }


if __name__ == "__main__":
    result = asyncio.run(run_all_e2e_tests())

    result_file = Path(__file__).parent.parent / "test_results" / "e2e_test_results.json"
    result_file.parent.mkdir(exist_ok=True)
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n[FILE] E2E test results saved to: {result_file}")

    import sys

    sys.exit(0 if result["failed"] == 0 else 1)
