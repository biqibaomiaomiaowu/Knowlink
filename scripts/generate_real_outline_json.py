from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import server.infra.db.models  # noqa: F401
from scripts.demo_assets_smoke import check_assets, load_manifest, repo_root
from server.domain.services import HandoutService
from server.infra.db.base import Base
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository
from server.tasks.parse_pipeline import run_parse_pipeline


DEFAULT_OUTPUT_PATH = Path("/tmp/knowlink-real-outline.json")
DEFAULT_MANIFEST_PATH = Path("server/seeds/demo_assets_manifest.json")


class OutlineGenerationBlocked(RuntimeError):
    pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate latest handout outline JSON from real fixed demo assets.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args(argv)

    root = repo_root()
    _load_env_file(args.env_file if args.env_file.is_absolute() else root / args.env_file)
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    asset_result = load_manifest(manifest_path, root=root)
    if asset_result.manifest is None:
        raise OutlineGenerationBlocked("demo asset manifest is missing or invalid")
    asset_errors = [diag for diag in (*asset_result.diagnostics, *check_assets(asset_result.manifest)) if diag.level == "error"]
    if asset_errors:
        raise OutlineGenerationBlocked("; ".join(diag.code for diag in asset_errors))

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    session = session_factory()
    try:
        repo = SqlAlchemyRuntimeRepository(session)
        course = repo.create_course(
            title=asset_result.manifest.manual_import_course_title or "KnowLink 固定联调课",
            entry_type="manual_import",
            goal_text="验证真实固定资料集的讲义 outline read model。",
            preferred_style="balanced",
        )
        course_id = int(course["courseId"])
        for index, asset in enumerate(asset_result.manifest.assets, start=1):
            path = (asset_result.manifest.local_base_dir / asset.relative_path).resolve()
            repo.create_resource(
                course_id,
                {
                    "resourceType": asset.resource_type,
                    "objectKey": str(path),
                    "originalName": asset.original_name,
                    "mimeType": asset.mime_type,
                    "sizeBytes": asset.size_bytes,
                    "checksum": asset.checksum,
                    "sortOrder": index,
                },
            )

        parse_run, trigger = repo.create_parse_run(course_id)
        parse_result = run_parse_pipeline(
            {
                "taskId": trigger["taskId"],
                "courseId": course_id,
                "parseRunId": parse_run["parseRunId"],
            },
            session_factory=lambda: session,
            base_dir=root,
        )
        video_segments = [
            segment
            for segment in repo.list_course_segments(course_id=course_id, parse_run_id=parse_run["parseRunId"])
            if segment.get("segmentType") == "video_caption"
        ]
        if not video_segments:
            issues = parse_result.get("issues") or []
            raise OutlineGenerationBlocked(
                "real video_caption segments were not produced; "
                f"parse status={parse_result.get('status')}; issues={json.dumps(issues, ensure_ascii=False)}"
            )

        HandoutService(courses=repo, handouts=repo, idempotency=repo).generate_handout(
            course_id=course_id,
            idempotency_key=None,
        )
        outline = repo.get_latest_outline(course_id)
        if outline is None:
            raise OutlineGenerationBlocked("latest outline read model was not produced")
        latest_handout = repo.get_latest_handout(course_id) or {}
        outline_meta = latest_handout.get("metaJson") if isinstance(latest_handout, dict) else {}
        if not isinstance(outline_meta, dict):
            outline_meta = {}

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(outline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sections = outline.get("items") if isinstance(outline.get("items"), list) else []
        child_item_count = sum(
            len(section.get("children") or [])
            for section in sections
            if isinstance(section, dict)
        )
        print(
            json.dumps(
                {
                    "status": "ok",
                    "output": str(args.output),
                    "courseId": course_id,
                    "parseRunId": parse_run["parseRunId"],
                    "handoutVersionId": outline.get("handoutVersionId"),
                    "sectionCount": len(sections),
                    "childItemCount": child_item_count,
                    "videoSegmentCount": len(video_segments),
                    "outlineUsedFallback": bool(outline_meta.get("outlineUsedFallback")),
                    "outlineIssues": outline_meta.get("outlineIssues") or [],
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        session.close()
        engine.dispose()


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


if __name__ == "__main__":
    raise SystemExit(main())
