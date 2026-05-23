# Physical computing

A collection of Python scripts for various physical computing projects with Raspberry Pi, Arduino, and other microcontrollers.

## Python virtual environment

```bash
# Create a Python virtual environment
python -m venv --system-site-packages ./camera_venv
# to activate the virtual environment
source ./camera_venv/bin/activate
# to exit the virtual environment
deactivate
```

This creates a virtual environment named `camera_venv` in the current directory. The `--system-site-packages` flag allows the virtual environment to access the system's site-packages, which can be useful if you want to use packages that are already installed globally.