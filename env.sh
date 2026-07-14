# shellcheck shell=sh
VENV_ROOT="$HOME/.env/.venv"

if [ ! -d "$VENV_ROOT" ]; then
    echo "Create Python venv for RT-Thread..."
    if ! python3 -m venv "$VENV_ROOT"; then
        echo "Failed to create Python venv for RT-Thread."
        return 1
    fi
    if ! "$VENV_ROOT/bin/python" -m pip install --upgrade pip ||
        ! "$VENV_ROOT/bin/pip" install "$HOME/.env/tools/scripts"; then
        echo "Failed to install RT-Thread dependencies."
        rm -rf "$VENV_ROOT"
        return 1
    fi
fi

. "$VENV_ROOT/bin/activate"
export PATH="$HOME/.env/tools/scripts:$PATH"
export RTT_EXEC_PATH=/usr/bin
