#!/usr/bin/env python3
"""
Recall - Simple local development launcher
Cross-platform script to set up and run Recall locally.

Usage:
    python recall.py setup    # First-time setup
    python recall.py run      # Start Recall (Qdrant + API)
    python recall.py api      # Start API only (Qdrant must be running)
"""

import subprocess
import sys
import os
import time
import platform
import urllib.request
import zipfile
from pathlib import Path


class Colors:
    """Terminal colors"""
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

    @staticmethod
    def strip():
        """Disable colors on Windows without ANSI support"""
        if platform.system() == 'Windows' and not os.environ.get('ANSICON'):
            Colors.BLUE = Colors.GREEN = Colors.YELLOW = Colors.RED = Colors.BOLD = Colors.END = ''


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")


def print_success(text):
    print(f"{Colors.GREEN}[OK] {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}[ERROR] {text}{Colors.END}")


def print_info(text):
    print(f"{Colors.YELLOW}[INFO] {text}{Colors.END}")


def get_project_root():
    """Get the project root directory (parent of 'local' folder)"""
    return Path(__file__).parent.parent.resolve()


def check_python_version():
    """Ensure Python 3.11+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print_error(f"Python 3.11+ required, you have {version.major}.{version.minor}")
        sys.exit(1)
    print_success(f"Python {version.major}.{version.minor}.{version.micro}")


def setup_venv():
    """Create and set up virtual environment"""
    root = get_project_root()
    venv_path = root / "venv"

    if venv_path.exists():
        print_success("Virtual environment already exists")
        return venv_path

    print_info("Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    print_success("Virtual environment created")
    return venv_path


def get_venv_python(venv_path):
    """Get path to Python executable in venv"""
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def install_dependencies(venv_python):
    """Install Python packages"""
    root = get_project_root()
    requirements = root / "requirements.txt"

    print_info("Upgrading pip...")
    subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
                   check=True, capture_output=True)

    print_info("Installing dependencies (this may take a few minutes)...")
    subprocess.run([str(venv_python), "-m", "pip", "install", "-r", str(requirements)],
                   check=True)
    print_success("Dependencies installed")

    print_info("Downloading spaCy language model...")
    # Try to download using pip directly (more reliable than spacy download)
    result = subprocess.run(
        [str(venv_python), "-m", "pip", "install",
         "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0-py3-none-any.whl"],
        capture_output=True
    )

    if result.returncode != 0:
        # Fallback: try the spacy download command
        result = subprocess.run(
            [str(venv_python), "-m", "spacy", "download", "en_core_web_sm"],
            capture_output=True
        )

    if result.returncode == 0:
        print_success("spaCy model downloaded")
    else:
        print_error("Failed to download spaCy model automatically")
        print_info("You can install it manually later with: python -m spacy download en_core_web_sm")
        print_info("The system will work without it, but entity extraction may be limited")


def create_directories():
    """Create data directories"""
    root = get_project_root()
    dirs = [
        root / "data" / "qdrant_storage",
        root / "data" / "kuzu"
    ]

    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
    print_success("Data directories created")


def check_qdrant_running():
    """Check if Qdrant is running on port 6333"""
    try:
        response = urllib.request.urlopen('http://localhost:6333/healthz', timeout=2)
        return response.status == 200
    except:
        return False


def get_qdrant_download_url():
    """Get Qdrant download URL for current platform"""
    system = platform.system()
    version = "v1.7.4"

    if system == "Windows":
        return f"https://github.com/qdrant/qdrant/releases/download/{version}/qdrant-x86_64-pc-windows-msvc.zip"
    elif system == "Linux":
        return f"https://github.com/qdrant/qdrant/releases/download/{version}/qdrant-x86_64-unknown-linux-gnu.tar.gz"
    elif system == "Darwin":  # macOS
        machine = platform.machine()
        if machine == "arm64":
            return f"https://github.com/qdrant/qdrant/releases/download/{version}/qdrant-aarch64-apple-darwin.tar.gz"
        else:
            return f"https://github.com/qdrant/qdrant/releases/download/{version}/qdrant-x86_64-apple-darwin.tar.gz"
    else:
        return None


def download_qdrant():
    """Download Qdrant standalone binary"""
    root = get_project_root()
    qdrant_dir = root / "qdrant_standalone"

    # Check if already downloaded
    if platform.system() == "Windows":
        qdrant_exe = qdrant_dir / "qdrant.exe"
    else:
        qdrant_exe = qdrant_dir / "qdrant"

    if qdrant_exe.exists():
        print_success("Qdrant already downloaded")
        return qdrant_exe

    # Get download URL
    url = get_qdrant_download_url()
    if not url:
        print_error(f"Qdrant standalone not available for {platform.system()}")
        print_info("Please use Docker: docker run -p 6333:6333 qdrant/qdrant")
        return None

    print_info("Downloading Qdrant standalone...")
    qdrant_dir.mkdir(exist_ok=True)

    archive_name = "qdrant.zip" if platform.system() == "Windows" else "qdrant.tar.gz"
    archive_path = qdrant_dir / archive_name

    # Download
    urllib.request.urlretrieve(url, archive_path)
    print_success("Downloaded")

    # Extract
    print_info("Extracting...")
    if platform.system() == "Windows":
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(qdrant_dir)
    else:
        import tarfile
        with tarfile.open(archive_path, 'r:gz') as tar_ref:
            tar_ref.extractall(qdrant_dir)
        # Make executable
        qdrant_exe.chmod(0o755)

    archive_path.unlink()
    print_success("Qdrant ready")

    return qdrant_exe


def start_qdrant():
    """Start Qdrant in background"""
    if check_qdrant_running():
        print_success("Qdrant is already running")
        return None

    print_info("Starting Qdrant...")

    qdrant_exe = download_qdrant()
    if not qdrant_exe:
        print_error("Could not start Qdrant")
        print_info("Please start Qdrant manually:")
        print_info("  docker run -p 6333:6333 -v $(pwd)/data/qdrant_storage:/qdrant/storage qdrant/qdrant")
        sys.exit(1)

    root = get_project_root()
    storage_path = root / "data" / "qdrant_storage"
    storage_path.mkdir(parents=True, exist_ok=True)

    # Create config file for Qdrant
    qdrant_dir = qdrant_exe.parent
    config_path = qdrant_dir / "config.yaml"

    if not config_path.exists():
        config_content = f"""storage:
  storage_path: {str(storage_path).replace(chr(92), '/')}

