#!/usr/bin/env python3
import os
import sys
import ctypes
import subprocess

# Constants for namespaces
CLONE_NEWUTS  = 0x04000000
CLONE_NEWPID  = 0x20000000
CLONE_NEWNS   = 0x00020000
CLONE_NEWNET  = 0x40000000  # <--- Added for Network isolation

# Mount flags
MS_REC = 16384
MS_PRIVATE = 1 << 18

libc = ctypes.CDLL("libc.so.6", use_errno=True)

def apply_limits(pid):
    """Apply PID, Memory, and CPU limits using cgroup v2"""
    cgroup_path = f"/sys/fs/cgroup/mdocker_{pid}"
    try:
        os.makedirs(cgroup_path, exist_ok=True)
        
        # 1. Limit PIDs (Max 50 processes)
        with open(f"{cgroup_path}/pids.max", "w") as f:
            f.write("50")
            
        # 2. Limit Memory (100MB)
        with open(f"{cgroup_path}/memory.max", "w") as f:
            f.write("104857600") # 100 * 1024 * 1024
            
        # 3. Limit CPU (Max 20% of one core)
        # Format: $MAX $PERIOD (20000 / 100000 = 20%)
        with open(f"{cgroup_path}/cpu.max", "w") as f:
            f.write("20000 100000")

        # Attach process to cgroup
        with open(f"{cgroup_path}/cgroup.procs", "w") as f:
            f.write(str(pid))
        print(f"[Host] Limits applied: 100MB RAM, 20% CPU")
    except Exception as e:
        print(f"[Host] Cgroup Error: {e}")

def setup_network(pid):
    """Creates a virtual ethernet bridge for the container"""
    # This is a simplified version of what Docker does:
    # 1. Create veth pair (veth0 <-> veth1)
    # 2. Move veth1 into the container's PID namespace
    # 3. Give veth1 an IP and bring it up
    try:
        # Create the veth pair
        subprocess.run(["ip", "link", "add", "veth0", "type", "veth", "peer", "name", "veth1"], check=True)
        # Move veth1 to the container
        subprocess.run(["ip", "link", "set", "veth1", "netns", str(pid)], check=True)
        # Set host side up
        subprocess.run(["ip", "addr", "add", "10.0.0.1/24", "dev", "veth0"], check=True)
        subprocess.run(["ip", "link", "set", "veth0", "up"], check=True)
        print(f"[Host] Network bridge veth0 created for PID {pid}")
    except Exception as e:
        print(f"[Host] Network Error: {e}")

def run_inside_container(rootfs_path, args):
    """The final isolated process"""
    libc.mount(None, b"/", None, MS_REC | MS_PRIVATE, None)
    
    # Configure networking inside the container
    # Note: We use 'ip' command which must exist inside your rootfs
    subprocess.run(["ip", "link", "set", "lo", "up"], check=False)
    subprocess.run(["ip", "addr", "add", "10.0.0.2/24", "dev", "veth1"], check=False)
    subprocess.run(["ip", "link", "set", "veth1", "up"], check=False)

    hostname = b"container-runtime"
    libc.sethostname(hostname, len(hostname))

    os.chroot(rootfs_path)
    os.chdir("/")

    os.makedirs("/proc", exist_ok=True)
    libc.mount(b"proc", b"/proc", b"proc", 0, None)

    print(f"[Child] Container active. Running: {' '.join(args)}")
    os.execvp(args[0], args)

def container_setup(rootfs_path, args):
    """Isolate using Namespaces"""
    try:
        # Added CLONE_NEWNET for network isolation
        os.unshare(CLONE_NEWUTS | CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWNET)
    except PermissionError:
        print("Error: Need root/sudo.")
        sys.exit(1)

    pid = os.fork()
    if pid == 0:
        run_inside_container(rootfs_path, args)
    else:
        # Parent waits for child
        _, status = os.waitpid(pid, 0)
        sys.exit(os.waitstatus_to_exitcode(status))

def main():
    if len(sys.argv) < 4:
        print(f"Usage: sudo {sys.argv[0]} run <rootfs> <cmd>")
        sys.exit(1)

    rootfs_path = os.path.abspath(sys.argv[2])
    command_args = sys.argv[3:]

    # Step 1: Fork to create the container
    pid = os.fork()
    if pid == 0:
        container_setup(rootfs_path, command_args)
    else:
        # Step 2: Parent manages the container from the outside
        apply_limits(pid)
        setup_network(pid)
        try:
            os.waitpid(pid, 0)
        except KeyboardInterrupt:
            os.kill(pid, 9)

if __name__ == "__main__":
    main()
