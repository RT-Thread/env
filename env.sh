# Can be overridden by $ENV_ROOT environment variable
# Get script directory as default ENV_ROOT
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export "ENV_ROOT=$SCRIPT_DIR"

# Virtual environment directory name
RT_VENV_DIR="$ENV_ROOT/venv/rt-env"

# Activate Python virtual environment
if [ -f "$RT_VENV_DIR/bin/activate" ]; then
    source "$RT_VENV_DIR/bin/activate"
    
    # Show welcome message using rt-env command
    if command -v rt-env &> /dev/null; then
        rt-env -v
    fi
else
    echo "Virtual environment not found. Please run the installation script first."
    return 1
fi

# Set PATH
# export PATH="$ENV_ROOT/tools/scripts:$PATH"
export RTT_EXEC_PATH=/usr/bin
