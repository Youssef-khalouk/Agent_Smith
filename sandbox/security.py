import ctypes
import ctypes.util
import os


CLONE_NEWUSER = 0x10000000
CLONE_NEWNS = 0x00020000


def unshare(flags: int) -> None:
    """
    Call the unshare(2) syscall on the current process, disassociating it
    from the namespaces specified by `flags` and giving it new ones.

    Must be called before any code that depends on being in the new
    namespace (e.g. before writing uid_map/gid_map, before mount()).
    """
    libc_path = ctypes.util.find_library("c")
    if libc_path is None:
        raise OSError("could not locate libc")

    libc = ctypes.CDLL(libc_path, use_errno=True)

    ret = libc.unshare(ctypes.c_int(flags))
    if ret != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno), "unshare() failed")


def map_root_user() -> None:
    """
    Map the calling process's real uid/gid to uid/gid 0 inside the new
    user namespace, equivalent to `unshare --map-root-user`.

    Must be called after unshare(CLONE_NEWUSER), and before attempting
    any operation (mount, chroot, etc.) that requires namespace-root
    privileges.
    """
    uid = os.getuid()
    gid = os.getgid()

    # Required by the kernel: gid_map cannot be written by an
    # unprivileged process unless setgroups is first denied.
    with open("/proc/self/setgroups", "w") as f:
        f.write("deny")

    with open("/proc/self/uid_map", "w") as f:
        f.write(f"0 {uid} 1\n")

    with open("/proc/self/gid_map", "w") as f:
        f.write(f"0 {gid} 1\n")