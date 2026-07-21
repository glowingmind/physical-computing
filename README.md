# Physical computing

This repository represents a collection of Python demos for physical computing and robotics projects using the Raspberry Pi computers. It includes examples for controlling GPIO pins, reading sensors, and interfacing with various hardware components. This repository is quickly growing and taking shape so please forgive its current lack of clear structure and documentation. We will be improving this over time. 

The demos are written in Python 3 and organized in the categories based on the library used to control the GPIO pins. The goal is to publish walkthroughs and tutorials of all of these projects on GitHub pages as a public website and to have supporting videos (or past streams ) on YouTube. This is a very early stage of the project and we are still working on the content. Please check back often for updates.

## Set up Python virtual environment

We recommend using a Python virtual environment to manage dependencies for the demos in this repository. You can create and activate a virtual environment on a Linux machine using the following commands. If you are on a Mac or Windows machine, please refer to the Python documentation for instructions on creating and activating virtual environments on those platforms.

```bash
# Create a Python virtual environment
python -m venv --system-site-packages ./phcmp_venv

# Activate the virtual environment
source ./phcmp_venv/bin/activate

# Run a demo script in Python
python lgpio-lib-demos/lgpio_fan_control.py

# Exit the virtual environment
deactivate
```

This creates a virtual environment named `phcmp_venv` in the current directory. The `--system-site-packages` flag allows the virtual environment to access the system's site-packages, which can be useful if you want to use packages that are already installed on your system.