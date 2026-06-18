"""
Account-level actions for fast-mcp-telegram: block/unblock users, delete messages,
delete/leave chats.

FORK EXTENSION for this deployment — NOT in upstream fast-mcp-telegram, which routes
destructive operations through the generic `invoke_mtproto` bridge. These wrappers give
the model dedicated, obvious tools instead.

Style mirrors src/tools/messages/editing.py: resolve entity -> Telethon call ->
structured result/error via log_and_build_error. Registered through
register_account_tools(mcp), called from server.py right after register_tools(mcp)
so the MCP server-card advertises these tools too.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.types import ToolAnnotations
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.types import Channel

from src.client.connection import get_connected_client
from src.server_components.mcp_tool_types import ChatId
from src.utils.entity import get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.logging_utils import log_operation_start, log_operation_success

logger = logging.getLogger(__name__)

_DOC = "https://github.com/leshchenko1979/fast-mcp-telegram/blob/main/docs/Tools-Reference.md"


def _d(body: str) -> str:
    """Append the canonical docs URL (kept out of f-strings so result braces stay literal)."""
    return body + f" Full documentation: {_DOC}"


def _chat_label(entity: Any) -> dict[str, Any]:
    return {
        "id": getattr(entity, "id", None),
        "username": getattr(entity, "username", None),
    }


async def _resolve_or_error(operation: str, chat_id: str, params: dict[str, Any]):
    """Resolve chat_id to an entity, or return (None, error_dict)."""
    entity = await get_entity_by_id(chat_id)
    if not entity:
        return None, log_and_build_error(
            operation=operation,
            error_message=f"Cannot find chat with ID '{chat_id}'",
            params=params,
            exception=ValueError(f"Cannot find any entity corresponding to '{chat_id}'"),
        )
    return entity, None


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

async def block_user_impl(chat_id: str) -> dict[str, Any]:
    params = {"chat_id": chat_id}
    log_operation_start("Blocking user", params)
    client = await get_connected_client()
    try:
        entity, err = await _resolve_or_error("block_user", chat_id, params)
        if err:
            return err
        await client(BlockRequest(id=entity))
        log_operation_success("User blocked", chat_id)
        return {"ok": True, "action": "blocked", "chat": _chat_label(entity)}
    except Exception as e:
        return log_and_build_error(
            operation="block_user",
            error_message=f"Failed to block: {e!s}",
            params=params,
            exception=e,
        )


async def unblock_user_impl(chat_id: str) -> dict[str, Any]:
    params = {"chat_id": chat_id}
    log_operation_start("Unblocking user", params)
    client = await get_connected_client()
    try:
        entity, err = await _resolve_or_error("unblock_user", chat_id, params)
        if err:
            return err
        await client(UnblockRequest(id=entity))
        log_operation_success("User unblocked", chat_id)
        return {"ok": True, "action": "unblocked", "chat": _chat_label(entity)}
    except Exception as e:
        return log_and_build_error(
            operation="unblock_user",
            error_message=f"Failed to unblock: {e!s}",
            params=params,
            exception=e,
        )


async def delete_messages_impl(
    chat_id: str, message_ids: list[int], revoke: bool = True
) -> dict[str, Any]:
    params = {"chat_id": chat_id, "message_ids": message_ids, "revoke": revoke}
    log_operation_start("Deleting messages", params)
    client = await get_connected_client()
    try:
        entity, err = await _resolve_or_error("delete_messages", chat_id, params)
        if err:
            return err
        await client.delete_messages(entity, message_ids, revoke=revoke)
        log_operation_success("Messages deleted", chat_id)
        return {
            "ok": True,
            "action": "deleted_messages",
            "count": len(message_ids),
            "revoke": revoke,
            "chat": _chat_label(entity),
        }
    except Exception as e:
        return log_and_build_error(
            operation="delete_messages",
            error_message=f"Failed to delete messages: {e!s}",
            params=params,
            exception=e,
        )


async def delete_chat_impl(chat_id: str, revoke: bool = False) -> dict[str, Any]:
    params = {"chat_id": chat_id, "revoke": revoke}
    log_operation_start("Deleting chat/dialog", params)
    client = await get_connected_client()
    try:
        entity, err = await _resolve_or_error("delete_chat", chat_id, params)
        if err:
            return err
        # delete_dialog removes the dialog (and leaves group/channel); revoke
        # only affects 1:1 user history.
        await client.delete_dialog(entity, revoke=revoke)
        log_operation_success("Chat deleted", chat_id)
        return {"ok": True, "action": "deleted_chat", "revoke": revoke, "chat": _chat_label(entity)}
    except Exception as e:
        return log_and_build_error(
            operation="delete_chat",
            error_message=f"Failed to delete chat: {e!s}",
            params=params,
            exception=e,
        )


async def leave_chat_impl(chat_id: str) -> dict[str, Any]:
    params = {"chat_id": chat_id}
    log_operation_start("Leaving chat", params)
    client = await get_connected_client()
    try:
        entity, err = await _resolve_or_error("leave_chat", chat_id, params)
        if err:
            return err
        if isinstance(entity, Channel):
            await client(LeaveChannelRequest(entity))
        else:
            await client.delete_dialog(entity)
        log_operation_success("Left chat", chat_id)
        return {"ok": True, "action": "left", "chat": _chat_label(entity)}
    except Exception as e:
        return log_and_build_error(
            operation="leave_chat",
            error_message=f"Failed to leave chat: {e!s}",
            params=params,
            exception=e,
        )


# ---------------------------------------------------------------------------
# Registration (called from server.py after register_tools(mcp))
# ---------------------------------------------------------------------------

def register_account_tools(mcp) -> None:
    # Imported here (not at module top) to avoid any import-time cycle with
    # tools_register, which is fully loaded by the time this runs.
    from src.server_components.tools_register import mcp_tool_with_restrictions

    @mcp.tool(
        description=_d("Block a user or bot (contacts.block) so they can no longer "
                       "message this account. Success: {ok, action, chat}."),
        annotations=ToolAnnotations(
            title="Block user", destructiveHint=True, idempotentHint=True, openWorldHint=True
        ),
    )
    @mcp_tool_with_restrictions("block_user")
    async def block_user(chat_id: ChatId) -> dict[str, Any]:
        """Block a user/bot."""
        return await block_user_impl(chat_id)

    @mcp.tool(
        description=_d("Unblock a previously blocked user or bot (contacts.unblock). "
                       "Success: {ok, action, chat}."),
        annotations=ToolAnnotations(
            title="Unblock user", destructiveHint=True, idempotentHint=True, openWorldHint=True
        ),
    )
    @mcp_tool_with_restrictions("unblock_user")
    async def unblock_user(chat_id: ChatId) -> dict[str, Any]:
        """Unblock a user/bot."""
        return await unblock_user_impl(chat_id)

    @mcp.tool(
        description=_d("Delete specific messages by id in a chat. revoke=true deletes for "
                       "everyone (your own messages). Success: {ok, action, count}."),
        annotations=ToolAnnotations(
            title="Delete messages", destructiveHint=True, idempotentHint=True, openWorldHint=True
        ),
    )
    @mcp_tool_with_restrictions("delete_messages")
    async def delete_messages(
        chat_id: ChatId, message_ids: list[int], revoke: bool = True
    ) -> dict[str, Any]:
        """Delete messages by id (revoke=true removes for everyone)."""
        return await delete_messages_impl(chat_id, message_ids, revoke)

    @mcp.tool(
        description=_d("Delete a whole dialog/conversation from this account (and leave it if a "
                       "group/channel). revoke=true also deletes 1:1 history for the other side. "
                       "Success: {ok, action}."),
        annotations=ToolAnnotations(
            title="Delete chat", destructiveHint=True, idempotentHint=True, openWorldHint=True
        ),
    )
    @mcp_tool_with_restrictions("delete_chat")
    async def delete_chat(chat_id: ChatId, revoke: bool = False) -> dict[str, Any]:
        """Delete a dialog (and leave group/channel)."""
        return await delete_chat_impl(chat_id, revoke)

    @mcp.tool(
        description=_d("Leave a group or channel. Success: {ok, action}."),
        annotations=ToolAnnotations(
            title="Leave chat", destructiveHint=True, idempotentHint=True, openWorldHint=True
        ),
    )
    @mcp_tool_with_restrictions("leave_chat")
    async def leave_chat(chat_id: ChatId) -> dict[str, Any]:
        """Leave a group/channel."""
        return await leave_chat_impl(chat_id)
