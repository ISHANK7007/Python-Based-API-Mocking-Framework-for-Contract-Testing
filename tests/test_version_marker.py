import os
import pytest
import subprocess
import time
import tempfile
import requests
import yaml
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, Optional, Generator, Tuple

# ----- Contract Version Management -----

class ContractVersion:
    """Represents a specific version of an API contract."""
    
    def __init__(self, name: str, version: str, contract_path: Optional[Path] = None):
        self.name = name
        self.version = version
        self.contract_path = contract_path
        
    @classmethod
    def parse(cls, version_str: str, contracts_dir: Path) -> 'ContractVersion':
        """Parse a version string like 'users-v1.2.3' and locate the contract file."""
        if "-v" not in version_str:
            raise ValueError(f"Invalid contract version format: {version_str}. Expected format: name-vX.Y.Z")
            
        name, version = version_str.split("-v", 1)
        
        # Look for the contract file
        contract_path = contracts_dir / f"{name}-v{version}.yaml"
        if not contract_path.exists():
            raise FileNotFoundError(f"Contract file not found: {contract_path}")
            
        return cls(name, version, contract_path)
    
    def __str__(self) -> str:
        return f"{self.name}-v{self.version}"


# ----- Mock Server Management -----

class MockServerManager:
    """Manages the lifecycle of a mock API server with a specific contract."""
    
    def __init__(self, 
                 contract_version: ContractVersion,
                 base_port: int = 8000,
                 server_cmd: str = "mock-server"):
        self.contract_version = contract_version
        self.base_port = base_port
        self.server_cmd = server_cmd
        self.process = None
        self.port = None
        self.temp_dir = None
        
    def start(self) -> int:
        """Start the mock server with the specified contract and return the port."""
        # Create a temporary directory for server artifacts
        self.temp_dir = tempfile.mkdtemp(prefix=f"mockserver_{self.contract_version.name}_")
        
        # Determine an available port
        self.port = self._find_available_port()
        
        # Build command to start the server
        cmd = [
            self.server_cmd,
            "serve",
            "--contract", str(self.contract_version.contract_path),
            "--port", str(self.port),
            "--log-dir", self.temp_dir
        ]
        
        # Start server process
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to be ready
        self._wait_for_server()
        
        return self.port
    
    def stop(self) -> None:
        """Stop the mock server and clean up resources."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            
        # Clean up temporary directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None
    
    def _find_available_port(self) -> int:
        """Find an available port to use for the mock server."""
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0))
        port = s.getsockname()[1]
        s.close()
        return port
        
    def _wait_for_server(self, timeout: int = 10, interval: float = 0.1) -> None:
        """Wait for the server to be ready to accept connections."""
        if not self.port:
            raise RuntimeError("Server port not set")
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://localhost:{self.port}/health")
                if response.status_code == 200:
                    return
            except requests.RequestException:
                pass
            
            # Check if process has exited
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                raise RuntimeError(
                    f"Mock server failed to start.\nStdout: {stdout}\nStderr: {stderr}"
                )
                
            time.sleep(interval)
            
        raise TimeoutError(f"Mock server did not become ready within {timeout} seconds")


# ----- Pytest Fixtures -----

@pytest.fixture(scope="session")
def contracts_dir(request) -> Path:
    """Return the directory containing contract definition files."""
    # Default to 'contracts' directory in project root
    contracts_path = Path(request.config.rootdir) / "contracts"
    
    # Allow override via pytest option
    if request.config.getoption("--contracts-dir", None):
        contracts_path = Path(request.config.getoption("--contracts-dir"))
        
    if not contracts_path.exists():
        pytest.fail(f"Contracts directory not found: {contracts_path}")
        
    return contracts_path

@pytest.fixture
def contract_version(request, contracts_dir) -> ContractVersion:
    """
    Get contract version based on test node markers.
    
    Usage: 
        @pytest.mark.contract_version("users-v1.2.3")
        def test_something(contract_version):
            ...
    """
    marker = request.node.get_closest_marker("contract_version")
    if not marker:
        pytest.fail("No contract_version marker specified for the test")
        
    version_str = marker.args[0]
    return ContractVersion.parse(version_str, contracts_dir)

@pytest.fixture
def mock_server(contract_version) -> Generator[Tuple[str, int], None, None]:
    """
    Start a mock server with the specified contract version and yield the base URL.
    Server will be automatically torn down after test.
    
    Returns a tuple of (base_url, port)
    """
    server_manager = MockServerManager(contract_version)
    try:
        port = server_manager.start()
        yield (f"http://localhost:{port}", port)
    finally:
        server_manager.stop()

@pytest.fixture
def api_client(mock_server) -> requests.Session:
    """
    Create a configured HTTP client for interacting with the mock server.
    """
    base_url, _ = mock_server
    session = requests.Session()
    session.base_url = base_url  # Store for convenience
    
    # Add request adapter to prepend base URL
    class BaseUrlAdapter(requests.adapters.BaseAdapter):
        def send(self, request, **kwargs):
            if not request.url.startswith(('http://', 'https://')):
                request.url = f"{base_url.rstrip('/')}/{request.url.lstrip('/')}"
            return super().send(request, **kwargs)
            
    session.mount('', BaseUrlAdapter())
    
    return session

# ----- Configuring Pytest -----

def pytest_addoption(parser):
    group = parser.getgroup("contract-testing")
    group.addoption(
        "--contracts-dir",
        default=None,
        help="Directory containing contract definition files"
    )
    group.addoption(
        "--mock-server-cmd",
        default="mock-server",
        help="Command to start the mock server"
    )

# ----- Test Parametrization Helper -----

def parametrize_contract_versions(*versions):
    """
    Decorator to parametrize tests with multiple contract versions.
    
    Usage:
        @parametrize_contract_versions("users-v1.0.0", "users-v1.1.0")
        def test_user_api(contract_version, mock_server, api_client):
            ...
    """
    ids = [f"contract:{v}" for v in versions]
    marks = [pytest.mark.contract_version(v) for v in versions]
    return pytest.mark.parametrize("contract_version_param", versions, ids=ids, indirect=True,
                                  marks=marks)