service:
  host: 0.0.0.0
  http_port: 6333
  grpc_port: 6334

telemetry_disabled: true
"""
        config_path.write_text(config_content)

    # Start process with config file
    process = subprocess.Popen(
        [str(qdrant_exe), "--config-path", str(config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(qdrant_dir)
    )

    # Wait for startup
    print_info("Waiting for Qdrant to start...")
    for i in range(30):
        if check_qdrant_running():
            print(f"{Colors.GREEN}[OK] Qdrant started{Colors.END}")
            return process
        time.sleep(1)
        if i % 5 == 0:
            print(".", end="", flush=True)

    print(f"\n{Colors.RED}[ERROR] Qdrant failed to start{Colors.END}")
    print_error("Qdrant failed to start")
    return None


def start_api(venv_python):
    """Start FastAPI server"""
    root = get_project_root()

    # Check Qdrant
    print_info("Checking Qdrant connection...")
    if not check_qdrant_running():
        print_error("Qdrant is not running!")
        print_info("Start Qdrant first with: python recall.py run")
        sys.exit(1)
    print_success("Qdrant connected")

    # Set environment variables
    os.environ['QDRANT_HOST'] = 'localhost'
    os.environ['QDRANT_PORT'] = '6333'
    os.environ['KUZU_PATH'] = './data/kuzu'
    os.environ['SQLITE_PATH'] = './data/recall.db'

    backend_dir = root / "backend"

    print_header("Recall API Server")
    print(f"{Colors.BOLD}API Documentation:{Colors.END} http://localhost:8000/docs")
    print(f"{Colors.BOLD}Health Check:{Colors.END}     http://localhost:8000/health")
    print(f"{Colors.BOLD}Qdrant Dashboard:{Colors.END} http://localhost:6333/dashboard")
    print(f"\n{Colors.YELLOW}Press Ctrl+C to stop{Colors.END}\n")

    try:
        subprocess.run(
            [str(venv_python), "-m", "uvicorn", "main:app",
             "--reload", "--host", "0.0.0.0", "--port", "8000"],
            cwd=str(backend_dir)
        )
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Server stopped{Colors.END}")


def cmd_setup():
    """Setup command: install dependencies and prepare environment"""
    print_header("Recall Setup")

    check_python_version()
    venv_path = setup_venv()
    venv_python = get_venv_python(venv_path)
    install_dependencies(venv_python)
    create_directories()

    print_header("Setup Complete!")
    print(f"{Colors.GREEN}Next steps:{Colors.END}")
    print(f"  {Colors.BOLD}python local/recall.py run{Colors.END}    # Start Recall")
    print()


def cmd_run():
    """Run command: start both Qdrant and API"""
    root = get_project_root()
    venv_path = root / "venv"

    if not venv_path.exists():
        print_error("Virtual environment not found. Run setup first:")
        print_info("python local/recall.py setup")
        sys.exit(1)

    venv_python = get_venv_python(venv_path)

    print_header("Starting Recall")

    try:
        # Start Qdrant
        qdrant_process = start_qdrant()

        # Start API
        start_api(venv_python)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Stopping servers...{Colors.END}")
        if qdrant_process:
            qdrant_process.terminate()
        sys.exit(0)


def cmd_api():
    """API-only command: start just the API server"""
    root = get_project_root()
    venv_path = root / "venv"

    if not venv_path.exists():
        print_error("Virtual environment not found. Run setup first:")
        print_info("python local/recall.py setup")
        sys.exit(1)

    venv_python = get_venv_python(venv_path)
    start_api(venv_python)


def show_help():
    """Show usage help"""
    print(f"""
{Colors.BOLD}Recall - Local Development Launcher{Colors.END}

{Colors.BOLD}Usage:{Colors.END}
    python local/recall.py setup    {Colors.YELLOW}# First-time setup{Colors.END}
    python local/recall.py run      {Colors.YELLOW}# Start Recall (Qdrant + API){Colors.END}
    python local/recall.py api      {Colors.YELLOW}# Start API only{Colors.END}

{Colors.BOLD}Commands:{Colors.END}
    {Colors.GREEN}setup{Colors.END}    Install dependencies and prepare environment
    {Colors.GREEN}run{Colors.END}      Start both Qdrant and the API server
    {Colors.GREEN}api{Colors.END}      Start only the API server (Qdrant must be running)

{Colors.BOLD}First-time users:{Colors.END}
    1. python local/recall.py setup
    2. python local/recall.py run
    3. Open http://localhost:8000/docs
""")


def main():
    Colors.strip()

    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "setup":
        cmd_setup()
    elif command == "run":
        cmd_run()
    elif command == "api":
        cmd_api()
    elif command in ["help", "-h", "--help"]:
        show_help()
    else:
        print_error(f"Unknown command: {command}")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
