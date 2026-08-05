#!/usr/bin/env python3
"""Pre-flight check for the AI4 GCP Agent Labs.

Run this BEFORE the workshop starts:

    python check_prereqs.py            # check everything, including one real
                                       # ~5-token model call
    python check_prereqs.py --lab 01   # only Lab 01's dependencies
    python check_prereqs.py --offline  # skip the live model call (and PyPI)
    python check_prereqs.py --setup    # guided, interactive setup: does the
                                       # tedious gcloud steps for you, in the
                                       # right order, asking first, then checks

Standard library only, so it runs on macOS, Linux, WSL, Git Bash, PowerShell
and Cloud Shell with nothing installed but Python itself. If you do not have
Python 3.10+, install it first.

Exit code is 0 when every REQUIRED check passed, 1 otherwise.
"""

# NOTE: keep this file boring. It must parse on old interpreters so the
# version check below can print something friendlier than a SyntaxError.

import os
import sys
import time

MIN_PYTHON = (3, 10)

if sys.version_info < MIN_PYTHON:
    sys.stderr.write(
        "FAIL: Python %d.%d.%d is too old. These labs need Python 3.10 or newer.\n"
        % sys.version_info[:3]
    )
    sys.stderr.write("      you ran: %s\n" % sys.executable)
    sys.stderr.write(
        "      fix: install Python 3.10+ (https://www.python.org/downloads/), or\n"
        "           use Google Cloud Shell, which already has it:\n"
        "           https://shell.cloud.google.com/cloudshell/open"
        "?cloudshell_git_repo=https://github.com/zeroasterisk/ai4-gcp-agent-labs\n"
    )
    raise SystemExit(1)

import argparse  # noqa: E402
import importlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
LABS_DIR = os.path.join(REPO_ROOT, "labs")

CLOUD_SHELL_URL = (
    "https://shell.cloud.google.com/cloudshell/open"
    "?cloudshell_git_repo=https://github.com/zeroasterisk/ai4-gcp-agent-labs"
)

# Import name -> the requirements.txt entry it comes from. Mirrors the
# preflight in each lab's test.sh.
LAB_REQUIREMENTS = {
    "01-adk": {
        "google.adk": "google-adk",
        "vertexai": "google-cloud-aiplatform",
        "mcp": "mcp",
        "pydantic": "pydantic",
        "pytest": "pytest",
    },
    "02-skills": {
        "google.adk": "google-adk",
        "google.adk.tools.skill_toolset": "google-adk",
        "vertexai": "google-cloud-aiplatform",
        "agentplatform": "google-cloud-aiplatform",
        "mcp": "mcp",
        "pydantic": "pydantic",
        "pytest": "pytest",
    },
    "03-mcp-servers": {
        "google.adk": "google-adk",
        "google.adk.tools.skill_toolset": "google-adk",
        "vertexai": "google-cloud-aiplatform",
        "agentplatform": "google-cloud-aiplatform",
        "mcp": "mcp",
        "pydantic": "pydantic",
        "starlette": "starlette",
        "uvicorn": "uvicorn",
        "pytest": "pytest",
    },
    "04-deployments": {
        "google.adk": "google-adk",
        "google.adk.tools.skill_toolset": "google-adk",
        "vertexai.agent_engines": "google-cloud-aiplatform",
        "agentplatform": "google-cloud-aiplatform",
        "mcp": "mcp",
        "starlette": "starlette",
        "uvicorn": "uvicorn",
        "cloudpickle": "cloudpickle",
        "pytest": "pytest",
    },
}
LAB_ORDER = ["01-adk", "02-skills", "03-mcp-servers", "04-deployments"]

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"

failures = []
warnings_seen = []


