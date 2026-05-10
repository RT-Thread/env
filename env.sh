#!/usr/bin/env bash

VENV_ROOT="$HOME/.env/.venv"
ENV_SCRIPTS="$HOME/.env/tools/scripts"

if [ ! -d "$VENV_ROOT" ]; then
    echo "Create Python venv for RT-Thread..."
    python3 -m venv "$VENV_ROOT"
    # shellcheck source=/dev/null
    source "$VENV_ROOT/bin/activate"

    python -m pip install --upgrade pip
    pip install "$ENV_SCRIPTS"
else
    # shellcheck source=/dev/null
    source "$VENV_ROOT/bin/activate"
fi

export PATH="$VENV_ROOT/bin:$ENV_SCRIPTS:$PATH"
