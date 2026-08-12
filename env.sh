# shellcheck shell=sh

ENV_ROOT="${ENV_ROOT:-$HOME/.env}"
VENV_ROOT="$ENV_ROOT/.venv"
ENV_SCRIPTS_ROOT="$ENV_ROOT/tools/scripts"
ENV_BOOTSTRAP="$ENV_SCRIPTS_ROOT/env_venv.py"
ENV_ACTIVATE="$VENV_ROOT/bin/activate"
bootstrap_status=0
activate_status=0

export ENV_ROOT
if [ "${ENV_VENV_AUTO_UPGRADE+x}" = "x" ]; then
    export ENV_VENV_AUTO_UPGRADE
fi
if [ "${ENV_PYPI_INDEX_URL+x}" = "x" ]; then
    export ENV_PYPI_INDEX_URL
fi

if command -v python3 >/dev/null 2>&1; then
    BOOTSTRAP_PYTHON=python3
elif [ -x "$VENV_ROOT/bin/python" ]; then
    BOOTSTRAP_PYTHON="$VENV_ROOT/bin/python"
else
    BOOTSTRAP_PYTHON=
fi

if [ -z "$BOOTSTRAP_PYTHON" ]; then
    echo "Cannot prepare the RT-Thread Env venv: Python 3 was not found." >&2
    bootstrap_status=1
elif [ ! -f "$ENV_BOOTSTRAP" ]; then
    echo "Cannot prepare the RT-Thread Env venv: $ENV_BOOTSTRAP was not found." >&2
    bootstrap_status=1
else
    "$BOOTSTRAP_PYTHON" "$ENV_BOOTSTRAP" \
        --venv "$VENV_ROOT" \
        --source "$ENV_SCRIPTS_ROOT" \
        --activation-script "$ENV_ROOT/env.sh" || bootstrap_status=$?
fi

if [ -f "$ENV_ACTIVATE" ]; then
    if ! . "$ENV_ACTIVATE"; then
        echo "Failed to activate the RT-Thread Env Python venv." >&2
        activate_status=1
    fi
else
    echo "Cannot activate the RT-Thread Env Python venv: $ENV_ACTIVATE was not found." >&2
    activate_status=1
fi

export PATH="$ENV_SCRIPTS_ROOT:$PATH"
export RTT_EXEC_PATH=/usr/bin

if [ "$activate_status" -ne 0 ]; then
    return "$activate_status" 2>/dev/null || exit "$activate_status"
fi
if [ "$bootstrap_status" -ne 0 ]; then
    return "$bootstrap_status" 2>/dev/null || exit "$bootstrap_status"
fi
