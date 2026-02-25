Setup: Create the Root Filesystem
Before running the container, you need a minimal Linux filesystem (Alpine Linux is recommended for its small size).

Run the following commands in your terminal:

```bash
# 1. Create a directory for the container image
mkdir -p container_root

# 2. Download the Alpine Linux Mini RootFS
# Note: Ensure the URL is valid. For 2026, you may want to check for the latest stable version.
wget https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/x86_64/alpine-minirootfs-3.18.4-x86_64.tar.gz

# 3. Extract the filesystem into the directory
# 'sudo' is often required to preserve file permissions and ownership (like root:root)
sudo tar -xzf alpine-minirootfs-3.18.4-x86_64.tar.gz -C container_root

# 4. Prepare your script
chmod +x mdocker.py
sudo ./mdocker.py run ./container_root /bin/sh

# 5. Also show the hostname
# run inside the container
export PS1='\u@\h:\w# '
