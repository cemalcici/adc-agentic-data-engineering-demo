"""What the agent may touch, and the only way it touches it.

The model is never asked which file to change — the target comes from the build
output, which names it. So this check no longer guards against a model naming
something it should not; it guards the agent's own path handling, which is where
a mistake would now have to originate, and which is worth guarding precisely
because it now looks safe.

Every write into the transformation project goes through `write_model` here.
Keeping the check and the write in one module is what makes "the agent writes
only inside the model directory" answerable by reading one file, rather than by
finding every place that opens one.

See adr/0023-the-agent-chooses-contents-never-targets.md
See adr/0003-enforce-the-transformation-write-scope-by-withholding-the-mount.md
"""

from __future__ import annotations

import pathlib

MODEL_DIRECTORY = "models"


class TargetOutsideModelDirectory(Exception):
    """A path that resolved somewhere the agent has no business being."""


def resolve_target(project_dir: str, relative_path: str) -> pathlib.Path:
    """Resolve a target inside the transformation project, or refuse.

    Resolution follows symbolic links and collapses traversal before the check,
    so `models/../../etc/passwd.sql` and a link pointing out of the project are
    both refused by the same comparison. Nothing is read here: the refusal
    happens before anything opens the path.
    """
    root = (pathlib.Path(project_dir) / MODEL_DIRECTORY).resolve()
    target = (pathlib.Path(project_dir) / relative_path).resolve()

    if target == root or root not in target.parents:
        raise TargetOutsideModelDirectory(
            f"{relative_path!r} resolves to {target}, which is not a file under {root}"
        )
    if target.suffix != ".sql":
        raise TargetOutsideModelDirectory(
            f"{relative_path!r} is not a transformation; only .sql files are in scope"
        )
    return target


def write_model(project_dir: str, relative_path: str, contents: str) -> pathlib.Path:
    """Write a transformation, having first refused anything out of scope.

    The only write into the transformation project. Writing the same contents
    twice leaves the same result, which is what makes a restart between writing
    and re-triggering safe without a check for whether the write already
    happened.
    """
    target = resolve_target(project_dir, relative_path)
    target.write_text(contents)
    return target
