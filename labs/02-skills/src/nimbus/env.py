"""Environment, auth-mode and `.env` handling for this lab.

Two auth paths are supported and the labs pick one automatically:

  * **Vertex AI + ADC** - the DEFAULT. Needs `GOOGLE_CLOUD_PROJECT`,
    `GOOGLE_CLOUD_LOCATION` and Application Default Credentials.
  * **AI Studio API key** - the documented FALLBACK. Needs only
    `GOOGLE_API_KEY`, no project and no billing. It is enough for Lab 01.
    Labs 02-04 additionally use managed Google Cloud services (Skill
    Registry, Agent Registry, Agent Engine) that an API key cannot reach,
    so those labs still require a project.

There is deliberately NO default project. A workshop repo that silently
falls back to somebody else's project is worse than one that stops and
tells you what to export, so `require_project()` raises instead of
guessing.

Resolution is LAZY on purpose. The labs build `root_agent` at import
time and the offline test suites import them with no project set, so
the project is only demanded at the point of real cloud use. Nothing in
this module validates anything at import time.

This file is duplicated verbatim in every lab (`labs/*/src/nimbus/env.py`)
so each lab stands alone. Keep the copies in sync.
"""

from __future__ import annotations

import os
import sys

PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"
LOCATION_ENV = "GOOGLE_CLOUD_LOCATION"
API_KEY_ENV = "GOOGLE_API_KEY"
ENTERPRISE_ENV = "GOOGLE_GENAI_USE_ENTERPRISE"
LEGACY_ENTERPRISE_ENV = "GOOGLE_GENAI_USE_VERTEXAI"  # deprecated by google-genai
MODEL_ENV = "GEMINI_MODEL"

# GOOGLE_CLOUD_AGENT_ENGINE_LOCATION is a real Agent Platform / ADK variable,
# not something this repo invented: the vertexai AdkApp template and ADK's
# own telemetry and CLI read it. We reuse it rather than coining a new name.
RESOURCE_LOCATION_ENV = "GOOGLE_CLOUD_AGENT_ENGINE_LOCATION"

# Two different "locations", on purpose.
#
# GOOGLE_CLOUD_LOCATION is where the MODEL is served from. `global` is the
# most broadly available Gemini endpoint, so it is the default: it avoids
# the "publisher model not found in your region" 404 for most people.
DEFAULT_LOCATION = "global"
# GOOGLE_CLOUD_AGENT_ENGINE_LOCATION is where MANAGED RESOURCES live - Agent
# Engine / Agent Runtime, and the Skill and Agent registries that hang off
# the same regional Agent Platform endpoint. Those are regional and do NOT
# accept `global`. Labs 02-04 use it; Lab 01 never touches it.
DEFAULT_RESOURCE_LOCATION = "us-central1"

# Mirrors nimbus/agent/config.py. The default model is NOT guaranteed to
# exist in every project or every region - `GEMINI_MODEL` is the escape
# hatch. Probing for a working model is the prereq checker's job
# (`python check_prereqs.py --probe-models` at the repo root), never the
# agent's.
DEFAULT_MODEL = "gemini-flash-latest"

VERTEX = "vertex"
AI_STUDIO = "ai-studio"

CLOUD_SHELL_URL = (
    "https://shell.cloud.google.com/cloudshell/open"
    "?cloudshell_git_repo=https://github.com/zeroasterisk/ai4-gcp-agent-labs"
)

# `.env.example` ships placeholders like `your-project-id`. Now that `.env`
# is actually loaded, a copied-but-unedited file would otherwise sail past
# every check and fail deep inside a cloud call, so treat placeholders as
# unset and say so.
PLACEHOLDER_PREFIXES = ("your-", "your_", "<", "gs://your-")

MISSING_PROJECT_MESSAGE = (
    "{problem}\n"
    "\n"
    "This lab defaults to Vertex AI + Application Default Credentials.\n"
    "Set your project and region, then log in:\n"
    "\n"
    "    export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)\n"
    "    export GOOGLE_CLOUD_LOCATION=global\n"
    "    gcloud auth application-default login\n"
    "\n"
    "...or copy this lab's .env.example to .env and fill it in - the labs\n"
    "load .env automatically.\n"
    "\n"
    "No GCP project at all? Lab 01 also runs on an AI Studio API key:\n"
    "\n"
    "    export GOOGLE_API_KEY=your-api-key   # https://aistudio.google.com/apikey\n"
    "\n"
    "Run `python check_prereqs.py` from the repo root to check your setup."
)

