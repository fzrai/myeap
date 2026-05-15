"""Tests for Docker-related functionality."""

import subprocess
import sys


def test_dockerfile_syntax():
    """Test that Dockerfile exists and has valid syntax."""
    from pathlib import Path

    dockerfile_path = Path(__file__).parent.parent.parent.parent / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile not found"

    content = dockerfile_path.read_text()

    # Check for essential Dockerfile directives
    assert "FROM python:3.11-slim" in content, "Base image not found"
    assert "WORKDIR /app" in content, "WORKDIR directive not found"
    assert "EXPOSE 8000" in content, "EXPOSE directive not found"


def test_dockerfile_has_production_stage():
    """Test that Dockerfile has a production stage."""
    from pathlib import Path

    dockerfile_path = Path(__file__).parent.parent.parent.parent / "Dockerfile"
    content = dockerfile_path.read_text()

    assert "FROM base as production" in content, "Production stage not found"
    assert "USER appuser" in content, "Non-root user not configured"


def test_dockerfile_has_healthcheck():
    """Test that production stage has healthcheck configured."""
    from pathlib import Path

    dockerfile_path = Path(__file__).parent.parent.parent.parent / "Dockerfile"
    content = dockerfile_path.read_text()

    assert "HEALTHCHECK" in content, "HEALTHCHECK not found"


def test_dockerfile_has_uv():
    """Test that Dockerfile installs uv package manager."""
    from pathlib import Path

    dockerfile_path = Path(__file__).parent.parent.parent.parent / "Dockerfile"
    content = dockerfile_path.read_text()

    assert "uv" in content.lower(), "uv package manager not found"


def test_dockerfile_has_development_stage():
    """Test that Dockerfile has a development stage."""
    from pathlib import Path

    dockerfile_path = Path(__file__).parent.parent.parent.parent / "Dockerfile"
    content = dockerfile_path.read_text()

    assert "FROM base as development" in content, "Development stage not found"


def test_docker_compose_files_exist():
    """Test that docker-compose files exist."""
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent.parent

    assert (project_root / "docker-compose.yml").exists(), "docker-compose.yml not found"
    assert (project_root / "docker-compose.dev.yml").exists(), "docker-compose.dev.yml not found"


def test_docker_compose_has_required_services():
    """Test that docker-compose.yml has required services."""
    from pathlib import Path
    import yaml

    docker_compose_path = Path(__file__).parent.parent.parent.parent / "docker-compose.yml"

    with open(docker_compose_path) as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})

    assert "api" in services, "API service not found"
    assert "postgres" in services, "PostgreSQL service not found"
    assert "redis" in services, "Redis service not found"
    assert "kafka" in services, "Kafka service not found"


def test_docker_compose_dev_has_volume_mount():
    """Test that docker-compose.dev.yml has volume mount for hot reload."""
    from pathlib import Path
    import yaml

    docker_compose_path = Path(__file__).parent.parent.parent.parent / "docker-compose.dev.yml"

    with open(docker_compose_path) as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    api_service = services.get("api", {})

    assert "volumes" in api_service, "Volumes not configured for API service"
    assert any("./src:/app/src" in vol for vol in api_service["volumes"]), "Source volume mount not found"


def test_dockerignore_exists():
    """Test that .dockerignore file exists."""
    from pathlib import Path

    dockerignore_path = Path(__file__).parent.parent.parent.parent / ".dockerignore"
    assert dockerignore_path.exists(), ".dockerignore not found"

    content = dockerignore_path.read_text()

    # Check for common ignores
    assert ".git" in content, ".git not ignored"
    assert "__pycache__" in content, "__pycache__ not ignored"
    assert ".venv" in content or "venv/" in content, "venv not ignored"


def test_docker_available():
    """Test if Docker is available (optional - skips if not available)."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            assert "Docker version" in result.stdout
        else:
            pass  # Docker not available, skip
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # Docker not available, skip test


def test_docker_compose_valid_yaml():
    """Test that docker-compose files are valid YAML."""
    from pathlib import Path
    import yaml

    project_root = Path(__file__).parent.parent.parent.parent

    for filename in ["docker-compose.yml", "docker-compose.dev.yml"]:
        filepath = project_root / filename
        with open(filepath) as f:
            try:
                compose = yaml.safe_load(f)
                assert compose is not None, f"{filename} is empty"
                assert "services" in compose, f"{filename} missing services key"
            except yaml.YAMLError as e:
                raise AssertionError(f"{filename} has invalid YAML: {e}")
