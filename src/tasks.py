import asyncio
import subprocess
from typing import Tuple
from src import config, db

ALLOWED_COMMANDS = config.ALLOWED_COMMANDS

MAX_OUTPUT_LENGTH = 4000

async def run_command(chat_id: int, command: str) -> Tuple[str, bool]:
    parts = command.strip().split()
    if not parts:
        return "No command provided.", False

    cmd_name = parts[0]
    if cmd_name not in ALLOWED_COMMANDS:
        return f"Command not allowed. Allowed: {', '.join(ALLOWED_COMMANDS)}", False

    try:
        result = await asyncio.wait_for(
            asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            ),
            timeout=30.0
        )
        
        stdout, stderr = await result.communicate()
        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""

        if error:
            output += f"\n[stderr: {error}]"

        if not output:
            output = "(no output)"

        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + "\n...(truncated)"

        await db.log_command(chat_id, command, output)
        
        return output, True

    except asyncio.TimeoutError:
        return "Command timed out (30s limit).", False
    except Exception as e:
        return f"Error: {str(e)}", False
