from __future__ import annotations

from pathlib import Path
import re

from sqlalchemy.orm import Session

from ariadne_index.models.entities import FileRecord, Repo, SymbolRecord
from ariadne_index.models.enums import EdgeType
from ariadne_index.parsers.registry import ParserRegistry
from ariadne_index.services.embeddings import EmbeddingProvider
from ariadne_index.services.filesystem import discover_files, sha256_text
from ariadne_index.services.graph import GraphService
from ariadne_index.services.storage import upsert_embedding


class IndexingService:
    def __init__(self, session: Session, embedder: EmbeddingProvider) -> None:
        self.session = session
        self.embedder = embedder
        self.parsers = ParserRegistry()
        self.graph = GraphService(session)

    def index_repo(self, repo: Repo) -> dict:
        root = Path(repo.local_path)
        files = discover_files(root, repo.include_globs, repo.exclude_globs)
        indexed = 0
        skipped = 0

        for path in files:
            relative_path = path.relative_to(root).as_posix()
            content = path.read_text(encoding="utf-8", errors="ignore")
            checksum = sha256_text(content)
            existing = (
                self.session.query(FileRecord)
                .filter(FileRecord.repo_id == repo.id, FileRecord.path == relative_path)
                .one_or_none()
            )
            if existing is not None and existing.checksum == checksum:
                skipped += 1
                continue

            parsed = self.parsers.parse(path, content)
            file_record = self._upsert_file(repo, relative_path, checksum, parsed, content=content)
            self._replace_symbols(repo, file_record, parsed)
            upsert_embedding(
                self.session,
                repo_id=repo.id,
                node_kind="file",
                node_id=file_record.id,
                embedding_role="summary",
                content=file_record.summary or relative_path,
                embedder=self.embedder,
            )
            indexed += 1

        for file_record in self.session.query(FileRecord).filter(FileRecord.repo_id == repo.id):
            self._sync_import_edges(repo, file_record)
        self._sync_test_edges(repo)
        self._sync_doc_edges(repo)
        self._sync_config_edges(repo)

        return {"repo": repo.name, "indexed": indexed, "skipped": skipped, "discovered": len(files)}

    def _upsert_file(self, repo: Repo, relative_path: str, checksum: str, parsed, *, content: str) -> FileRecord:
        file_record = (
            self.session.query(FileRecord)
            .filter(FileRecord.repo_id == repo.id, FileRecord.path == relative_path)
            .one_or_none()
        )
        if file_record is None:
            file_record = FileRecord(repo_id=repo.id, path=relative_path, checksum=checksum)
            self.session.add(file_record)

        file_record.language = parsed.language
        file_record.checksum = checksum
        file_record.commit_sha = repo.current_commit_sha
        file_record.summary = parsed.summary
        file_record.imports = parsed.imports
        file_record.tags = parsed.tags
        metadata = {"parser": parsed.language.value}
        if parsed.language.value in {"markdown", "json", "yaml", "toml"}:
            metadata["content_excerpt"] = content[:4000]
        file_record.metadata_json = metadata
        self.session.flush()
        return file_record

    def _replace_symbols(self, repo: Repo, file_record: FileRecord, parsed) -> None:
        self.session.query(SymbolRecord).filter(SymbolRecord.file_id == file_record.id).delete()

        symbols_by_name: dict[str, SymbolRecord] = {}
        for parsed_symbol in parsed.symbols:
            symbol = SymbolRecord(
                repo_id=repo.id,
                file_id=file_record.id,
                name=parsed_symbol.name,
                qualified_name=parsed_symbol.qualified_name or parsed_symbol.name,
                symbol_type=parsed_symbol.symbol_type,
                language=parsed.language,
                line_start=parsed_symbol.line_start,
                line_end=parsed_symbol.line_end,
                signature=parsed_symbol.signature,
                docstring=parsed_symbol.docstring,
                summary=parsed_symbol.summary,
                metadata_json={},
            )
            self.session.add(symbol)
            self.session.flush()
            symbols_by_name[symbol.name] = symbol

            self.graph.add_edge(
                repo_id=repo.id,
                from_node_kind="file",
                from_node_id=file_record.id,
                to_node_kind="symbol",
                to_node_id=symbol.id,
                edge_type=EdgeType.file_contains_symbol,
            )
            upsert_embedding(
                self.session,
                repo_id=repo.id,
                node_kind="symbol",
                node_id=symbol.id,
                embedding_role="summary",
                content=symbol.summary or symbol.signature or symbol.name,
                embedder=self.embedder,
            )

        for symbol in self.session.query(SymbolRecord).filter(SymbolRecord.file_id == file_record.id):
            if "." in (symbol.qualified_name or ""):
                parent_name = symbol.qualified_name.rsplit(".", 1)[0]
                parent = symbols_by_name.get(parent_name)
                if parent is not None:
                    symbol.parent_symbol_id = parent.id

        self._sync_import_edges(repo, file_record)

    def _sync_import_edges(self, repo: Repo, file_record: FileRecord) -> None:
        from ariadne_index.models.entities import Edge

        self.session.query(Edge).filter(
            Edge.repo_id == repo.id,
            Edge.from_node_kind == "file",
            Edge.from_node_id == file_record.id,
            Edge.edge_type == EdgeType.file_imports_file,
        ).delete()

        import_targets = {
            target.path.removesuffix(".py").replace("/", "."): target
            for target in self.session.query(FileRecord).filter(FileRecord.repo_id == repo.id)
        }
        for imported in file_record.imports:
            target = import_targets.get(imported)
            if target is None:
                continue
            self.graph.add_edge(
                repo_id=repo.id,
                from_node_kind="file",
                from_node_id=file_record.id,
                to_node_kind="file",
                to_node_id=target.id,
                edge_type=EdgeType.file_imports_file,
            )

    def _sync_test_edges(self, repo: Repo) -> None:
        from ariadne_index.models.entities import Edge

        self.session.query(Edge).filter(
            Edge.repo_id == repo.id,
            Edge.edge_type == EdgeType.test_covers_symbol,
        ).delete()

        files = list(self.session.query(FileRecord).filter(FileRecord.repo_id == repo.id))
        module_to_file = {file.path.removesuffix(".py").replace("/", "."): file for file in files}
        symbols_by_file_id: dict[int, list[SymbolRecord]] = {}
        for symbol in self.session.query(SymbolRecord).filter(SymbolRecord.repo_id == repo.id):
            symbols_by_file_id.setdefault(symbol.file_id, []).append(symbol)

        for test_file in files:
            is_test = "test" in test_file.tags or test_file.path.startswith("tests/") or "/test" in test_file.path
            if not is_test:
                continue
            covered_files = {
                module_to_file[imported]
                for imported in test_file.imports
                if imported in module_to_file
            }
            for covered_file in covered_files:
                for symbol in symbols_by_file_id.get(covered_file.id, []):
                    self.graph.add_edge(
                        repo_id=repo.id,
                        from_node_kind="file",
                        from_node_id=test_file.id,
                        to_node_kind="symbol",
                        to_node_id=symbol.id,
                        edge_type=EdgeType.test_covers_symbol,
                        metadata_json={"covered_file": covered_file.path},
                    )

    def _sync_doc_edges(self, repo: Repo) -> None:
        from ariadne_index.models.entities import Edge

        self.session.query(Edge).filter(
            Edge.repo_id == repo.id,
            Edge.edge_type == EdgeType.doc_describes_symbol,
        ).delete()

        files = list(self.session.query(FileRecord).filter(FileRecord.repo_id == repo.id))
        docs = [
            file
            for file in files
            if file.language.value == "markdown" or file.path.startswith("docs/")
        ]
        symbols = list(self.session.query(SymbolRecord).filter(SymbolRecord.repo_id == repo.id))
        files_by_id = {file.id: file for file in files}

        for doc in docs:
            text = f"{doc.path} {doc.summary or ''} {doc.metadata_json.get('content_excerpt', '')}".lower()
            doc_terms = set(term for term in re.split(r"\W+", text) if len(term) >= 4)
            for symbol in symbols:
                symbol_terms = {
                    term
                    for term in re.split(r"[_\W]+", f"{symbol.name} {symbol.qualified_name or ''}")
                    if len(term) >= 4
                }
                file_record = files_by_id.get(symbol.file_id)
                if file_record is None:
                    continue
                file_terms = {
                    term
                    for term in re.split(r"[\/_.\W]+", file_record.path)
                    if len(term) >= 4
                }

                if not symbol_terms.intersection(doc_terms) and not file_terms.intersection(doc_terms):
                    continue

                self.graph.add_edge(
                    repo_id=repo.id,
                    from_node_kind="file",
                    from_node_id=doc.id,
                    to_node_kind="symbol",
                    to_node_id=symbol.id,
                    edge_type=EdgeType.doc_describes_symbol,
                    metadata_json={"doc_path": doc.path, "file_path": file_record.path},
                    weight=0.8,
                )

    def _sync_config_edges(self, repo: Repo) -> None:
        from ariadne_index.models.entities import Edge

        self.session.query(Edge).filter(
            Edge.repo_id == repo.id,
            Edge.edge_type == EdgeType.config_affects_file,
        ).delete()

        files = list(self.session.query(FileRecord).filter(FileRecord.repo_id == repo.id))
        config_files = [file for file in files if self._is_config_file(file)]
        code_files = [file for file in files if self._is_code_file(file)]
        symbols_by_file_id: dict[int, list[SymbolRecord]] = {}
        for symbol in self.session.query(SymbolRecord).filter(SymbolRecord.repo_id == repo.id):
            symbols_by_file_id.setdefault(symbol.file_id, []).append(symbol)

        stopwords = {
            "config",
            "configs",
            "document",
            "settings",
            "default",
            "value",
            "values",
            "enabled",
            "workspace",
        }

        for config_file in config_files:
            excerpt = (config_file.metadata_json or {}).get("content_excerpt", "")
            config_text = f"{config_file.path} {config_file.summary or ''} {excerpt}".lower()
            config_terms = {
                term
                for term in re.split(r"[^\w]+", config_text)
                if len(term) >= 4 and term not in stopwords
            }
            if not config_terms:
                continue

            for code_file in code_files:
                symbols = symbols_by_file_id.get(code_file.id, [])
                haystack = " ".join(
                    filter(
                        None,
                        [
                            code_file.path.lower(),
                            (code_file.summary or "").lower(),
                            " ".join(imported.lower() for imported in code_file.imports),
                            " ".join(symbol.name.lower() for symbol in symbols),
                            " ".join((symbol.summary or "").lower() for symbol in symbols),
                        ],
                    )
                )
                overlap = sorted(term for term in config_terms if term in haystack)
                module_hints = {
                    code_file.path.removesuffix(".py").replace("/", ".").lower(),
                    code_file.path.removesuffix(".ts").replace("/", ".").lower(),
                    code_file.path.removesuffix(".js").replace("/", ".").lower(),
                }
                has_module_hint = any(hint and hint in config_text for hint in module_hints)
                if len(overlap) < 2 and not has_module_hint:
                    continue

                self.graph.add_edge(
                    repo_id=repo.id,
                    from_node_kind="file",
                    from_node_id=config_file.id,
                    to_node_kind="file",
                    to_node_id=code_file.id,
                    edge_type=EdgeType.config_affects_file,
                    metadata_json={
                        "config_path": config_file.path,
                        "file_path": code_file.path,
                        "matched_terms": overlap[:6],
                    },
                    weight=1.0 + min(len(overlap), 4) * 0.1 + (0.2 if has_module_hint else 0.0),
                )

    def _is_config_file(self, file_record: FileRecord) -> bool:
        return file_record.path.startswith("config/") or file_record.language.value in {"toml", "yaml", "json"}

    def _is_code_file(self, file_record: FileRecord) -> bool:
        return file_record.language.value in {"python", "typescript", "javascript"}
