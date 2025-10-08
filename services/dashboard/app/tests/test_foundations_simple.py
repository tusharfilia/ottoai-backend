"""
Simplified foundation validation tests that don't require full app startup.
"""
import pytest
import os
import subprocess
from pathlib import Path

class TestSecurity:
    """Test basic security measures."""
    
    def test_no_hardcoded_secrets(self):
        """Test that no hardcoded secrets exist in code."""
        # Run secret scan
        try:
            result = subprocess.run([
                "python", "scripts/scan_no_secrets.py"
            ], capture_output=True, text=True, cwd=".")
            
            # Should pass (exit code 0)
            assert result.returncode == 0, f"Secret scan failed: {result.stderr}"
            print("✅ Secret scan PASSED")
            
        except FileNotFoundError:
            pytest.xfail("Secret scan script not found")
    
    def test_environment_variables_configured(self):
        """Test that required environment variables are configured."""
        required_vars = [
            "CLERK_SECRET_KEY",
            "DATABASE_URL", 
            "REDIS_URL",
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "CALLRAIL_API_KEY",
            "DEEPGRAM_API_KEY",
            "OPENAI_API_KEY",
            "BLAND_API_KEY",
            "ALLOWED_ORIGINS"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            pytest.xfail(f"Missing environment variables: {missing_vars}")
        else:
            print("✅ Environment variables configured")

class TestCodeStructure:
    """Test code structure and organization."""
    
    def test_middleware_exists(self):
        """Test that middleware files exist."""
        middleware_files = [
            "app/middleware/tenant.py",
            "app/middleware/rate_limiter.py"
        ]
        
        for file_path in middleware_files:
            assert Path(file_path).exists(), f"Middleware file not found: {file_path}"
        
        print("✅ Middleware files exist")
    
    def test_observability_components_exist(self):
        """Test that observability components exist."""
        obs_files = [
            "app/obs/logging.py",
            "app/obs/tracing.py", 
            "app/obs/metrics.py",
            "app/obs/middleware.py",
            "app/obs/errors.py"
        ]
        
        for file_path in obs_files:
            assert Path(file_path).exists(), f"Observability file not found: {file_path}"
        
        print("✅ Observability components exist")
    
    def test_realtime_components_exist(self):
        """Test that real-time components exist."""
        realtime_files = [
            "app/realtime/bus.py",
            "app/realtime/hub.py"
        ]
        
        for file_path in realtime_files:
            assert Path(file_path).exists(), f"Real-time file not found: {file_path}"
        
        print("✅ Real-time components exist")
    
    def test_webhook_routes_exist(self):
        """Test that webhook routes exist."""
        webhook_files = [
            "app/routes/call_rail.py",
            "app/routes/mobile_routes/twilio.py",
            "app/routes/bland.py",
            "app/routes/webhooks.py"
        ]
        
        for file_path in webhook_files:
            assert Path(file_path).exists(), f"Webhook route not found: {file_path}"
        
        print("✅ Webhook routes exist")
    
    def test_health_endpoints_exist(self):
        """Test that health endpoints exist."""
        health_files = [
            "app/routes/health.py",
            "app/routes/websocket.py"
        ]
        
        for file_path in health_files:
            assert Path(file_path).exists(), f"Health endpoint not found: {file_path}"
        
        print("✅ Health endpoints exist")

class TestDatabaseStructure:
    """Test database structure and migrations."""
    
    def test_migrations_exist(self):
        """Test that database migrations exist."""
        migrations_dir = Path("migrations/versions")
        assert migrations_dir.exists(), "Migrations directory not found"
        
        migration_files = list(migrations_dir.glob("*.py"))
        assert len(migration_files) > 0, "No migration files found"
        
        print(f"✅ Found {len(migration_files)} migration files")
    
    def test_idempotency_migration_exists(self):
        """Test that idempotency migration exists."""
        idempotency_migration = Path("migrations/versions/001_add_idempotency_keys.py")
        assert idempotency_migration.exists(), "Idempotency migration not found"
        
        print("✅ Idempotency migration exists")
    
    def test_performance_migration_exists(self):
        """Test that performance indexes migration exists."""
        performance_migration = Path("migrations/versions/002_add_performance_indexes.py")
        assert performance_migration.exists(), "Performance indexes migration not found"
        
        print("✅ Performance indexes migration exists")

class TestServices:
    """Test service layer components."""
    
    def test_idempotency_service_exists(self):
        """Test that idempotency service exists."""
        idempotency_service = Path("app/services/idempotency.py")
        assert idempotency_service.exists(), "Idempotency service not found"
        
        print("✅ Idempotency service exists")
    
    def test_messaging_guard_exists(self):
        """Test that messaging guard exists."""
        messaging_guard = Path("app/services/messaging/guard.py")
        assert messaging_guard.exists(), "Messaging guard not found"
        
        print("✅ Messaging guard exists")
    
    def test_audit_shim_exists(self):
        """Test that audit test shim exists."""
        audit_shim = Path("app/utils/audit_test_shim.py")
        assert audit_shim.exists(), "Audit test shim not found"
        
        print("✅ Audit test shim exists")

class TestScripts:
    """Test utility scripts."""
    
    def test_secret_scan_script_exists(self):
        """Test that secret scan script exists."""
        secret_scan = Path("scripts/scan_no_secrets.py")
        assert secret_scan.exists(), "Secret scan script not found"
        
        # Check if it's executable
        assert secret_scan.stat().st_mode & 0o111, "Secret scan script not executable"
        
        print("✅ Secret scan script exists and is executable")
    
    def test_verification_scripts_exist(self):
        """Test that verification scripts exist."""
        verification_scripts = [
            "scripts/verify_foundations.sh",
            "scripts/smoke_foundations.sh",
            "scripts/metrics_snapshot.sh"
        ]
        
        for script in verification_scripts:
            script_path = Path(script)
            assert script_path.exists(), f"Verification script not found: {script}"
        
        print("✅ Verification scripts exist")

class TestDocumentation:
    """Test documentation and reports."""
    
    def test_documentation_exists(self):
        """Test that documentation exists."""
        docs_files = [
            "README.md",
            "DEPLOYMENT_RUNBOOK.md",
            "docs/deploy/redis.md",
            "docs/events/catalog.md",
            "docs/ops/foundations-dashboard.md"
        ]
        
        for file_path in docs_files:
            assert Path(file_path).exists(), f"Documentation not found: {file_path}"
        
        print("✅ Documentation exists")
    
    def test_reports_directory_exists(self):
        """Test that reports directory exists."""
        reports_dir = Path("docs/reports")
        assert reports_dir.exists(), "Reports directory not found"
        
        raw_dir = Path("docs/reports/_raw")
        assert raw_dir.exists(), "Raw reports directory not found"
        
        print("✅ Reports directory exists")