NEEDS_PROJECT_MESSAGE = (
    "this lab needs a Google Cloud project.\n"
    "\n"
    "You are in AI Studio mode (GOOGLE_API_KEY is set). That is enough for\n"
    "Lab 01, but this lab uses managed Google Cloud services (Skill Registry,\n"
    "Agent Registry, Agent Engine) that an API key cannot reach.\n"
    "\n"
    "To run this lab:\n"
    "\n"
    "    export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)\n"
    "    export GOOGLE_CLOUD_LOCATION=global\n"
    "    export GOOGLE_GENAI_USE_ENTERPRISE=True\n"
    "    gcloud auth application-default login\n"
    "\n"
    "Or open the repo in Cloud Shell, which is already authenticated:\n"
    "\n"
    "    " + CLOUD_SHELL_URL + "\n"
    "\n"
    "No project? Lab 01 works on the API key alone:\n"
    "\n"
    "    cd labs/01-adk && python run_local.py"
)


class MissingProjectError(RuntimeError):
    """Raised when the lab needs a GCP project and none was supplied."""


def is_placeholder(value: str | None) -> bool:
    """Returns True when `value` is an unedited `.env.example` placeholder."""
    lowered = (value or "").strip().lower()
    return bool(lowered) and lowered.startswith(PLACEHOLDER_PREFIXES)


def _real(name: str) -> str | None:
    """Returns `os.environ[name]`, or None when empty or a placeholder."""
    value = os.environ.get(name, "").strip()
    if not value or is_placeholder(value):
        return None
    return value


def _project_problem() -> str:
    """Returns the first line of the missing-project message."""
    raw = os.environ.get(PROJECT_ENV, "").strip()
    if raw and is_placeholder(raw):
        return (
            "GOOGLE_CLOUD_PROJECT is still the .env.example placeholder "
            + repr(raw)
            + " - edit your .env."
        )
    return "GOOGLE_CLOUD_PROJECT is not set."


def missing_project_message() -> str:
    """Returns the actionable message for a missing/placeholder project."""
    return MISSING_PROJECT_MESSAGE.format(problem=_project_problem())


# ---------------------------------------------------------------------------
# .env loading (stdlib only - no python-dotenv dependency on purpose)
# ---------------------------------------------------------------------------


def parse_dotenv(text: str) -> dict[str, str]:
    """Parses `.env` text into a mapping.

    Understands `KEY=value`, `export KEY=value`, single- and double-quoted
    values, `#` comments (whole-line and trailing on unquoted values) and
    blank lines. Unparseable lines are ignored rather than fatal: a stray
    line in a config file should never stop a workshop.

    Args:
        text: The raw contents of a `.env` file.

    Returns:
        The parsed key/value pairs, in file order.
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key or not _is_identifier(key):
            continue
        values[key] = _parse_value(value.strip())
    return values


def _parse_value(value: str) -> str:
    """Unwraps one `.env` value: quotes, escapes and trailing comments.

    Args:
        value: The raw right-hand side of a `KEY=value` line.

    Returns:
        The cleaned value.
    """
    if value[:1] in ("'", '"'):
        quote = value[0]
        index = 1
        chunks: list[str] = []
        while index < len(value):
            char = value[index]
            if char == "\\" and quote == '"' and index + 1 < len(value):
                nxt = value[index + 1]
                chunks.append(
                    {"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt)
                )
                index += 2
                continue
            if char == quote:
                # Anything after the closing quote is a comment.
                return "".join(chunks)
            chunks.append(char)
            index += 1
        # Unterminated quote: take what we have rather than failing.
        return "".join(chunks)
    # Unquoted: a ` #` starts a trailing comment.
    hash_at = value.find(" #")
    if hash_at != -1:
        value = value[:hash_at]
    return value.strip()


def _is_identifier(key: str) -> bool:
    """Returns True when `key` looks like a shell/env variable name."""
    return key.replace("_", "a").isalnum() and not key[0].isdigit()


def repo_root(start: str | None = None) -> str | None:
    """Walks up from `start` looking for the repo root.

    Args:
        start: Directory (or file) to start from. Defaults to this file.

    Returns:
        The first ancestor holding a `.git` entry or a `labs/` directory,
        or None when there is no such ancestor.
    """
    here = os.path.abspath(start or __file__)
    if os.path.isfile(here):
        here = os.path.dirname(here)
    while True:
        if os.path.exists(os.path.join(here, ".git")) or os.path.isdir(
            os.path.join(here, "labs")
        ):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def lab_root() -> str:
    """Returns this lab's directory (the parent of `src/`)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def dotenv_candidates(start: str | None = None) -> list[str]:
    """Returns the `.env` paths to try, most specific first.

    Args:
        start: The entry point's file or directory. Defaults to this lab.

    Returns:
        Existing `.env` paths: the lab directory first, then the repo root.
    """
    here = os.path.abspath(start) if start else lab_root()
    if os.path.isfile(here):
        here = os.path.dirname(here)
    candidates = [here, lab_root()]
    root = repo_root(here)
    if root:
        candidates.append(root)
    seen: list[str] = []
    for directory in candidates:
        path = os.path.join(directory, ".env")
        if path not in seen and os.path.isfile(path):
            seen.append(path)
    return seen


