# shellcheck shell=sh
VENV_ROOT="$HOME/.env/.venv"

if [ ! -d "$VENV_ROOT" ]; then
    echo "Create Python venv for RT-Thread..."
    python3 -m venv "$VENV_ROOT" || return
    if ! "$VENV_ROOT/bin/python" -m pip install --upgrade pip ||
        ! "$VENV_ROOT/bin/pip" install "$HOME/.env/tools/scripts"; then
        rm -rf "$VENV_ROOT"
        return 1
    fi
fi

. "$VENV_ROOT/bin/activate"
export PATH="$HOME/.env/tools/scripts:$PATH"
export RTT_EXEC_PATH=/usr/bin
