# How I upgrade Chia on one harvester today.

### UPDATE INSTRUCTIONS

```
# Change directory
cd ~/chia-blockchain

# Activate the virtual environment
. ./activate

# Stop running services
chia stop -d all

# Deactivate the virtual environment
deactivate

# Remove the current virtual environments
rm -r venv
rm -r .penv
rm -r .venv

# Pull the latest version
git fetch
git checkout latest
git reset --hard FETCH_HEAD --recurse-submodules

# This should say "nothing to commit, working tree clean"
# if you have uncommitted changes, RELEASE.dev0 will be reported
git status

# Install the new version
sh install.sh

# Activate the virtual environment
. ./activate

# Initialize the new version
chia init

# Start Upgraded Harvester
chia start harvester

```