def repo_revision():
    """Returns the short commit this checkout is on, or None outside git.

    Printed in the header so a stale clone is obvious: a fix you already
    pushed is worthless if the person in front of you never pulled it.
    """
    try:
        out = subprocess.run(["git", "-C", REPO_ROOT, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
    except Exception:  # noqa: BLE001 - no git, not a checkout, whatever
        return None
    rev = out.stdout.strip()
    return rev if out.returncode == 0 and rev else None


def report(status, title, detail=None, fix=None, required=True):
    """Prints one check result and records failures.

    Args:
        status: PASS, FAIL, WARN or SKIP.
        title: One-line description of the check.
        detail: Optional extra context, printed indented.
        fix: Optional copy-pasteable remedy, printed on FAIL/WARN.
        required: When False, a FAIL does not affect the exit code.
    """
    print("[%s] %s" % (status.ljust(4), title))
    for line in (detail or "").splitlines():
        print("       %s" % line)
    if status in (FAIL, WARN) and fix:
        print("       fix:")
        for line in fix.splitlines():
            print("         %s" % line)
    if status == FAIL and required:
        failures.append(title)
    if status == WARN:
        warnings_seen.append(title)


def section(name):
    """Prints a section separator."""
    print("")
    print("-- %s" % name)


# ---------------------------------------------------------------------------
# 0. Shared helpers
# ---------------------------------------------------------------------------


def load_lab_env(lab):
    """Imports a lab's `nimbus.env` so we agree on .env and auth resolution.

    Args:
        lab: Lab directory name, or None to use Lab 01 (always present).

    Returns:
        The imported module, or None when it cannot be loaded.
    """
    lab = lab or "01-adk"
    src = os.path.join(LABS_DIR, lab, "src")
    if not os.path.isdir(src):
        return None
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        spec = importlib.util.spec_from_file_location(
            "_nimbus_env_for_prereqs", os.path.join(src, "nimbus", "env.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:  # pragma: no cover - defensive
        return None


def detect_lab(explicit):
    """Resolves which lab(s) to check.

    Args:
        explicit: The `--lab` value, e.g. `01`, `01-adk`, `all` or None.

    Returns:
        A list of lab directory names.
    """
    if explicit:
        value = explicit.strip().lower()
        if value == "all":
            return list(LAB_ORDER)
        for name in LAB_ORDER:
            if value == name or name.startswith(value + "-") or value == name[:2]:
                return [name]
        raise SystemExit(
            "unknown --lab %r. Pick one of: %s, all" % (explicit, ", ".join(LAB_ORDER))
        )
    cwd = os.path.abspath(os.getcwd())
    for name in LAB_ORDER:
        lab_dir = os.path.join(LABS_DIR, name)
        if cwd == lab_dir or cwd.startswith(lab_dir + os.sep):
            return [name]
    return list(LAB_ORDER)


def in_cloud_shell():
    """True when we are running inside Google Cloud Shell.

    Cloud Shell is worth special-casing: it is already authenticated, and
    telling someone there to run `gcloud auth application-default login`
    sends them down a browser-popup rabbit hole they do not need.
    """
    for name in ("GOOGLE_CLOUD_SHELL", "CLOUD_SHELL", "DEVSHELL_PROJECT_ID"):
        if os.environ.get(name, "").strip():
            return True
    return False


def gcloud_config_dir():
    """Returns the gcloud config directory, honouring CLOUDSDK_CONFIG.

    Cloud Shell and some corporate images relocate this away from
    ~/.config/gcloud, which is why hard-coding the home-directory path
    reports "no credentials" on a machine that is perfectly authenticated.
    """
    explicit = os.environ.get("CLOUDSDK_CONFIG", "").strip()
    if explicit:
        return explicit
    if os.name == "nt":
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                            "gcloud")
    return os.path.expanduser("~/.config/gcloud")


def adc_path():
    """Returns the Application Default Credentials FILE path, if one exists.

    Returns None when ADC is served by the metadata server instead of a file
    (Cloud Shell, GCE, Cloud Run) - that is not an error, see detect_adc().
    """
    explicit = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if explicit and os.path.isfile(explicit):
        return explicit
    candidate = os.path.join(gcloud_config_dir(),
                             "application_default_credentials.json")
    return candidate if os.path.isfile(candidate) else None


def metadata_service_account():
    """Asks the GCE/Cloud Shell metadata server who we are, briefly.

    Returns:
        The service-account email string, or None. Never raises, and never
        blocks for more than a couple of seconds.
    """
    host = os.environ.get("GCE_METADATA_HOST", "").strip() or "169.254.169.254"
    url = ("http://%s/computeMetadata/v1/instance/service-accounts/default/email"
           % host)
    request = urllib.request.Request(url,
                                     headers={"Metadata-Flavor": "Google"})
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.read().decode("utf-8", "replace").strip() or None
    except Exception:  # noqa: BLE001 - not on GCE, or no metadata server
        return None


def detect_adc():
    """Finds Application Default Credentials, however they are provided.

    ADC is not always a file. On Cloud Shell, GCE, Cloud Run and Agent Engine
    it comes from the metadata server, and on relocated gcloud installs the
    file is not under ~/.config. Checking only the home-directory path is how
    a fully-authenticated Cloud Shell gets told it has no credentials.

    Returns:
        A (source, detail) tuple, where source is "file", "ambient" or None.
    """
    path = adc_path()
    if path:
        return "file", path

    # google.auth is installed with the labs' requirements. Import it lazily
    # so this script still runs, and still explains itself, on a machine with
    # nothing installed - the stdlib-only promise holds for the failure path.
    try:
        import google.auth  # noqa: PLC0415 - deliberate lazy import

        credentials, _ = google.auth.default()
        name = type(credentials).__name__
        email = getattr(credentials, "service_account_email", None)
        detail = "resolved by google.auth (%s)" % name
        if email:
            detail += "\nservice account: %s" % email
        return "ambient", detail
    except Exception:  # noqa: BLE001 - not installed, or genuinely no ADC
        pass

    if in_cloud_shell() or os.environ.get("GCE_METADATA_HOST", "").strip():
        email = metadata_service_account()
        if email:
            return "ambient", "metadata server (%s)" % email
    return None, None


def adc_quota_project():
    """Returns the quota project baked into the ADC file, if any.

    ADC records the project your API calls are BILLED and QUOTA'd against.
    It is set at `gcloud auth application-default login` time from whatever
    `gcloud config get-value project` said then - which is exactly why the
    project has to be set BEFORE that login. Change the project afterwards
    and GOOGLE_CLOUD_PROJECT and the ADC quota project quietly disagree,
    which shows up as a 403, or as usage billed to the wrong project.
    """
    path = adc_path()
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle).get("quota_project_id") or ""
            return value.strip() or None
    except Exception:  # noqa: BLE001 - unreadable, or not JSON
        return None


def check_adc_quota_project(project):
    """Warns when ADC's quota project disagrees with GOOGLE_CLOUD_PROJECT."""
    quota = adc_quota_project()
    if not project or not quota or quota == project:
        return
    report(
        WARN,
        "ADC quota project (%s) is not GOOGLE_CLOUD_PROJECT (%s)"
        % (quota, project),
        "Your credentials bill and quota against %s, but the labs are\n"
        "pointed at %s. This usually means the project was set AFTER\n"
        "`gcloud auth application-default login`, not before. It shows up\n"
        "as a 403, or as usage landing on the wrong project."
        % (quota, project),
        "gcloud auth application-default set-quota-project %s\n"
        "(or let the script do it: python check_prereqs.py --setup)" % project,
    )


# ---------------------------------------------------------------------------
# 1-2. Interpreter
# ---------------------------------------------------------------------------


def check_python():
    """Reports the interpreter version and path."""
    report(
        PASS,
        "Python %d.%d.%d (>= 3.10 required)" % sys.version_info[:3],
        "executable: %s\nplatform:   %s" % (sys.executable, platform.platform()),
    )


def check_virtualenv():
    """Warns (never fails) when not running inside a virtualenv."""
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    conda = os.environ.get("CONDA_DEFAULT_ENV")
    if in_venv:
        report(PASS, "Virtualenv active", "prefix: %s" % sys.prefix)
    elif conda:
        report(WARN, "Conda env %r active, not a venv" % conda,
               "Conda usually works, but the labs are only tested on venv.")
    else:
        report(
            WARN,
            "Not running inside a virtualenv",
            "Installing into the system Python often fails or breaks other tools.",
            "uv venv .venv\n"
            "source .venv/bin/activate        # Windows: .venv\\Scripts\\Activate.ps1",
        )


# ---------------------------------------------------------------------------
# 3. Dependencies
# ---------------------------------------------------------------------------


def check_dependencies(labs):
    """Checks that each selected lab's imports resolve.

    Args:
        labs: Lab directory names to check.

    Returns:
        True when every selected lab's imports resolved.
    """
    all_ok = True
    for lab in labs:
        missing = []
        for module, dist in sorted(LAB_REQUIREMENTS[lab].items()):
            try:
                found = importlib.util.find_spec(module) is not None
            except Exception:
                found = False
            if not found:
                missing.append((module, dist))
        if missing:
            names = ", ".join(sorted({dist for _, dist in missing}))
            report(
                FAIL,
                "Lab %s dependencies" % lab,
                "missing: %s\n(from: %s)"
                % (", ".join(module for module, _ in missing), names),
                "cd labs/%s\n"
                "uv venv .venv\n"
                "source .venv/bin/activate        # Windows: .venv\\Scripts\\Activate.ps1\n"
                "uv pip install -r requirements.txt" % lab,
            )
        else:
            report(PASS, "Lab %s dependencies importable" % lab)
            continue
        all_ok = False


    return all_ok


# ---------------------------------------------------------------------------
# 4. Network
# ---------------------------------------------------------------------------



def check_pip_index():
    """Warns when installs are pointed at a private mirror lacking these packages.

    Reaching pypi.org is not enough: a corporate proxy (Artifact Registry,
    Artifactory, Nexus) configured as the default index makes the install fail
    with "No matching distribution found" - or a 401 - even though the network
    is fine. On managed machines this usually comes from a SYSTEM-level file
    (/etc/pip.conf, /etc/uv/uv.toml), which beats anything a project can set,
    so only an environment variable or a CLI flag overrides it.
    """
    index = ""
    source = ""
    for name in ("UV_DEFAULT_INDEX", "UV_INDEX_URL", "PIP_INDEX_URL"):
        value = os.environ.get(name, "").strip()
        if value:
            index, source = value, name
            break
    if not index:
        try:
            out = subprocess.run(
                [sys.executable, "-m", "pip", "config", "get", "global.index-url"],
                capture_output=True, text=True, timeout=15)
            if out.returncode == 0 and out.stdout.strip():
                index = out.stdout.strip()
                source = "pip config (global.index-url)"
        except Exception:
            pass
    if not index or "pypi.org" in index:
        report(PASS, "package index is the public PyPI",
               ("%s = %s" % (source, index)) if source
               else "default (https://pypi.org/simple)")
        return
    system_files = [path for path in ("/etc/pip.conf", "/etc/uv/uv.toml")
                    if os.path.exists(path)]
    detail = ("%s = %s\nThis mirror may not carry google-adk; installs then fail with\n"
              "'Could not find a version that satisfies the requirement ... "
              "(from versions: none)',\nor a 401 from the private index."
              % (source, index))
    if system_files:
        detail += ("\nLikely source on this machine: %s\n"
                   "System-level config beats any project-level config, so only an\n"
                   "environment variable or a CLI flag overrides it."
                   % ", ".join(system_files))
    else:
        detail += ("\nUsual sources are /etc/pip.conf and /etc/uv/uv.toml. System-level\n"
                   "config beats any project-level config, so only an environment\n"
                   "variable or a CLI flag overrides it.")
    report(WARN, "installs are pointed at a private index", detail,
           "Set the public index for your whole shell:\n"
           "    export UV_DEFAULT_INDEX=https://pypi.org/simple\n"
           "    # PowerShell: $env:UV_DEFAULT_INDEX=\"https://pypi.org/simple\"\n"
           "or per command:\n"
           "    uv pip install --default-index https://pypi.org/simple -r requirements.txt")


def check_pypi(offline, deps_ok=False):
    """Checks that PyPI is reachable (conference wifi / corporate proxy).

    Reachability only matters if you still need to INSTALL something. When every
    lab's dependencies already import, a blocked PyPI is downgraded to a warning
    so a corporate proxy cannot fail a machine that is, in fact, ready to go.

    Args:
        offline: Skip the network entirely.
        deps_ok: True when all selected labs' dependencies already import.
    """
    if offline:
        report(SKIP, "PyPI reachable (--offline)")
        return
    url = "https://pypi.org/simple/pip/"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ai4-labs-check"})
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read(64)
        report(PASS, "PyPI reachable", "GET %s" % url)
        return
    except urllib.error.HTTPError as err:
        report(WARN, "PyPI returned HTTP %s" % err.code,
               "Probably fine for installs that are already done.")
        return
    except Exception as err:
        text = str(err)
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if "CERTIFICATE_VERIFY_FAILED" in text or "SSLError" in type(err).__name__:
            detail = ("%s: %s\n"
                      "This is a TLS-inspecting corporate proxy, not a dead network."
                      % (type(err).__name__, err))
            fix = ("Point Python at your corporate CA bundle:\n"
                   "    export SSL_CERT_FILE=/path/to/corp-ca.pem\n"
                   "    export REQUESTS_CA_BUNDLE=/path/to/corp-ca.pem\n"
                   "or install with uv's TLS escape hatch:\n"
                   "    uv pip install \\\n"
                   "        --allow-insecure-host pypi.org \\\n"
                   "        --allow-insecure-host files.pythonhosted.org \\\n"
                   "        -r requirements.txt")
        else:
            detail = "%s: %s\nHTTPS_PROXY=%s" % (type(err).__name__, err, proxy or "<unset>")
            fix = ("Check wifi / VPN. Behind a corporate proxy:\n"
                   "    export HTTPS_PROXY=http://your-proxy:port")
        if deps_ok:
            report(WARN, "PyPI unreachable (but everything is already installed)",
                   detail + "\nNot a blocker: every lab's dependencies import fine. "
                            "This only matters if you need to install something else.",
                   fix, required=False)
        else:
            report(FAIL, "PyPI unreachable", detail,
                   fix + "\nAlready installed everything? Re-run with --offline.")


# ---------------------------------------------------------------------------
# 5-6. Auth
# ---------------------------------------------------------------------------


def check_auth(env):
    """Reports which auth mode is active and whether it is usable.

    Args:
        env: The lab's `nimbus.env` module, or None.

    Returns:
        The active mode string, `vertex` or `ai-studio`.
    """
    mode = env.auth_mode() if env else (
        "ai-studio" if os.environ.get("GOOGLE_API_KEY", "").strip() else "vertex"
    )
    adc_source, adc_detail = detect_adc()
    api_key = (env.api_key_or_none() if env else os.environ.get("GOOGLE_API_KEY")) or ""

    if mode == "ai-studio":
        report(
            PASS,
            "Auth mode: AI Studio API key (GOOGLE_API_KEY)",
            "key ends with ...%s\nThis is the fallback path. Lab 01 only - Labs "
            "02-04 need a GCP project." % api_key[-4:],
        )
        return mode

    if adc_source == "file":
        report(
            PASS,
            "Auth mode: Vertex AI + Application Default Credentials (the default)",
            "ADC: %s" % adc_detail,
        )
    elif adc_source == "ambient":
        where = "Cloud Shell" if in_cloud_shell() else "this VM"
        report(
            PASS,
            "Auth mode: Vertex AI + Application Default Credentials (the default)",
            "ADC is provided by the environment - %s is already authenticated,\n"
            "so there is no credentials file and nothing to log in to.\n"
            "%s" % (where, adc_detail),
        )
    else:
        report(
            FAIL,
            "Auth mode: Vertex AI (the default), but no credentials found",
            "No Application Default Credentials and no GOOGLE_API_KEY.",
            "Let the script do it for you:\n"
            "     python check_prereqs.py --setup\n"
            "   or pick ONE by hand:\n"
            "  A) Cloud Shell (nothing to install, already authenticated):\n"
            "     %s\n"
            "  B) Local + GCP project, in this order:\n"
            "     export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID\n"
            "     gcloud auth login --update-adc\n"
            '     gcloud config set project "$GOOGLE_CLOUD_PROJECT"\n'
            '     gcloud auth application-default set-quota-project "$GOOGLE_CLOUD_PROJECT"\n'
            "  C) No GCP project at all (Lab 01 only):\n"
            "     get a key at https://aistudio.google.com/apikey then\n"
            "     export GOOGLE_API_KEY=your-api-key" % CLOUD_SHELL_URL,
        )
    return mode


def check_project(env, mode):
    """Checks project/location, which are only required in Vertex mode."""
    project = env.project_or_none() if env else (
        os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip() or None
    )
    location = env.location() if env else (
        os.environ.get("GOOGLE_CLOUD_LOCATION", "").strip() or "global"
    )
    if env and hasattr(env, "resource_location"):
        resource_location = env.resource_location()
        resource_explicit = bool(
            os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION", "").strip())
    else:
        resource_location = (
            os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION", "").strip()
            or (location if location != "global" else "us-central1"))
        resource_explicit = bool(
            os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION", "").strip())
    if mode == "ai-studio":
        report(SKIP, "GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION",
               "Not needed in AI Studio mode.")
        return
    if project:
        report(PASS, "GOOGLE_CLOUD_PROJECT=%s" % project,
               "GOOGLE_CLOUD_LOCATION=%s%s   (model endpoint)\n"
               "GOOGLE_CLOUD_AGENT_ENGINE_LOCATION=%s%s   (Agent Engine + "
               "Skill/Agent Registry - labs 02-04)"
               % (location,
                  "  (default)" if not os.environ.get("GOOGLE_CLOUD_LOCATION") else "",
                  resource_location,
                  "" if resource_explicit else "  (derived)"))
        check_adc_quota_project(project)
        return
    raw = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    detail = "GOOGLE_CLOUD_PROJECT is not set."
    if raw:
        detail = (
            "GOOGLE_CLOUD_PROJECT is still the .env.example placeholder %r - "
            "edit your .env." % raw
        )
    report(
        FAIL,
        "GOOGLE_CLOUD_PROJECT is not usable",
        detail,
        "export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)\n"
        "export GOOGLE_CLOUD_LOCATION=global\n"
        "(no gcloud? type the real project id literally. Or copy a lab's\n"
        " .env.example to .env and fill it in - .env is loaded automatically)",
    )


# ---------------------------------------------------------------------------
# 7. The check that actually proves something
# ---------------------------------------------------------------------------


def diagnose_live_error(err, mode, model, project, location):
    """Turns a model-call exception into a specific, actionable diagnosis.

    Args:
        err: The exception raised by the live call.
        mode: `vertex` or `ai-studio`.
        model: The model id that was tried.
        project: The GCP project, or None.
        location: The GCP region.

    Returns:
        A `(headline, fix)` tuple.
    """
    text = ("%s: %s" % (type(err).__name__, err)).lower()

    if "defaultcredentialserror" in text or "could not automatically determine" in text:
        return (
            "no Application Default Credentials",
            "gcloud auth application-default login\n"
            "(or use Cloud Shell: %s)" % CLOUD_SHELL_URL,
        )
    if (
        "refresherror" in text
        or "metadata.google.internal" in text
        or "invalid_grant" in text
        or "reauth" in text
        or "token has been expired or revoked" in text
    ):
        return (
            "credentials were found but could not be refreshed",
            "gcloud auth application-default login\n"
            "(on a VM with no service-account scopes this always fails - use\n"
            " Cloud Shell instead: %s)" % CLOUD_SHELL_URL,
        )
    if "api key not valid" in text or "api_key_invalid" in text:
        return (
            "the GOOGLE_API_KEY was rejected",
            "Get a fresh key at https://aistudio.google.com/apikey and\n"
            "export GOOGLE_API_KEY=your-api-key",
        )
    if "billing" in text:
        return (
            "billing is not enabled on the project",
            "Enable billing:\n"
            "  https://console.cloud.google.com/billing/linkedaccount?project=%s"
            % (project or "your-project-id"),
        )
    if "serviceusage" in text or "has not been used in project" in text or (
        "service_disabled" in text
    ):
        return (
            "the Vertex AI API is not enabled on this project",
            "gcloud services enable aiplatform.googleapis.com --project %s"
            % (project or "your-project-id"),
        )
    if "orgpolicy" in text or "org policy" in text or "constraints/" in text:
        return (
            "an organization policy is blocking this call",
            "Ask your GCP admin, or use a personal project / an AI Studio key:\n"
            "  export GOOGLE_API_KEY=your-api-key  # https://aistudio.google.com/apikey",
        )
    if "permission" in text or "403" in text or "denied" in text:
        return (
            "permission denied on the project",
            "You need roles/aiplatform.user on %s:\n"
            "  gcloud projects add-iam-policy-binding %s \\\n"
            "    --member=user:$(gcloud config get-value account) \\\n"
            "    --role=roles/aiplatform.user"
            % (project or "your-project-id", project or "your-project-id"),
        )
    if "404" in text or "not found" in text or "was not found" in text:
        return (
            "model %r is not available%s"
            % (model, " in %s" % location if mode == "vertex" else ""),
            (("This is a REGIONAL endpoint (%s). The global endpoint serves\n"
              "the widest set of models - try it first:\n"
              "  export GOOGLE_CLOUD_LOCATION=global\n" % location)
             if mode == "vertex" and location != "global" else "")
            + "Find one that works for you:\n"
              "  python check_prereqs.py --probe-models\n"
              "  export GEMINI_MODEL=<the model it reports>\n"
              "List them: gcloud ai models list --region=%s" % location,
        )
    if "429" in text or "quota" in text or "resource_exhausted" in text:
        return (
            "quota exhausted / rate limited",
            "Wait a minute and retry, or use a different project or region.",
        )
    if (
        "getaddrinfo" in text
        or "timed out" in text
        or "connection" in text
        or "ssl" in text
        or "proxy" in text
    ):
        return (
            "could not reach the API over the network",
            "Check wifi / VPN / corporate proxy:\n"
            "  export HTTPS_PROXY=http://your-proxy:port\n"
            "Then re-run. To skip this check: python check_prereqs.py --offline",
        )
    return (
        "the model call failed",
        "Raw error:\n  %s: %s\n"
        "If this is a region or model problem, try:\n"
        "  python check_prereqs.py --probe-models" % (type(err).__name__, err),
    )


# Probed newest-first by --probe-models. No single model is available in every
# project and region - gemini-3.5-flash works on AI Studio but is NOT available
# on Vertex in every region, which is why assuming a single hard-pinned default
# is unsafe. The `-latest` aliases come first because they are the most broadly
# resolvable, and `gemini-flash-latest` is the repo-wide default.
MODEL_CANDIDATES = (
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.1-flash",
    "gemini-3-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
)


def _say_ok(client, model):
    """Makes one tiny generate_content call. Raises on failure."""
    client.models.generate_content(
        model=model,
        contents="Reply with the single word: ok",
        config={"max_output_tokens": 8, "temperature": 0},
    )


def _say_ok_retry_once(client, model, pause=2.0):
    """Same, but retries once after a short pause.

    A single cold call can fail transiently (a 503, a slow first token, a
    connection reset behind a corporate proxy). Reporting FAIL on that is
    worse than useless the morning of a workshop: it sends people chasing
    an auth problem they do not have. One retry removes almost all of it.

    Raises:
        The exception from the SECOND attempt, if both fail.
    """
    try:
        _say_ok(client, model)
        return
    except Exception:  # noqa: BLE001 - first attempt may fail transiently
        time.sleep(pause)
    _say_ok(client, model)


def _model_client(mode, env, project, location):
    """Builds a genai client for the active auth mode."""
    from google import genai  # noqa: PLC0415
    if mode == "vertex":
        return genai.Client(vertexai=True, project=project, location=location)
    return genai.Client(api_key=(env.api_key_or_none() if env
                                 else os.environ["GOOGLE_API_KEY"]))


def probe_models(env, mode, model_override):
    """Tries every candidate model and reports which ones actually work.

    Answers the question the failure message can only guess at: given THIS
    project, region and auth mode, which model should I export?
    """
    project = env.project_or_none() if env else os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = env.location() if env else (
        os.environ.get("GOOGLE_CLOUD_LOCATION") or "global")
    where = ("vertex %s/%s" % (project, location)) if mode == "vertex" else "ai studio"
    print("\n-- probing models (%s)" % where)
    try:
        client = _model_client(mode, env, project, location)
    except Exception as err:  # noqa: BLE001
        report(FAIL, "Could not create a client to probe with", str(err))
        return
    working = []
    order = ([model_override] if model_override else []) + [
        m for m in MODEL_CANDIDATES if m != model_override]
    for name in order:
        try:
            # Retry once: a transient 503 must not blacklist a good model.
            _say_ok_retry_once(client, name, pause=1.0)
        except Exception as err:  # noqa: BLE001
            short = str(err).split("\n")[0][:110]
            print("  [--] %-24s %s" % (name, short))
            continue
        print("  [OK] %-24s available" % name)
        working.append(name)
    print()
    if working:
        report(PASS, "%d of %d candidate models work here" % (len(working), len(order)),
               ", ".join(working),
               "Use the first one:\n    export GEMINI_MODEL=%s" % working[0])
    else:
        report(FAIL, "No candidate model worked",
               "Auth is fine but no model answered in %s." % where,
               ("Try the global endpoint first - it serves the widest set of\n"
                "models:\n"
                "    export GOOGLE_CLOUD_LOCATION=global\n"
                "Then check the Vertex AI API is enabled and billing is active:\n"
                "    gcloud services enable aiplatform.googleapis.com\n"
                if mode == "vertex" and location != "global" else
                "Check the Vertex AI API is enabled and billing is active:\n"
                "    gcloud services enable aiplatform.googleapis.com\n"
                "then try a region, e.g. GOOGLE_CLOUD_LOCATION=us-central1\n"))


def check_live_model(env, mode, offline, model_override):
    """Makes ONE real ~5-token model call. The only check that proves anything.

    Args:
        env: The lab's `nimbus.env` module, or None.
        mode: `vertex` or `ai-studio`.
        offline: Skip the call when True.
        model_override: `--model` value, if given.
    """
    model = model_override or (env.model() if env else
                               os.environ.get("GEMINI_MODEL") or "gemini-flash-latest")
    project = env.project_or_none() if env else os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = env.location() if env else (
        os.environ.get("GOOGLE_CLOUD_LOCATION") or "global")

    if offline:
        report(SKIP, "Live model call (--offline / --skip-live)",
               "This is the ONLY check that proves billing, API enablement,\n"
               "model availability and org policy. Run it before the workshop.")
        return

    try:
        from google import genai  # noqa: PLC0415 - deliberately not top-level
    except Exception:
        report(
            FAIL,
            "Live model call: google-genai is not installed",
            "Install a lab's requirements first, then re-run.",
            "cd labs/01-adk && uv pip install -r requirements.txt",
        )
        return

    if mode == "vertex" and not project:
        report(FAIL, "Live model call skipped: no project in Vertex mode",
               "Fix GOOGLE_CLOUD_PROJECT above, then re-run.",
               "export GOOGLE_CLOUD_PROJECT=your-project-id")
        return
    if mode == "ai-studio" and not (env.api_key_or_none() if env
                                    else os.environ.get("GOOGLE_API_KEY")):
        report(FAIL, "Live model call skipped: no GOOGLE_API_KEY",
               "", "export GOOGLE_API_KEY=your-api-key")
        return

    try:
        if mode == "vertex":
            client = genai.Client(vertexai=True, project=project, location=location)
            where = "vertex %s/%s" % (project, location)
        else:
            client = genai.Client(
                api_key=(env.api_key_or_none() if env
                         else os.environ["GOOGLE_API_KEY"]))
            where = "ai studio"
        _say_ok_retry_once(client, model)
    except Exception as err:  # noqa: BLE001 - we diagnose, not re-raise
        headline, fix = diagnose_live_error(err, mode, model, project, location)
        report(FAIL, "Live model call FAILED - %s" % headline,
               "model: %s" % model,
               fix + "\n\nNot sure which model to pick? Let it find one for you:\n"
                     "    python check_prereqs.py --probe-models")
        return
    report(PASS, "Live model call succeeded", "model: %s (%s)" % (model, where))


# ---------------------------------------------------------------------------
# 8. Optional tooling
# ---------------------------------------------------------------------------


def check_tooling():
    """Checks uv (required), then reports gcloud presence (optional)."""
    uv_path = shutil.which("uv")
    if uv_path:
        report(PASS, "uv found (required)", uv_path)
    else:
        report(
            FAIL,
            "uv not found (required)",
            "Every environment and install instruction in these labs uses uv:\n"
            "    uv venv .venv\n"
            "    source .venv/bin/activate\n"
            "    uv pip install -r requirements.txt",
            "curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            "# Windows PowerShell:\n"
            "#   powershell -ExecutionPolicy ByPass -c "
            "\"irm https://astral.sh/uv/install.ps1 | iex\"\n"
            "# docs: https://docs.astral.sh/uv/getting-started/installation/\n"
            "# no suitable Python? uv installs one:  uv python install 3.12",
            required=True,
        )
    for tool, why in (
        ("gcloud", "only needed for Labs 03/04 and for `gcloud auth "
                   "application-default login`"),
    ):
        path = shutil.which(tool)
        if path:
            report(PASS, "%s found" % tool, path)
        else:
            report(SKIP, "%s not found - optional" % tool, why, required=False)


# ---------------------------------------------------------------------------
# 9. Guided setup - only ever reached via --setup
#
# Everything below this line is opt-in. Without --setup this script stays what
# it has always been: a read-only diagnosis that changes nothing.
# ---------------------------------------------------------------------------

VERTEX_API = "aiplatform.googleapis.com"
AI_STUDIO_KEY_URL = "https://aistudio.google.com/apikey"
GCLOUD_INSTALL_URL = "https://cloud.google.com/sdk/docs/install"


def setup_step(number, title):
    """Prints a numbered guided-setup step header."""
    print("")
    print("== step %s - %s" % (number, title))


def setup_say(text):
    """Prints indented prose inside a guided-setup step."""
    for line in text.splitlines():
        print("   %s" % line)


def setup_show(cmd):
    """Prints the exact command we are about to run."""
    print("")
    print("   $ %s" % " ".join(cmd))
    print("")


def ask_yes_no(question, assume_yes, default=True, runs_command=True):
    """Asks a yes/no question. Default is yes unless told otherwise.

    Args:
        question: The prompt, without the [Y/n] suffix.
        assume_yes: When True, answer yes without prompting (--yes).
        default: The answer used for a bare Enter.
        runs_command: True when saying yes will execute something. Those
            questions answer NO on a non-interactive stdin, so a pipe or a
            CI job can never run a command by accident. Questions that only
            choose a branch fall back to `default` instead.

    Returns:
        True for yes.
    """
    suffix = "[Y/n]" if default else "[y/N]"
    if assume_yes:
        print("   %s %s yes (--yes)" % (question, suffix))
        return True
    if not sys.stdin.isatty():
        if runs_command:
            print("   %s %s no (stdin is not a terminal; use --yes to run "
                  "unattended)" % (question, suffix))
            return False
        print("   %s %s %s (stdin is not a terminal, taking the default)"
              % (question, suffix, "yes" if default else "no"))
        return default
    try:
        answer = input("   %s %s " % (question, suffix)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("")
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def ask_text(question, assume_yes=False):
    """Asks for a line of text. Returns an empty string when unavailable."""
    if assume_yes and not sys.stdin.isatty():
        return ""
    if not sys.stdin.isatty():
        print("   %s (stdin is not a terminal - skipping)" % question)
        return ""
    try:
        return input("   %s " % question).strip()
    except (EOFError, KeyboardInterrupt):
        print("")
        return ""


def run_step_command(cmd, interactive=False, timeout=300):
    """Runs one setup command.

    Args:
        cmd: Command as a list of arguments.
        interactive: When True the child keeps the terminal, so browser
            prompts and URLs from `gcloud auth login` are visible.
        timeout: Seconds before giving up (ignored when interactive).

    Returns:
        A (returncode, output) tuple. `output` is "" for interactive runs.
    """
    try:
        if interactive:
            completed = subprocess.run(cmd)
            return completed.returncode, ""
        completed = subprocess.run(cmd, capture_output=True, text=True,
                                   timeout=timeout)
        output = (completed.stdout or "") + (completed.stderr or "")
        for line in output.strip().splitlines():
            print("   | %s" % line)
        return completed.returncode, output
    except FileNotFoundError:
        return 127, "command not found: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, "timed out after %ss" % timeout
    except KeyboardInterrupt:
        print("")
        return 130, "interrupted"


def gcloud_value(*args):
    """Runs a read-only gcloud command quietly. Returns its stdout, stripped."""
    try:
        completed = subprocess.run(["gcloud"] + list(args),
                                   capture_output=True, text=True, timeout=60)
    except Exception:  # noqa: BLE001 - gcloud missing, slow or broken
        return ""
    if completed.returncode != 0:
        return ""
    return (completed.stdout or "").strip()


def setup_gcloud_present():
    """Step a. Confirms gcloud is installed. Returns True when it is."""
    setup_step("a", "is the gcloud CLI installed?")
    path = shutil.which("gcloud")
    if path:
        report(PASS, "gcloud found", path)
        return True
    report(
        FAIL,
        "gcloud is not on PATH",
        "Guided setup drives gcloud, so it cannot continue without it.",
        "Install it: %s\n"
        "Then re-run: python check_prereqs.py --setup\n"
        "No time for an install? Use an AI Studio API key instead (Lab 01\n"
        "works fully on it): %s" % (GCLOUD_INSTALL_URL, AI_STUDIO_KEY_URL),
        required=False,
    )
    return False


def setup_account(assume_yes):
    """Step b. Signs gcloud in and writes ADC in the same browser popup.

    `gcloud auth login --update-adc` does both logins at once: it signs in
    the gcloud command AND writes Application Default Credentials for your
    Python code. That is one browser round-trip instead of two. It runs
    before the project is set, so the ADC quota project is realigned
    explicitly in step d.

    Returns:
        True when there is an active account afterwards.
    """
    setup_step("b", "sign in to gcloud (and write ADC in the same popup)")
    active = gcloud_value("auth", "list", "--filter=status:ACTIVE",
                          "--format=value(account)")
    adc_source, adc_detail = detect_adc()

    if adc_source == "ambient":
        where = "Cloud Shell" if in_cloud_shell() else "this VM"
        report(PASS, "%s is already authenticated - no login needed" % where,
               adc_detail)
        return True
    if active and adc_source == "file":
        report(PASS, "active gcloud account: %s" % active.splitlines()[0],
               "ADC already present: %s" % adc_detail)
        return True

    setup_say(
        "This opens ONE browser popup that does two things: it signs in the\n"
        "gcloud command itself, and --update-adc writes the Application\n"
        "Default Credentials your Python code uses. Skipping the ADC half is\n"
        "the single most common failure.")
    cmd = ["gcloud", "auth", "login", "--update-adc"]
    setup_show(cmd)
    if not ask_yes_no("Run it?", assume_yes):
        report(SKIP, "gcloud auth login --update-adc skipped", required=False)
        return False
    code, _ = run_step_command(cmd, interactive=True)
    active = gcloud_value("auth", "list", "--filter=status:ACTIVE",
                          "--format=value(account)")
    if code == 0 and active:
        report(PASS, "signed in as %s" % active.splitlines()[0],
               "ADC: %s" % (adc_path() or "written by --update-adc"))
        return True
    report(FAIL, "still no active account after gcloud auth login --update-adc",
           "exit code %d" % code,
           "Try again, or use a personal Google account - corporate accounts\n"
           "sometimes block the browser login with an org policy.",
           required=False)
    return False


def setup_project(assume_yes):
    """Step c. Resolves and sets the active project. Returns its id or None."""
    setup_step("c", "which Google Cloud project?")
    current = gcloud_value("config", "get-value", "project")
    if current in ("", "(unset)", "None"):
        current = None
    if current:
        setup_say("gcloud is currently pointed at: %s" % current)
        if ask_yes_no("Use this project?", assume_yes, runs_command=False):
            report(PASS, "project: %s" % current)
            return current
    else:
        setup_say("gcloud has no project configured.")
    if ask_yes_no("List the projects you can see?", assume_yes, default=True):
        listing = ["gcloud", "projects", "list", "--limit=50"]
        setup_show(listing)
        run_step_command(listing)
    project = ask_text("Project ID (the id, not the display name):",
                       assume_yes)
    if not project:
        report(
            SKIP,
            "no project chosen",
            "Labs 02-04 need one. Lab 01 also runs on an AI Studio key:\n"
            "  %s" % AI_STUDIO_KEY_URL,
            required=False,
        )
        return None
    cmd = ["gcloud", "config", "set", "project", project]
    setup_say("gcloud ignores GOOGLE_CLOUD_PROJECT - it reads\n"
              "CLOUDSDK_CORE_PROJECT - so it needs this explicitly. Step d\n"
              "then points the ADC quota project at the same project.")
    setup_show(cmd)
    if not ask_yes_no("Run it?", assume_yes):
        report(SKIP, "project not set", required=False)
        return None
    code, _ = run_step_command(cmd)
    confirmed = gcloud_value("config", "get-value", "project")
    if code == 0 and confirmed == project:
        report(PASS, "project set to %s" % confirmed)
        return confirmed
    report(FAIL, "could not set the project",
           "gcloud still reports %r" % (confirmed or "(unset)"),
           "Check the id with: gcloud projects list", required=False)
    return None


def setup_billing(project):
    """Detect-only billing report. Never tries to change billing.

    Linking a billing account is an account-level action with real money
    attached; a setup script has no business doing it, and in a workshop the
    instructor usually hands out credits anyway. So we look, and we tell you
    what we saw.
    """
    setup_step("e", "is billing linked to the project? (read-only)")
    if not project:
        report(SKIP, "no project to check", required=False)
        return
    enabled = gcloud_value("billing", "projects", "describe", project,
                           "--format=value(billingEnabled)")
    if enabled.lower() == "true":
        report(PASS, "billing is linked to %s" % project)
        return
    if enabled.lower() == "false":
        report(
            FAIL,
            "billing is NOT linked to %s" % project,
            "Vertex AI will not serve a model to a project with no billing\n"
            "account, even when you have free credits sitting there. This is\n"
            "the single most common blocker.",
            "Link one:\n"
            "  https://console.cloud.google.com/billing/linkedaccount?project=%s\n"
            "At a workshop: ask the instructor for the credits/coupon first.\n"
            "No billing at all? Lab 01 runs on an AI Studio key: %s"
            % (project, AI_STUDIO_KEY_URL),
            required=False,
        )
        return
    report(
        SKIP,
        "could not read the billing status of %s" % project,
        "That needs the Cloud Billing API and billing.resourceAssociations.list,\n"
        "which plenty of accounts do not have. Not a problem by itself - the\n"
        "live model call at the end is the real test.",
        required=False,
    )


def setup_enable_api(project, assume_yes):
    """Step f. Enables the Vertex AI API on the project."""
    setup_step("f", "enable the Vertex AI API")
    if not project:
        report(SKIP, "no project, nothing to enable", required=False)
        return False
    enabled = gcloud_value("services", "list", "--enabled",
                           "--filter=config.name:%s" % VERTEX_API,
                           "--format=value(config.name)",
                           "--project", project)
    if VERTEX_API in enabled:
        report(PASS, "%s is already enabled on %s" % (VERTEX_API, project))
        return True
    setup_say(
        "This can take a minute or two, and the very first model call right\n"
        "afterwards can still return 403 while it propagates. That is normal -\n"
        "wait a moment and re-run the checks.\n"
        "Enabling it creates nothing billable on its own.")
    cmd = ["gcloud", "services", "enable", VERTEX_API, "--project", project]
    setup_show(cmd)
    if not ask_yes_no("Run it?", assume_yes):
        report(SKIP, "%s not enabled" % VERTEX_API, required=False)
        return False
    code, output = run_step_command(cmd, timeout=600)
    if code == 0:
        report(PASS, "%s enabled on %s" % (VERTEX_API, project))
        return True
    if "PERMISSION_DENIED" in output or "denied" in output.lower():
        report(
            FAIL,
            "not allowed to enable %s on %s" % (VERTEX_API, project),
            "Enabling an API needs the serviceusage.services.enable\n"
            "permission (Service Usage Admin, or Owner/Editor). Locked-down\n"
            "corporate projects routinely withhold it.",
            "Fastest ways forward, pick one:\n"
            "  1. Ask an admin to enable %s on %s\n"
            "  2. Use a personal / free-trial project instead\n"
            "  3. Use an AI Studio API key - Lab 01 works fully on it:\n"
            "     %s" % (VERTEX_API, project, AI_STUDIO_KEY_URL),
            required=False,
        )
        return False
    if "billing" in output.lower() or "FAILED_PRECONDITION" in output:
        report(
            FAIL,
            "enabling %s needs billing linked to %s" % (VERTEX_API, project),
            "Google Cloud will not enable a paid API on a project with no\n"
            "billing account attached, even with free credits available.",
            "Link a billing account:\n"
            "  https://console.cloud.google.com/billing/linkedaccount?project=%s\n"
            "At a workshop: ask the instructor for the credits/coupon.\n"
            "Or use an AI Studio key for Lab 01: %s"
            % (project, AI_STUDIO_KEY_URL),
            required=False,
        )
        return False
    report(FAIL, "enabling %s failed (exit %d)" % (VERTEX_API, code),
           "See the gcloud output above.",
           "Check billing is linked to %s, then try again." % project,
           required=False)
    return False


def setup_adc(project, assume_yes):
    """Step d. Verifies Application Default Credentials, and fixes quota.

    Cloud Shell (and any GCE VM, Cloud Run service or Agent Engine instance)
    already has ADC from the metadata server. Running
    `gcloud auth application-default login` there is not just unnecessary,
    it sends people chasing a browser popup that cannot open, so we detect
    that case and skip the step entirely.
    """
    setup_step("d", "Application Default Credentials")
    source, detail = detect_adc()

    if source == "ambient":
        where = "Cloud Shell" if in_cloud_shell() else "this VM"
        report(
            PASS,
            "ADC is already provided by the environment - nothing to do",
            "%s is authenticated for you and serves credentials from the\n"
            "metadata server. There is no credentials file, and you should\n"
            "NOT run `gcloud auth application-default login` here.\n"
            "%s" % (where, detail),
        )
        return True

    setup_say(
        "ADC is what your Python code authenticates with. Step b already\n"
        "wrote it via `gcloud auth login --update-adc`, so this step is\n"
        "normally just a verification - plus one fix. Because that login ran\n"
        "BEFORE the project was set, the credentials can carry the wrong\n"
        "quota project, and we realign it explicitly below.")

    if source == "file":
        setup_say("ADC file already present: %s" % detail)
        if gcloud_value("auth", "application-default", "print-access-token"):
            report(PASS, "existing ADC works", detail)
            setup_fix_quota_project(project, assume_yes)
            return True
        setup_say("...but it did not produce a token, so it is expired or "
                  "revoked.")

    setup_say("Falling back to the ADC-only login for this one step:")
    cmd = ["gcloud", "auth", "application-default", "login"]
    setup_show(cmd)
    if not ask_yes_no("Run it?", assume_yes):
        report(SKIP, "ADC not created", required=False)
        return False
    code, _ = run_step_command(cmd, interactive=True)
    verify = ["gcloud", "auth", "application-default", "print-access-token"]
    setup_say("Verifying with:")
    setup_show(verify)
    if gcloud_value("auth", "application-default", "print-access-token"):
        report(PASS, "ADC works", adc_path() or "")
        setup_fix_quota_project(project, assume_yes)
        return True
    report(FAIL, "ADC still not usable (exit %d)" % code, None,
           "Re-run `gcloud auth application-default login`. If an org policy\n"
           "blocks it, use a personal project or the AI Studio key path:\n"
           "  %s" % AI_STUDIO_KEY_URL, required=False)
    return False


def setup_fix_quota_project(project, assume_yes):
    """Step d2. Realigns the ADC quota project when it drifted."""
    quota = adc_quota_project()
    if not project or not quota or quota == project:
        return
    setup_step("d2", "ADC quota project does not match")
    setup_say(
        "Your ADC bills and quotas against %s, but you chose %s.\n"
        "That is the classic 'it 403s and I do not know why' setup, and it\n"
        "happens when the project is set after the ADC login instead of\n"
        "before it. One command realigns them." % (quota, project))
    cmd = ["gcloud", "auth", "application-default", "set-quota-project",
           project]
    setup_show(cmd)
    if not ask_yes_no("Run it?", assume_yes):
        report(SKIP, "quota project left as %s" % quota, required=False)
        return
    code, _ = run_step_command(cmd)
    now = adc_quota_project()
    if code == 0 and now == project:
        report(PASS, "ADC quota project is now %s" % project)
    else:
        report(FAIL, "quota project is still %r" % (now or "unset"),
               "This needs the serviceusage.services.use permission on %s."
               % project, required=False)


def setup_exports(project):
    """Step g. Prints the exports the user has to paste themselves."""
    setup_step("g", "environment variables")
    setup_say(
        "A child process cannot change its parent shell's environment, so\n"
        "this script cannot export these for you. Copy the two lines below\n"
        "into your shell (and into your ~/.bashrc or ~/.zshrc if you want\n"
        "them to survive a new terminal):")
    print("")
    print("export GOOGLE_CLOUD_PROJECT=%s" % (project or "YOUR_PROJECT_ID"))
    print("export GOOGLE_CLOUD_LOCATION=global")
    print("")
    setup_say(
        "PowerShell:\n"
        '  $env:GOOGLE_CLOUD_PROJECT = "%s"\n'
        '  $env:GOOGLE_CLOUD_LOCATION = "global"'
        % (project or "YOUR_PROJECT_ID"))
    if project:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
        setup_say("(They are set inside THIS process too, so the checks below\n"
                  "run against them. Your shell still needs the paste.)")


def setup_ai_studio(assume_yes):
    """The no-GCP-project branch: an AI Studio key, good for Lab 01."""
    setup_step("*", "AI Studio API key (Lab 01 only)")
    setup_say(
        "No project is fine for Lab 01 - it has no cloud dependency except\n"
        "the model call. Labs 02-04 use managed services an API key cannot\n"
        "reach, so you will need a project for those.\n"
        "\n"
        "1. Open %s\n"
        "2. Click 'Create API key' (a Google account is all it takes)\n"
        "3. Copy the key" % AI_STUDIO_KEY_URL)
    key = ask_text("Paste the key here (or press Enter to skip):", assume_yes)
    if not key:
        report(SKIP, "no API key entered",
               "Set it yourself when you have one:\n"
               "  export GOOGLE_API_KEY=YOUR_API_KEY\n"
               "  export GOOGLE_GENAI_USE_ENTERPRISE=False", required=False)
        return False
    os.environ["GOOGLE_API_KEY"] = key
    os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "False"
    report(PASS, "GOOGLE_API_KEY set for this process (ends ...%s)" % key[-4:])
    setup_say(
        "Again, this process cannot export into your shell. Paste this:")
    print("")
    print("export GOOGLE_API_KEY=%s" % key)
    print("export GOOGLE_GENAI_USE_ENTERPRISE=False")
    print("")
    return True


def run_guided_setup(assume_yes):
    """Walks the setup steps in the order that actually works.

    Order matters, and the wrong order is why this exists:
    login (--update-adc, one popup for both) -> set project -> realign the
    ADC quota project -> enable the API -> exports -> verify.

    Args:
        assume_yes: Skip the per-step confirmation prompts (--yes).
    """
    print("")
    print("=" * 75)
    print("GUIDED SETUP")
    print("=" * 75)
    setup_say(
        "Every step tells you what it is about to run, shows you the exact\n"
        "command, and asks first. Nothing destructive runs, and the only API\n"
        "this enables is %s.\n"
        "Answer 'n' to any step to skip it. Ctrl-C is always safe." % VERTEX_API)
    if in_cloud_shell():
        setup_say(
            "\nCloud Shell detected. You are already signed in and already\n"
            "have working credentials, so the login steps below will detect\n"
            "that and skip themselves. Do not run\n"
            "`gcloud auth login --update-adc` or\n"
            "`gcloud auth application-default login` here.")

    if in_cloud_shell():
        have_project = True
    else:
        have_project = ask_yes_no(
            "Do you have (or can you create) a Google Cloud project?",
            assume_yes, runs_command=False)
    if have_project:
        if setup_gcloud_present():
            setup_account(assume_yes)
            project = setup_project(assume_yes)
            setup_adc(project, assume_yes)
            setup_billing(project)
            setup_enable_api(project, assume_yes)
            setup_exports(project)
    else:
        setup_ai_studio(assume_yes)

    print("")
    print("=" * 75)
    print("GUIDED SETUP DONE - re-running the normal checks so you can see")
    print("the result for yourself, live model call and all.")
    print("=" * 75)


# ---------------------------------------------------------------------------


def main():
    """Runs every check and returns the process exit code."""
    parser = argparse.ArgumentParser(
        description="Pre-flight check for the AI4 GCP Agent Labs."
    )
    parser.add_argument(
        "--lab",
        help="which lab to check dependencies for: 01, 02, 03, 04, a full "
             "directory name, or 'all'. Defaults to the lab you are standing "
             "in, else all.",
    )
    parser.add_argument("--offline", action="store_true",
                        help="skip every network check (PyPI and the live model call)")
    parser.add_argument("--skip-live", action="store_true",
                        help="skip only the live model call")
    parser.add_argument("--model", help="model id to use for the live call")
    parser.add_argument("--probe-models", action="store_true",
                        help="try every candidate model and report which work here")
    parser.add_argument("--setup", action="store_true",
                        help="guided, interactive setup: walks gcloud login, "
                             "project, the Vertex AI API and ADC in the right "
                             "order, asking before each command, then runs the "
                             "normal checks. Without this flag nothing is "
                             "changed.")
    parser.add_argument("--yes", action="store_true",
                        help="with --setup, do not prompt before each command "
                             "(still only runs the commands --setup would)")
    args = parser.parse_args()

    if args.setup:
        run_guided_setup(args.yes)
    elif args.yes:
        print("note: --yes only does something with --setup.")

    labs = detect_lab(args.lab)
    env = load_lab_env(labs[0])
    loaded = env.load_dotenv(os.getcwd()) if env else []
    if env:
        env.apply_auth_env()

    print("AI4 GCP Agent Labs - prerequisite check")
    _rev = repo_revision()
    print("repo: %s%s" % (REPO_ROOT, (" @ " + _rev) if _rev else ""))
    print("labs checked: %s" % ", ".join(labs))
    if loaded:
        print(".env loaded: %s" % ", ".join(loaded))
    else:
        print(".env loaded: none (using the real environment only)")

    section("interpreter")
    check_python()
    check_virtualenv()

    section("dependencies")
    deps_ok = check_dependencies(labs)

    section("network")
    check_pypi(args.offline, deps_ok)
    check_pip_index()

    section("auth")
    mode = check_auth(env)
    check_project(env, mode)

    section("live model call")
    check_live_model(env, mode, args.offline or args.skip_live, args.model)
    if args.probe_models and not (args.offline or args.skip_live):
        probe_models(env, mode, args.model)

    section("tooling")
    check_tooling()

    print("")
    if env:
        print(env.describe_auth())
    if failures:
        print("RESULT: %d required check(s) FAILED:" % len(failures))
        for name in failures:
            print("  - %s" % name)
        print("Fix the items above and re-run: python check_prereqs.py")
        return 1
    if warnings_seen:
        print("RESULT: all required checks passed (%d warning(s))."
              % len(warnings_seen))
    else:
        print("RESULT: all checks passed.")
    print("Next: cd labs/%s && ./test.sh   then   python run_local.py" % labs[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
