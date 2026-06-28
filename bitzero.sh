#!/data/data/com.termux/files/usr/bin/bash

arch=$(uname -m)

if [ "$arch" = "aarch64" ]; then
    exec python -c "import sys; sys.path.insert(0, '$PREFIX/bin'); import bitzero_64" "$@"
else
    exec python -c "import sys; sys.path.insert(0, '$PREFIX/bin'); import bitzero_32" "$@"
fi
