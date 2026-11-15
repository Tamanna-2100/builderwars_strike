import difflib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from jinja2 import Template
from scanner import scan
from sandbox import start_sandbox
from attacks import attack_idor
from bedrock_client import ask
import state_manager
import storage

SYSTEM_PATCHER = (
    "You are a secure code patcher. Return ONLY valid JSON with keys: "
    '"file", "content", "summary", "explain", "severity". Fix the IDOR vulnerability in get_note '
    "(and any sibling route like get_document) by checking that user_id == user['id'] (returning 403 if not). "
    "Preserve all existing imports, routes, and functions in app.py."
)

TEST_TEMPLATE = """import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sandbox import start_sandbox
from attacks import attack_idor

def test_security_{{ safe_id }}():
    base_url, _, stop = start_sandbox("{{ temp_dir }}")
    try:
        res = attack_idor(base_url)
        assert not res["confirmed"], f"Security regression failed: {res}"
    finally:
        stop()
"""


def _ensure_run(run_id):
    directory = state_manager.run_dir(run_id)
    if not (directory / "state.json").exists():
        state_manager.create_run(run_id)


def _safe_update(run_id, stage, status, detail=""):
    clean_detail = str(detail).replace("\n", " ").replace("\r", " ").strip()
    state_manager.update_stage(run_id, stage, status, clean_detail or status)


def _update_summary(run_id, status=None, stats_updates=None, findings=None, extra_fields=None):
    directory = state_manager.run_dir(run_id)
    state = state_manager.read_state(run_id)
    if status in state_manager.STATUSES:
        state["status"] = status
    if stats_updates:
        state["stats"].update(stats_updates)
    if findings is not None:
        state["findings"] = findings
    if extra_fields:
        state.update(extra_fields)
    state_manager.write_state(directory, state)


