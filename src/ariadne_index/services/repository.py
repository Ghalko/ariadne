from __future__ import annotations

import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from ariadne_index.config import get_settings
from ariadne_index.models.entities import Repo
from ariadne_index.schemas import RepoCreate
from ariadne_index.services.identity import repo_uuid


class RepoService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()

    def add_repo(self, payload: RepoCreate) -> Repo:
        repo = Repo(
            uuid=repo_uuid(payload.name),
            name=payload.name,
            local_path=str(Path(payload.local_path).expanduser().resolve()),
            default_branch=payload.default_branch,
            active_branch=payload.active_branch,
            current_commit_sha=payload.current_commit_sha,
            include_globs=payload.include_globs or self.settings.default_include_globs,
            exclude_globs=payload.exclude_globs or self.settings.default_exclude_globs,
        )
        self.refresh_repo_metadata(repo, overwrite=False)

        self.session.add(repo)
        self.session.flush()
        return repo

    def get_repo_by_name(self, name: str) -> Repo:
        repo = self.session.query(Repo).filter(Repo.name == name).one_or_none()
        if repo is None:
            raise ValueError(f"Unknown repo: {name}")
        return repo

    def list_repos(self) -> list[Repo]:
        return list(self.session.query(Repo).order_by(Repo.name))

    def refresh_repo_metadata(self, repo: Repo, *, overwrite: bool = True) -> Repo:
        if not Path(repo.local_path, ".git").exists():
            return repo

        default_branch = self._git_output(repo.local_path, "rev-parse", "--abbrev-ref", "HEAD")
        current_commit_sha = self._git_output(repo.local_path, "rev-parse", "HEAD")

        if overwrite or not repo.default_branch:
            repo.default_branch = default_branch
        if overwrite or not repo.active_branch:
            repo.active_branch = default_branch
        if overwrite or not repo.current_commit_sha:
            repo.current_commit_sha = current_commit_sha

        self.session.flush()
        return repo

    def _git_output(self, cwd: str, *args: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                check=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None
        return completed.stdout.strip() or None
