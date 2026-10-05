"""SSH connection helper and execution manager using Paramiko."""

import os
from typing import Optional, Tuple
import paramiko
from app.models import SshConnection


class SshManager:
    @staticmethod
    def create_client(conn: SshConnection, timeout: float = 8.0) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        kwargs = {
            "hostname": conn.host,
            "port": conn.port,
            "username": conn.username or None,
            "timeout": timeout,
            "banner_timeout": timeout,
        }

        # Handle key file or password
        if conn.key_path:
            expanded_key = os.path.expanduser(conn.key_path)
            if os.path.exists(expanded_key):
                kwargs["key_filename"] = expanded_key
            else:
                raise FileNotFoundError(f"Key file not found: {conn.key_path}")

        if conn.password:
            kwargs["password"] = conn.password

        client.connect(**kwargs)
        return client

    @staticmethod
    def test_connection(conn: SshConnection) -> Tuple[bool, str]:
        """Tests an SSH connection, returning (success, message)."""
        try:
            client = SshManager.create_client(conn, timeout=5.0)
            client.close()
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def run_detached(conn: SshConnection, directory: str, command: str) -> Tuple[bool, str, str]:
        """Executes a detached/background command over SSH via nohup."""
        try:
            client = SshManager.create_client(conn)
            cmd = command.strip()
            if directory.strip():
                dir_esc = directory.strip().replace("'", "'\\''")
                full_cmd = f"cd '{dir_esc}' && nohup {cmd} >/dev/null 2>&1 & echo $!"
            else:
                full_cmd = f"nohup {cmd} >/dev/null 2>&1 & echo $!"

            stdin, stdout, stderr = client.exec_command(full_cmd)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            client.close()
            return True, out, err
        except Exception as e:
            return False, "", str(e)