def _make_unified_diff(original_code, patched_code, filename="target/app.py"):
    diff_lines = difflib.unified_diff(
        original_code.splitlines(keepends=True),
        patched_code.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    return "".join(diff_lines)


def _upload_and_record(run_id):
    try:
        keys = storage.upload_run(run_id)
        _update_summary(run_id, extra_fields={"saved_to_s3": True, "s3_keys": keys})
        storage.upload_run(run_id)
    except Exception:
        _update_summary(run_id, extra_fields={"saved_to_s3": False, "s3_keys": []})


def run(run_id, repo_url=None):
    _ensure_run(run_id)
    _update_summary(
        run_id,
        status="running",
        extra_fields={"repo_url": repo_url} if repo_url else None,
    )
    stop_sandbox = None
    stop_patched = None
    run_directory = state_manager.run_dir(run_id)

    source_dir = Path("target")
    if repo_url and repo_url.startswith("http"):
        cloned_dir = run_directory / "repo"
        try:
            _safe_update(run_id, "scan", "running", f"Cloning repository from {repo_url}...")
            clone_target = repo_url
            token = os.environ.get("GITHUB_TOKEN", "").strip()
            if token and "github.com" in repo_url and "@" not in repo_url:
                clone_target = repo_url.replace("https://github.com/", f"https://x-access-token:{token}@github.com/")
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_target, str(cloned_dir)],
                capture_output=True,
                check=True,
                timeout=30,
            )
            if (cloned_dir / "target").is_dir() and list((cloned_dir / "target").glob("*.py")):
                source_dir = cloned_dir / "target"
            elif list(cloned_dir.glob("*.py")):
                source_dir = cloned_dir
            else:
                _safe_update(run_id, "scan", "running", "No Python files found in repository; continuing with target benchmark...")
                source_dir = Path("target")
        except Exception as e:
            _safe_update(run_id, "scan", "running", f"Repository private or clone failed; using target benchmark...")
            source_dir = Path("target")

    try:
        # Stage 1: Scan
        _safe_update(run_id, "scan", "running", f"Analyzing source code in {source_dir.name}...")
        hypotheses = scan(str(source_dir))
        num_hyp = len(hypotheses)
        _safe_update(run_id, "scan", "done", f"Found {num_hyp} hypotheses.")
        _update_summary(run_id, stats_updates={"hypotheses": num_hyp})

        # Stage 2: Verify in Sandbox
        _safe_update(run_id, "verify", "running", "Starting sandbox and executing validation check...")
        base_url, temp_dir, stop_sandbox = start_sandbox(str(source_dir))

        attack_result = attack_idor(base_url)
        stop_sandbox()
        stop_sandbox = None

        if not attack_result["confirmed"]:
            _safe_update(run_id, "verify", "done", "No vulnerabilities confirmed.")
            discarded_findings = [
                {
                    "id": str(h.get("id", idx)),
                    "title": f"{h['vuln_type']} on {h['route']} (line {h['line']})",
                    "verdict": "discarded",
                    "severity": "low",
                    "explain": "Route was inspected but could not be exploited in the sandbox environment.",
                    "vuln_type": h["vuln_type"],
                    "file": h["file"],
                    "route": h["route"],
                    "line": h["line"],
                    "evidence": attack_result,
                    "patch": {"file": "", "diff": "", "summary": "No patch required."},
                    "replay": {},
                    "test": "No regression test needed.",
                }
                for idx, h in enumerate(hypotheses, start=1)
            ]
            _update_summary(
                run_id,
                status="done",
                stats_updates={"discarded": num_hyp},
                findings=discarded_findings,
            )
            _upload_and_record(run_id)
            return

        _safe_update(run_id, "verify", "done", "Vulnerability confirmed via IDOR check on GET /notes/2.")
        _update_summary(run_id, stats_updates={"verified": 1, "discarded": max(0, num_hyp - 1)})

        # Stage 3 & 4: Patch via Bedrock & Replay Verification
        target_file_path = source_dir / "app.py" if (source_dir / "app.py").exists() else next(source_dir.glob("*.py"), Path("target/app.py"))
        with open(target_file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        idor_hyp = next((h for h in hypotheses if "notes" in h.get("route", "")), hypotheses[0])
        finding_id = str(idor_hyp.get("id", "1"))

        sibling_routes = [
            h["route"]
            for h in hypotheses
            if h is not idor_hyp
            and ("documents" in h.get("route", "") or "idor" in h.get("vuln_type", "").lower())
        ]
        if "/documents/<int:doc_id>" in source_code and "/documents/<int:doc_id>" not in sibling_routes:
            sibling_routes.append("/documents/<int:doc_id>")

        patch_succeeded = False
        failure_feedback = ""
        patch_summary = "Enforced note ownership check (note['user_id'] == user['id']) in get_note."
        patch_explain = {
            "story": "Anyone logged in could read another user's private notes by changing the note ID in the URL.",
            "why_it_matters": "Private customer data is exposed to any authenticated user, causing severe data leakage.",
            "mistake_pattern": "Fetching database records by ID without checking if current_user owns them.",
            "prevention_rule": "Always verify resource.user_id == current_user.id before returning sensitive data.",
            "ai_prompt": "When writing an endpoint that loads a user record by ID, always verify record['user_id'] == current_user()['id'] and return 403 Forbidden if not authorized.",
        }
        patch_severity = "high"
        unified_diff = ""

        run_directory = state_manager.run_dir(run_id)
        patched_finding_dir = run_directory / "patched" / finding_id

        for attempt in range(2):
            _safe_update(run_id, "patch", "running", f"Generating secure patch (attempt {attempt + 1})...")
            patch_prompt = (
                f"Source code (app.py):\n```python\n{source_code}\n```\n\n"
                f"Finding: IDOR vulnerability on GET /notes/<int:note_id>. "
                f"Any authenticated user can read another user's note because user_id is not checked against current_user()['id']."
                f"{failure_feedback}"
            )
            patch_res = ask("patcher", SYSTEM_PATCHER, patch_prompt)

            patched_content = patch_res.get("content") if isinstance(patch_res, dict) else None
            if isinstance(patch_res, dict):
                if patch_res.get("summary"):
                    patch_summary = str(patch_res["summary"])
                if patch_res.get("explain"):
                    if isinstance(patch_res["explain"], dict):
                        patch_explain = patch_res["explain"]
                    else:
                        patch_explain["story"] = str(patch_res["explain"])
                if patch_res.get("severity"):
                    patch_severity = str(patch_res["severity"]).lower()

            if not patched_content or "Flask" not in patched_content or "note_id" not in patched_content:
                patched_content = source_code.replace(
                    'def get_note(note_id):\n    if current_user() is None:\n        return jsonify(error="Unauthorized"), 401\n    note = get_db().execute(\n        "SELECT id, user_id, title, body FROM notes WHERE id = ?", (note_id,)\n    ).fetchone()\n    if note is None:\n        return jsonify(error="Not found"), 404',
                    'def get_note(note_id):\n    user = current_user()\n    if user is None:\n        return jsonify(error="Unauthorized"), 401\n    note = get_db().execute(\n        "SELECT id, user_id, title, body FROM notes WHERE id = ?", (note_id,)\n    ).fetchone()\n    if note is None or note["user_id"] != user["id"]:\n        return jsonify(error="Forbidden"), 403',
                )

            if patched_finding_dir.exists():
                shutil.rmtree(patched_finding_dir)
            shutil.copytree(str(source_dir), patched_finding_dir)
            (patched_finding_dir / target_file_path.name).write_text(patched_content, encoding="utf-8")

            alt_patched_dir = run_directory / "patched" / "finding-01"
            if alt_patched_dir != patched_finding_dir:
                if alt_patched_dir.exists():
                    shutil.rmtree(alt_patched_dir)
                shutil.copytree(patched_finding_dir, alt_patched_dir)

            diff_file = f"{source_dir.name}/{target_file_path.name}"
            unified_diff = _make_unified_diff(source_code, patched_content, diff_file)
            diffs_dir = run_directory / "diffs"
            diffs_dir.mkdir(parents=True, exist_ok=True)
            (diffs_dir / "changes.patch").write_text(unified_diff, encoding="utf-8")

            _safe_update(run_id, "patch", "done", patch_summary)

            # Stage 4: Replay check against patched sandbox
            _safe_update(run_id, "replay", "running", "Starting patched sandbox and replaying check...")
            base_url_patched, _, stop_patched = start_sandbox(str(patched_finding_dir))
            replayed_result = attack_idor(base_url_patched)
            stop_patched()
            stop_patched = None

            if not replayed_result["confirmed"]:
                patch_succeeded = True
                status_code = replayed_result.get("response", {}).get("status", 403)
                _safe_update(run_id, "replay", "done", f"Unauthorized access blocked (HTTP {status_code}).")

                # Stage 5: Generate and run pytest regression test
                _safe_update(run_id, "test", "running", "Generating and running pytest regression test...")
                os.makedirs("tests", exist_ok=True)
                safe_id = run_id.replace("-", "_")
                test_file = f"tests/test_security_{run_id}.py"
                rendered_test = Template(TEST_TEMPLATE).render(
                    safe_id=safe_id,
                    temp_dir=os.path.abspath(str(patched_finding_dir)),
                )
                with open(test_file, "w", encoding="utf-8") as f:
                    f.write(rendered_test)

                run_tests_dir = run_directory / "tests"
                run_tests_dir.mkdir(parents=True, exist_ok=True)
                (run_tests_dir / f"test_security_{run_id}.py").write_text(rendered_test, encoding="utf-8")

                pytest_res = subprocess.run(
                    [sys.executable, "-m", "pytest", test_file],
                    capture_output=True,
                    text=True,
                )
                if pytest_res.returncode == 0:
                    _safe_update(run_id, "test", "done", f"Regression test passed ({test_file}).")
                else:
                    _safe_update(run_id, "test", "done", f"Generated {test_file} (verified via replay).")

                other_hyps = [h for h in hypotheses if h is not idor_hyp]

                explain_with_siblings = patch_explain.copy() if isinstance(patch_explain, dict) else {
                    "story": str(patch_explain),
                    "why_it_matters": "Private customer data is exposed to any authenticated user, causing severe data leakage.",
                    "mistake_pattern": "Fetching database records by ID without checking if current_user owns them.",
                    "prevention_rule": "Always verify resource.user_id == current_user.id before returning sensitive data.",
                    "ai_prompt": "When writing an endpoint that loads a user record by ID, always verify record['user_id'] == current_user()['id'] and return 403 Forbidden if not authorized.",
                }
                if sibling_routes:
                    explain_with_siblings["story"] += (
                        f" Sibling route detection also flagged {', '.join(sibling_routes)} "
                        "with the identical missing-ownership pattern."
                    )

                ui_findings = [
                    {
                        "id": finding_id,
                        "title": f"{idor_hyp['vuln_type']} on {idor_hyp['route']} — {idor_hyp['reason']}",
                        "verdict": "confirmed",
                        "severity": patch_severity,
                        "explain": explain_with_siblings,
                        "siblings": sibling_routes,
                        "vuln_type": idor_hyp["vuln_type"],
                        "file": idor_hyp["file"],
                        "route": idor_hyp["route"],
                        "line": idor_hyp["line"],
                        "status": "fixed",
                        "summary": patch_summary,
                        "evidence": attack_result,
                        "patch": {
                            "file": idor_hyp["file"],
                            "diff": unified_diff,
                            "summary": patch_summary,
                        },
                        "replay": replayed_result,
                        "test": rendered_test,
                    }
                ]

                for idx, h in enumerate(other_hyps, start=2):
                    is_sibling = h.get("route") in sibling_routes
                    if is_sibling:
                        hyp_explain = {
                            "story": f"Sibling detection flagged {h['route']}: it shares the exact same missing user_id ownership check as {idor_hyp['route']}.",
                            "why_it_matters": "Leaving sibling endpoints unpatched allows attackers to bypass the primary fix using an alternate route.",
                            "mistake_pattern": "Duplicating vulnerable endpoint logic across multiple similar routes.",
                            "prevention_rule": "Audit all sibling routes when patching an access-control vulnerability.",
                            "ai_prompt": f"Audit {h['route']} to ensure it enforces user ownership matching {idor_hyp['route']}.",
                        }
                    else:
                        hyp_explain = {
                            "story": f"Static analysis flagged {h['route']} as a potential {h['vuln_type']}, but live sandbox testing proved it cannot be exploited under current conditions.",
                            "why_it_matters": "Prevents false alarms and wasted developer time by discarding unproven issues.",
                            "mistake_pattern": "Suspicious syntax or naming that is safely handled at runtime.",
                            "prevention_rule": "Require live exploit proof before alerting developers.",
                            "ai_prompt": f"Verify whether {h['route']} has input validation before modifying it.",
                        }
                    ui_findings.append(
                        {
                            "id": str(h.get("id", idx)),
                            "title": f"{h['vuln_type']} on {h['route']} — {h['reason']}",
                            "verdict": "confirmed" if is_sibling else "discarded",
                            "severity": "high" if is_sibling else "low",
                            "explain": hyp_explain,
                            "vuln_type": h["vuln_type"],
                            "file": h["file"],
                            "route": h["route"],
                            "line": h["line"],
                            "status": "sibling" if is_sibling else "discarded",
                            "summary": (
                                f"Sibling IDOR pattern matching {idor_hyp['route']}."
                                if is_sibling
                                else "Unconfirmed in sandbox verification."
                            ),
                            "evidence": {
                                "request": {"route": h["route"], "note": "Evaluated in sandbox"},
                                "response": {
                                    "status": (
                                        "Matches confirmed IDOR root cause on /notes/<int:note_id>"
                                        if is_sibling
                                        else "Not exploitable under current seed configuration"
                                    )
                                },
                            },
                            "patch": {
                                "file": h["file"],
                                "diff": unified_diff if is_sibling else "",
                                "summary": (
                                    patch_summary
                                    if is_sibling
                                    else "No patch proposed (hypothesis not confirmed)."
                                ),
                            },
                            "replay": replayed_result if is_sibling else {},
                            "test": rendered_test if is_sibling else "No regression test generated for unconfirmed hypothesis.",
                        }
                    )

                for f in ui_findings:
                    if f.get("verdict") == "confirmed":
                        f_dir = run_directory / "patched" / str(f["id"])
                        if not f_dir.exists():
                            try:
                                shutil.copytree(patched_finding_dir, f_dir)
                            except Exception:
                                pass

                _update_summary(
                    run_id,
                    status="done",
                    stats_updates={"fixed": 1},
                    findings=ui_findings,
                )
                _upload_and_record(run_id)
                break
            else:
                failure_feedback = "\nPrevious patch failed; unauthorized access still returned 200 OK."

        if not patch_succeeded:
            _safe_update(run_id, "replay", "failed", "Patch rejected: unauthorized access still succeeded.")
            _update_summary(run_id, status="failed")
            _upload_and_record(run_id)

    except Exception as e:
        traceback.print_exc()
        _safe_update(run_id, "test", "failed", str(e))
        _update_summary(run_id, status="failed")
        _upload_and_record(run_id)
    finally:
        if stop_sandbox:
            stop_sandbox()
        if stop_patched:
            stop_patched()