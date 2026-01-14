# Screenshot
<img src="https://github.com/kuzeyron/LindCam/blob/main/screenshots/Screenshot1.png" />

# Virtual Environment (venv) setup:
```sh
# Place these two in ~/.bashrc
alias activate='source .venv/bin/activate'
alias venv='python -m venv .venv'

# Refresh .bashrc only once:
source ~/.bashrc

# Creating venv
venv

# Activating the venv (always trigger this when you are returning to this project. Such as you have exited the terminal)
activate

# Packages to install
pip install -r requirements.txt
```

# Executing the project
```sh
# Running the fullscreen app
python receiver.py

# Running the client that is meant for Android:
python main.py
```
