"""Only resources relevant to the selected surface are advertised."""
import asyncio
from src.effects.artifact_text import artifact_text_impl
from src.models import EventPage, Run


def register(mcp, deps):
    if "workbench_status" in deps.selected:
        @mcp.resource("workbench://policy", mime_type="application/json", description="Current local policy; configuration is not authorization for a new action.")
        def policy() -> dict:
            return deps.policy.snapshot().model_dump()

        @mcp.resource("workbench://tools", mime_type="application/json", description="Exactly the registered tools, safety classes and hints.")
        def tools() -> dict:
            return {"profile": deps.config.profile, "tools": deps.tool_catalogue()}

    if "job_read" in deps.selected:
        @mcp.resource("workbench://jobs/{id}/events{?cursor,limit}", mime_type="application/json",
                      description="Append-only events, at most 100 per page; continue with next_cursor.")
        def job_events(id: str, cursor: int = 0, limit: int = 50) -> dict:
            return deps.registry.events(id, cursor=cursor, limit=limit).model_dump()

        @mcp.resource("workbench://runs/{id}", mime_type="application/json", description="One owned run manifest; no raw files or save data.")
        def run(id: str) -> dict:
            return deps.registry.get_run(id).model_dump(by_alias=True)

        @mcp.resource("workbench://artifacts/{id}{?cursor,limit}", mime_type="application/json",
                      description="Read complete registered JSON/plain/CSV text (8 MiB maximum), redacted and revision-pinned. limit is 1–32768 characters; follow next_cursor. Never binary/save contents.")
        async def artifact_text(id: str, cursor: str | None = None, limit: int = 8192) -> dict:
            return await asyncio.to_thread(artifact_text_impl, deps, id, cursor, limit)
