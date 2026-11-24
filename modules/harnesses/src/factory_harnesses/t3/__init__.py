"""Persistent T3 threads. No fixture mode or implicit provider fallback."""

import asyncio
import hashlib
import json
import os
import shutil
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from factory_contracts import (
    ContractError,
    HarnessCapabilities,
    HarnessEvent,
    HarnessResult,
    TaskSpec,
    Usage,
)


class T3Harness:
    def __init__(self) -> None:
        self._baseline: dict[str, str | None] = {}

    async def catalog(self) -> list[dict[str, Any]]:
        home = Path(os.environ.get("T3CODE_HOME", str(Path.home() / ".t3"))) / "userdata"
        try:
            settings = json.loads(await asyncio.to_thread((home / "settings.json").read_text))
            manifest = json.loads(await asyncio.to_thread((home / "model-manifest.json").read_text))
            current = manifest["manifest"]["currentModels"]
            providers = settings["providerInstances"]
            return [
                {
                    "id": instance_id,
                    "driver": instance["driver"],
                    "name": instance.get("displayName") or instance_id,
                    "enabled": instance.get("enabled", True),
                    "models": current.get(instance["driver"], []),
                }
                for instance_id, instance in providers.items()
            ]
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise ContractError("T3 provider catalog is unavailable or incompatible") from exc

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(streaming=True, worktrees=True, name="t3")

    async def _cli(self, args: list[str], message: str | None = None) -> str:
        binary = os.environ.get("T3CODE_CLI_PATH") or shutil.which("t3")
        if not binary:
            candidate = Path.home() / ".t3/bin/t3"
            if candidate.is_file():
                binary = str(candidate)
        if not binary:
            raise ContractError("T3 is unavailable; install/start T3 and set T3CODE_CLI_PATH")
        process = await asyncio.create_subprocess_exec(
            binary,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(
                process.communicate(message.encode() if message is not None else None), timeout=60
            )
        except BaseException:
            process.kill()
            await process.wait()
            raise
        if process.returncode:
            # CLI stderr can contain prompts, credentials, or repository content.
            raise ContractError(f"T3 command {args[0]} {args[1]} failed ({process.returncode})")
        return stdout.decode()

    async def start_task(self, task: TaskSpec) -> str:
        provider = task.provider or os.environ.get("FACTORY_T3_PROVIDER", "")
        model = task.model or os.environ.get("FACTORY_T3_MODEL", "")
        if not provider or not model:
            raise ContractError("Select FACTORY_T3_PROVIDER and FACTORY_T3_MODEL explicitly")
        choices = await self.catalog()
        chosen = next((item for item in choices if item["id"] == provider), None)
        if not chosen or not chosen["enabled"] or model not in chosen["models"]:
            raise ContractError("Selected T3 provider/model is unavailable; refresh its catalog")
        if not task.repo or not await asyncio.to_thread(Path(task.repo).is_dir) or not task.branch:
            raise ContractError("T3 needs a prepared repository and a factory branch")
        await self._cli(["project", "add", task.repo, "--title", task.title or "Factory request"])
        raw = await self._cli(
            [
                "thread",
                "start",
                task.repo,
                "-",
                "--worktree",
                "HEAD",
                "--branch",
                task.branch,
                "--title",
                task.title or "Factory request",
                "--provider",
                provider,
                "--model",
                model,
                "--json",
            ],
            task.instruction,
        )
        try:
            thread_id = json.loads(raw)["threadId"]
            if not isinstance(thread_id, str) or not thread_id:
                raise ValueError
        except (KeyError, ValueError, TypeError) as exc:
            raise ContractError("T3 launch outcome is unknown; reconcile before retrying") from exc
        self._baseline[thread_id] = None
        return thread_id

    async def _show(self, task_id: str) -> dict[str, Any]:
        try:
            result = json.loads(await self._cli(["thread", "show", task_id, "--json"]))
            thread = result["thread"]
            if not isinstance(thread, dict) or "activeRunId" not in thread:
                raise ValueError
            if thread.get("archived"):
                raise ContractError("T3 thread was archived")
            return result
        except (ValueError, KeyError, TypeError) as exc:
            raise ContractError(
                "Unsupported T3 thread response; refusing to infer success"
            ) from exc

    async def stream_events(self, task_id: str) -> AsyncGenerator[HarnessEvent, None]:
        async with asyncio.timeout(int(os.environ.get("FACTORY_HARNESS_TIMEOUT", "600"))):
            while True:
                shown = await self._show(task_id)
                text = self._last_message(shown)
                if (
                    not shown["thread"]["activeRunId"]
                    and text
                    and text != self._baseline.get(task_id)
                ):
                    yield HarnessEvent(type="result", message=self._last_message(shown))
                    return
                yield HarnessEvent(
                    type="progress",
                    message=hashlib.sha256(json.dumps(shown, sort_keys=True).encode()).hexdigest(),
                )
                await asyncio.sleep(2)

    @staticmethod
    def _last_message(shown: dict[str, Any]) -> str:
        messages = shown.get("messages") or []
        for item in reversed(messages):
            if isinstance(item, dict) and item.get("role") == "assistant":
                return str(item.get("text") or "")
        return ""

    async def recover_operation(self, task_id: str, marker: str, previous: str) -> None:
        shown = await self._show(task_id)
        messages = shown.get("messages") or []
        if not any(
            isinstance(item, dict)
            and item.get("role") == "user"
            and marker in str(item.get("text", ""))
            for item in messages
        ):
            raise ContractError(
                "Cannot prove the pending instruction reached T3; operator action required"
            )
        self._baseline[task_id] = previous

    async def send_message(self, task_id: str, message: str) -> None:
        shown = await self._show(task_id)
        if shown["thread"]["activeRunId"]:
            raise ContractError("T3 is busy; refusing to queue a duplicate stage")
        self._baseline[task_id] = self._last_message(shown)
        await self._cli(["thread", "send", task_id, "-"], message)

    async def get_result(self, task_id: str) -> HarnessResult:
        shown = await self._show(task_id)
        thread = shown["thread"]
        text = self._last_message(shown)
        # Idle alone is not success: questions, permissions, failures also stop a turn.
        status = "ok" if not thread["activeRunId"] and text else "failed"
        if thread.get("status") in {"failed", "error", "cancelled", "waiting", "interrupted"}:
            status = "failed"
        return HarnessResult(status=status, summary=text, workspace=thread.get("worktreePath"))

    async def cancel(self, task_id: str) -> None:
        import httpx

        home = Path(os.environ.get("T3CODE_HOME", str(Path.home() / ".t3")))
        try:
            runtime = json.loads(
                await asyncio.to_thread((home / "userdata/server-runtime.json").read_text)
            )
            origin = runtime["origin"]
            url = httpx.URL(origin)
            if url.host not in {"127.0.0.1", "localhost", "::1"}:
                raise ValueError
            issued = json.loads(
                await self._cli(
                    [
                        "auth",
                        "session",
                        "issue",
                        "--scope",
                        "orchestration:read",
                        "--scope",
                        "orchestration:operate",
                        "--ttl",
                        "5m",
                        "--label",
                        "factory-interrupt",
                        "--json",
                    ]
                )
            )
            token, session_id = issued["token"], issued["sessionId"]
        except (ValueError, KeyError, OSError) as exc:
            raise ContractError(
                "T3 interrupt authentication failed; stop the session in T3"
            ) from exc
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json, text/event-stream",
                }

                async def rpc(body: dict[str, Any]) -> dict[str, Any]:
                    response = await client.post(origin + "/mcp", headers=headers, json=body)
                    response.raise_for_status()
                    if response.headers.get("mcp-session-id"):
                        headers["mcp-session-id"] = response.headers["mcp-session-id"]
                    if "id" not in body:
                        return {}
                    if "event-stream" in response.headers.get("content-type", ""):
                        replies = [
                            json.loads(line[5:])
                            for line in response.text.splitlines()
                            if line.startswith("data:")
                        ]
                        reply = next(item for item in replies if item.get("id") == body["id"])
                    else:
                        reply = response.json()
                    if reply.get("error"):
                        raise ContractError("T3 refused interrupt RPC")
                    return reply["result"]

                await rpc(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {},
                            "clientInfo": {"name": "software-factory", "version": "0.1.0"},
                        },
                    }
                )
                await rpc({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
                result = await rpc(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "t3_thread_interrupt",
                            "arguments": {
                                "threadId": task_id,
                                "reason": "Factory stopped this request",
                                "clientRequestId": f"factory-stop-{task_id}",
                            },
                        },
                    }
                )
                if result.get("isError"):
                    raise ContractError("T3 refused session interruption")
        finally:
            await self._cli(["auth", "session", "revoke", session_id])
        async with asyncio.timeout(30):
            for _attempt in range(30):
                if not (await self._show(task_id))["thread"]["activeRunId"]:
                    return
                await asyncio.sleep(1)
        raise ContractError("T3 did not confirm session interruption")

    async def usage(self, task_id: str) -> Usage:
        raise ContractError("This T3 CLI integration does not expose verified billing usage")
