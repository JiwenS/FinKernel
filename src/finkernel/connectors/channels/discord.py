from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable

import discord

from finkernel.config import Settings
from finkernel.schemas.ui import DiscordConfirmationMessage
from finkernel.storage.models import WorkflowRequestModel

logger = logging.getLogger(__name__)


class ConfirmationView(discord.ui.View):
    def __init__(
        self,
        *,
        actor_handler: Callable[[str, str, str, str], str],
        request_id: str,
        token: str,
    ) -> None:
        super().__init__(timeout=None)
        self.actor_handler = actor_handler
        self.request_id = request_id
        self.token = token

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        result = await asyncio.to_thread(
            self.actor_handler,
            str(interaction.user.id),
            "approve",
            self.request_id,
            self.token,
        )
        await interaction.response.send_message(result, ephemeral=True)
        self.stop()

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        result = await asyncio.to_thread(
            self.actor_handler,
            str(interaction.user.id),
            "reject",
            self.request_id,
            self.token,
        )
        await interaction.response.send_message(result, ephemeral=True)
        self.stop()


class DiscordHITLClient(discord.Client):
    def __init__(self, settings: Settings, action_handler: Callable[[str, str, str, str], str]) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)
        self.settings = settings
        self.action_handler = action_handler
        self._ready_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.discord_bot_token and self.settings.discord_channel_id)

    async def on_ready(self) -> None:
        logger.info("Discord bot ready as %s", self.user)
        self._ready_event.set()

    def start_background(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_client, daemon=True)
        self._thread.start()
        if not self._ready_event.wait(timeout=30):
            raise RuntimeError("Discord bot failed to become ready within 30 seconds.")

    def stop_background(self) -> None:
        if self._thread is None or self._loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(self.close(), self._loop)
        future.result(timeout=10)
        self._thread.join(timeout=10)
        self._thread = None
        self._loop = None
        self._ready_event.clear()

    def send_confirmation(self, workflow_request: WorkflowRequestModel) -> None:
        if not self.enabled:
            raise RuntimeError("Discord bot token and channel id must be configured for real HITL.")
        if not self.loop_running():
            raise RuntimeError("Discord bot loop is not running.")
        self._run_coroutine(self._send_confirmation_async(workflow_request))

    def send_status_update(self, workflow_request: WorkflowRequestModel, message: str) -> None:
        if not self.enabled or not self.loop_running():
            return
        self._run_coroutine(self._send_status_update_async(message))

    def _run_client(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.start(self.settings.discord_bot_token))
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    def _run_coroutine(self, coro: asyncio.Future | asyncio.coroutines) -> None:
        if self._loop is None:
            raise RuntimeError("Discord bot loop is not running.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        future.result(timeout=15)

    def loop_running(self) -> bool:
        return self._loop is not None and self._ready_event.is_set()

    async def _resolve_channel(self) -> discord.abc.Messageable:
        channel = self.get_channel(self.settings.discord_channel_id)
        if channel is None:
            channel = await self.fetch_channel(self.settings.discord_channel_id)
        return channel

    async def _send_confirmation_async(self, workflow_request: WorkflowRequestModel) -> None:
        channel = await self._resolve_channel()
        prefix = self.settings.discord_command_prefix
        notes_excerpt = None
        if workflow_request.notes:
            normalized = " ".join(workflow_request.notes.split())
            notes_excerpt = normalized[:350] + ("…" if len(normalized) > 350 else "")
        confirmation = DiscordConfirmationMessage(
            request_id=workflow_request.request_id,
            symbol=workflow_request.symbol,
            side=workflow_request.side,
            quantity=workflow_request.quantity,
            limit_price=workflow_request.limit_price,
            request_source=workflow_request.request_source,
            notes_excerpt=notes_excerpt,
            confirmation_token=workflow_request.confirmation_token,
            approve_command=f"{prefix}approve {workflow_request.request_id} {workflow_request.confirmation_token}",
            reject_command=f"{prefix}reject {workflow_request.request_id} {workflow_request.confirmation_token}",
        )
        body = self._build_confirmation_body(confirmation, is_advisor_suggestion=workflow_request.request_source == "advisor-loop")
        view = ConfirmationView(
            actor_handler=self.action_handler,
            request_id=workflow_request.request_id,
            token=workflow_request.confirmation_token,
        )
        await channel.send(body, view=view)

    async def _send_status_update_async(self, message: str) -> None:
        channel = await self._resolve_channel()
        await channel.send(message)

    @staticmethod
    def _build_confirmation_body(confirmation: DiscordConfirmationMessage, *, is_advisor_suggestion: bool) -> str:
        heading = "FinKernel advisor suggestion pending approval" if is_advisor_suggestion else "FinKernel approval required"
        lines = [
            heading,
            f"Request: {confirmation.request_id}",
            f"Order: {confirmation.side.upper()} {confirmation.quantity} {confirmation.symbol} @ {confirmation.limit_price}",
        ]
        if confirmation.request_source:
            lines.append(f"Source: {confirmation.request_source}")
        if confirmation.notes_excerpt:
            lines.append(f"Rationale: {confirmation.notes_excerpt}")
        lines.extend(
            [
                "Use the buttons below to approve or reject.",
                f"Fallback approve command: `{confirmation.approve_command}`",
                f"Fallback reject command: `{confirmation.reject_command}`",
            ]
        )
        return "\n".join(lines)
