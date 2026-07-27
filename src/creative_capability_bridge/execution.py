"""Transactional, selective, and resumable plan execution."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from .coordinates import normalize_plan
from .inspection import inspect_document
from .receipts import file_hash
from .schema import Operation, Plan, PlanError
from .signing import canonical_bytes

STATE_VERSION = 1


class ExecutableAdapter(Protocol):
    executable: str | None

    def execute(self, plan: Plan, *, replace: bool = False) -> Path: ...

    def preview(self, plan: Plan) -> dict[str, Any]: ...

    def application_version(self) -> str | None: ...


@dataclass(frozen=True)
class ExecutionResult:
    output: Path
    backup: Path | None
    inspection: dict[str, Any]
    executed_plan: Plan
    completed: tuple[str, ...]
    state: Path | None = None


def operation_key(operation: Operation, index: int) -> str:
    return operation.identifier or f"op-{index}"


def select_operations(
    plan: Plan,
    *,
    only: set[str] | None = None,
    skip: set[str] | None = None,
    from_operation: str | None = None,
) -> tuple[tuple[Operation, ...], tuple[str, ...]]:
    entries = [
        (operation_key(operation, index), operation)
        for index, operation in enumerate(plan.operations, start=1)
    ]
    if from_operation:
        keys = [key for key, _ in entries]
        if from_operation not in keys:
            raise PlanError(f"Unknown --from operation: {from_operation}")
        entries = entries[keys.index(from_operation) :]
    selected: list[tuple[str, Operation]] = []
    for key, operation in entries:
        selectors = {key, *operation.tags}
        if only and selectors.isdisjoint(only):
            continue
        if skip and not selectors.isdisjoint(skip):
            continue
        selected.append((key, operation))
    if not selected:
        raise PlanError("Operation selection produced an empty plan.")
    return tuple(item for _, item in selected), tuple(key for key, _ in selected)


def execute_transactionally(
    plan: Plan,
    adapter: ExecutableAdapter,
    *,
    replace_output: bool = False,
    backup_path: Path | None = None,
    preserve_backup: bool = True,
) -> ExecutionResult:
    normalized = normalize_plan(plan)
    output = normalized.output_path
    if output.exists() and not replace_output:
        raise PlanError(f"Output already exists: {output}. Pass --replace to replace it.")
    output.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if output.exists() and preserve_backup:
        backup = (backup_path or _default_backup(output)).resolve()
        if backup.exists():
            raise PlanError(f"Rollback backup already exists: {backup}")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output, backup)

    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{output.stem}-ccb-", suffix=output.suffix, dir=output.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    temporary.unlink()
    staged_plan = replace(normalized, output_path=temporary)
    try:
        adapter.execute(staged_plan, replace=False)
        inspection = inspect_document(temporary, executable=adapter.executable)
        os.replace(temporary, output)
    except Exception:
        temporary.unlink(missing_ok=True)
        if backup and not output.exists():
            shutil.copy2(backup, output)
        raise
    keys = tuple(operation_key(item, index) for index, item in enumerate(plan.operations, start=1))
    return ExecutionResult(output, backup, inspection, normalized, keys)


def execute_checkpointed(
    plan: Plan,
    adapter: ExecutableAdapter,
    *,
    only: set[str] | None = None,
    skip: set[str] | None = None,
    from_operation: str | None = None,
    state_path: Path | None = None,
    resume: bool = False,
    replace_output: bool = False,
    backup_path: Path | None = None,
) -> ExecutionResult:
    normalized = normalize_plan(plan)
    operations, keys = select_operations(
        normalized, only=only, skip=skip, from_operation=from_operation
    )
    fingerprint = _fingerprint(plan)
    completed: list[str] = []
    state_target = state_path.resolve() if state_path else None
    if resume:
        if state_target is None:
            raise PlanError("--resume requires --state.")
        state = _load_state(state_target)
        if state.get("plan_sha256") != fingerprint:
            raise PlanError("Resume state belongs to a different plan.")
        if state.get("output") != str(plan.output_path):
            raise PlanError("Resume state points to a different output.")
        if file_hash(plan.output_path) != state.get("output_sha256"):
            raise PlanError("Resume output has changed since the last checkpoint.")
        completed = [str(item) for item in state.get("completed", [])]
    elif state_target and state_target.exists():
        raise PlanError(f"Execution state already exists: {state_target}")

    pending = [(key, item) for key, item in zip(keys, operations) if key not in completed]
    if not pending:
        inspection = inspect_document(plan.output_path, executable=adapter.executable)
        return ExecutionResult(
            plan.output_path,
            None,
            inspection,
            replace(normalized, operations=operations),
            keys,
            state_target,
        )

    original_output_existed = plan.output_path.exists()
    if original_output_existed and not (replace_output or resume):
        raise PlanError(f"Output already exists: {plan.output_path}. Pass --replace to replace it.")
    backup: Path | None = None
    last_inspection: dict[str, Any] = {}
    for position, (key, operation) in enumerate(pending):
        current_input = plan.output_path if plan.output_path.exists() else normalized.input_path
        step_plan = replace(
            normalized,
            input_path=current_input,
            output_path=plan.output_path,
            operations=(operation,),
            coordinate_space=None,
        )
        result = execute_transactionally(
            step_plan,
            adapter,
            replace_output=plan.output_path.exists(),
            backup_path=backup_path,
            preserve_backup=position == 0 and original_output_existed and not resume,
        )
        backup = result.backup or backup
        last_inspection = result.inspection
        completed.append(key)
        if state_target:
            _write_state(
                state_target,
                {
                    "state_version": STATE_VERSION,
                    "plan_sha256": fingerprint,
                    "output": str(plan.output_path),
                    "output_sha256": file_hash(plan.output_path),
                    "completed": completed,
                },
            )
    return ExecutionResult(
        plan.output_path,
        backup,
        last_inspection,
        replace(normalized, operations=operations),
        tuple(completed),
        state_target,
    )


def _default_backup(output: Path) -> Path:
    return output.with_name(f"{output.stem}.ccb-backup{output.suffix}")


def _fingerprint(plan: Plan) -> str:
    return hashlib.sha256(canonical_bytes(plan.as_dict())).hexdigest()


def _load_state(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"Could not read execution state: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("state_version") != STATE_VERSION:
        raise PlanError("Execution state version is not supported.")
    return payload


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