def load_dotenv(start: str | None = None) -> list[str]:
    """Loads `.env` into `os.environ` without clobbering real env vars.

    Precedence, highest first: the real environment, then the lab's `.env`,
    then the repo root's `.env`. Nothing already set is ever overwritten,
    so `GOOGLE_CLOUD_PROJECT=x python run_local.py` always wins.

    Args:
        start: The entry point's file or directory. Defaults to this lab.

    Returns:
        The `.env` files that were read, in the order they were applied.
    """
    loaded: list[str] = []
    for path in dotenv_candidates(start):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            continue
        for key, value in parse_dotenv(text).items():
            if key not in os.environ:
                os.environ[key] = value
        loaded.append(path)
    return loaded


# ---------------------------------------------------------------------------
# Auth mode
# ---------------------------------------------------------------------------


def _truthy(value: str | None) -> bool:
    """Returns True for the usual truthy spellings."""
    return (value or "").strip().lower() in ("1", "true", "yes", "y", "on")


def api_key_or_none() -> str | None:
    """Returns `$GOOGLE_API_KEY`, or None when it is unset/empty."""
    return _real(API_KEY_ENV)


def enterprise_requested() -> bool:
    """Returns True when the user explicitly asked for enterprise/Vertex."""
    return _truthy(os.environ.get(ENTERPRISE_ENV)) or _truthy(
        os.environ.get(LEGACY_ENTERPRISE_ENV)
    )


def auth_mode() -> str:
    """Returns the active auth mode: `vertex` (default) or `ai-studio`.

    AI Studio wins only when `GOOGLE_API_KEY` is set AND the user has not
    asked for enterprise mode. Everything else - including a bare machine
    with nothing set - resolves to Vertex, which is the primary path.
    """
    if api_key_or_none() and not enterprise_requested():
        return AI_STUDIO
    return VERTEX


def apply_auth_env() -> str:
    """Normalizes `GOOGLE_GENAI_USE_ENTERPRISE` so ADK sees the same mode.

    ADK and google-genai read `GOOGLE_GENAI_USE_ENTERPRISE` (the deprecated
    `GOOGLE_GENAI_USE_VERTEXAI` is only a fallback) to decide between Vertex
    and the Gemini Developer API. Whichever mode we resolved, make it
    explicit rather than relying on library defaults.

    Returns:
        The active auth mode.
    """
    mode = auth_mode()
    os.environ[ENTERPRISE_ENV] = "True" if mode == VERTEX else "False"
    # Keep the deprecated twin consistent, but only if the user set it, so
    # google-genai does not warn about conflicting values.
    if LEGACY_ENTERPRISE_ENV in os.environ:
        os.environ[LEGACY_ENTERPRISE_ENV] = os.environ[ENTERPRISE_ENV]
    if mode == VERTEX:
        # Materialize the region so downstream clients and the printed
        # summary agree on it.
        os.environ[LOCATION_ENV] = location()
    return mode


def bootstrap(start: str | None = None) -> str:
    """Entry-point bootstrap: load `.env`, then settle the auth mode.

    Call this FIRST in an entry-point script, before importing the agent
    modules, because they read `GEMINI_MODEL` and friends at import time.

    Args:
        start: `__file__` of the entry point. Defaults to this lab.

    Returns:
        The active auth mode.
    """
    load_dotenv(start)
    return apply_auth_env()


# ---------------------------------------------------------------------------
# Project / location / model
# ---------------------------------------------------------------------------


def project_or_none() -> str | None:
    """Returns `$GOOGLE_CLOUD_PROJECT`, or None when it is unset/empty."""
    return _real(PROJECT_ENV)


def require_project() -> str:
    """Returns `$GOOGLE_CLOUD_PROJECT` or raises an actionable error.

    Returns:
        The project id the user exported.

    Raises:
        MissingProjectError: If `GOOGLE_CLOUD_PROJECT` is unset or empty.
    """
    project = project_or_none()
    if project is None:
        if auth_mode() == AI_STUDIO:
            raise MissingProjectError(
                NEEDS_PROJECT_MESSAGE[0].upper() + NEEDS_PROJECT_MESSAGE[1:]
            )
        raise MissingProjectError(missing_project_message())
    return project


def location() -> str:
    """Returns the MODEL location: `$GOOGLE_CLOUD_LOCATION` or `global`."""
    return _real(LOCATION_ENV) or DEFAULT_LOCATION


def resource_location() -> str:
    """Returns the location for managed Agent Platform resources.

    Agent Engine / Agent Runtime and the Skill and Agent registries are
    regional and do not accept `global`, so they cannot simply reuse
    `$GOOGLE_CLOUD_LOCATION` (which points at the model endpoint and
    defaults to `global`).

    The resolution order matches the Agent Platform SDK, so setting
    nothing new keeps working for anyone who already pins a region:

    1. `$GOOGLE_CLOUD_AGENT_ENGINE_LOCATION`, if set.
    2. `$GOOGLE_CLOUD_LOCATION`, unless it is `global`.
    3. `us-central1`.

    Returns:
        The region to use for managed Agent Platform resources.
    """
    explicit = _real(RESOURCE_LOCATION_ENV)
    if explicit:
        return explicit
    model_location = _real(LOCATION_ENV)
    if model_location and model_location.lower() != "global":
        return model_location
    return DEFAULT_RESOURCE_LOCATION


def model() -> str:
    """Returns `$GEMINI_MODEL`, defaulting to this lab's verified model."""
    return _real(MODEL_ENV) or DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Preflight for entry-point scripts
# ---------------------------------------------------------------------------


def describe_auth() -> str:
    """Returns a one-line summary of the active auth mode."""
    if auth_mode() == AI_STUDIO:
        return (
            "Auth: AI Studio API key (GOOGLE_API_KEY) - no GCP project needed "
            "- model=" + model()
        )
    return (
        "Auth: Vertex AI + ADC (the default) - project="
        + (project_or_none() or "<unset>")
        + ", location="
        + location()
        + " (model), "
        + resource_location()
        + " (resources), model="
        + model()
    )


def check_auth_or_exit(needs_project: bool = False) -> str:
    """Preflight for entry-point scripts. Prints the active auth mode.

    Prints guidance and exits non-zero rather than letting a traceback (or a
    confusing cloud 403) reach the user.

    Args:
        needs_project: True for labs that use managed Google Cloud services
            (Skill Registry, Agent Registry, Agent Engine) and therefore
            cannot run on an AI Studio API key alone.

    Returns:
        The active auth mode.
    """
    mode = apply_auth_env()
    if mode == AI_STUDIO:
        if needs_project:
            print(f"ERROR: {NEEDS_PROJECT_MESSAGE}", file=sys.stderr)
            raise SystemExit(1)
        print(describe_auth())
        return mode
    try:
        require_project()
    except MissingProjectError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        raise SystemExit(1) from None
    os.environ[LOCATION_ENV] = location()
    print(describe_auth())
    return mode


def check_project_or_exit() -> str:
    """Back-compat preflight: demands a project regardless of auth mode.

    Prefer `check_auth_or_exit(needs_project=...)`, which does not ask an
    AI Studio user for a project they do not need.

    Returns:
        The project id the user exported.
    """
    check_auth_or_exit(needs_project=True)
    return require_project()
