"""UI smoke matrix for the five supported ERP Delivery installations.

Each database is installed from scratch, served by a real Odoo HTTP process,
and opened in Chromium. The test deliberately does not create business data;
it verifies that the installed combination can log in, open the ERP Projects
action, open the Project form, and expose the expected Customer field shape.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ODOO_BIN = ROOT.parent / "odoo-venv/bin/python"
ODOO_SCRIPT = ROOT.parent / "odoo/odoo-bin"
ADDONS = f"{ROOT.parent / 'odoo/addons'},{ROOT / 'custom_addons'}"
PG_BIN = Path("/usr/lib/postgresql/16/bin")
PG_HOST = "/tmp"
PG_PORT = "55432"
DATA_DIR = Path("/tmp/erp-delivery-ui-data")
SCREENSHOT_DIR = ROOT / "docs/implementation/screenshots/006_ui_e2e"
RESULT_PATH = ROOT / "docs/implementation/results_ui_install_matrix.json"
REUSE_EXISTING = os.environ.get("MATRIX_REUSE") == "1"
TEST_PASSWORD = os.environ.get("ERP_DELIVERY_TEST_PASSWORD")
if not TEST_PASSWORD:
    raise RuntimeError("Set ERP_DELIVERY_TEST_PASSWORD before running the UI matrix")

COMBINATIONS = [
    ("core", ("erp_delivery",), True),
    ("core_sale", ("erp_delivery", "erp_delivery_sale"), False),
    ("core_quality", ("erp_delivery", "erp_delivery_quality"), True),
    ("all_sale_quality", ("erp_delivery", "erp_delivery_sale", "erp_delivery_quality"), False),
    ("all_quality_sale", ("erp_delivery", "erp_delivery_quality", "erp_delivery_sale"), False),
]


def odoo_args(db: str) -> list[str]:
    return [
        str(ODOO_BIN),
        str(ODOO_SCRIPT),
        f"--addons-path={ADDONS}",
        f"--db_host={PG_HOST}",
        f"--db_port={PG_PORT}",
        "--db_user=pc",
        "--db_password=",
        f"--data-dir={DATA_DIR}",
        f"-d={db}",
        "--workers=0",
        "--max-cron-threads=0",
    ]


def run_checked(command: list[str], *, input_text: str | None = None, log_path: Path | None = None) -> None:
    output = None
    if log_path:
        output = log_path.open("w", encoding="utf-8")
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT.parent,
            input=input_text,
            text=True,
            stdout=output,
            stderr=subprocess.STDOUT if output else None,
            check=False,
        )
    finally:
        if output:
            output.close()
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}")


def wait_for_port(port: int) -> None:
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"Odoo did not listen on port {port}")


def fixture_admin(db: str, log_path: Path) -> None:
    code = f"""
admin = env.ref('base.user_admin')
manager_group = env.ref('erp_delivery.group_erp_delivery_manager')
admin.write({{'password': {TEST_PASSWORD!r}, 'groups_id': [(4, manager_group.id)]}})
env.cr.commit()
print('matrix_fixture_ready', admin.login)
"""
    args = odoo_args(db)
    run_checked(
        [args[0], args[1], "shell"] + args[2:] + ["--shell-interface=python"],
        input_text=code,
        log_path=log_path,
    )


def run_ui_smoke(db: str, port: int, expect_customer: bool, key: str) -> dict[str, object]:
    base = f"http://127.0.0.1:{port}"
    server_log = Path(f"/tmp/erp-delivery-ui-matrix-{key}.log")
    server_output = server_log.open("w", encoding="utf-8")
    server = subprocess.Popen(
        odoo_args(db)
        + [
            "--http-interface=127.0.0.1",
            f"--http-port={port}",
            "--log-level=info",
        ],
        cwd=ROOT.parent,
        stdout=server_output,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_port(port)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"{base}/web/login?db={db}")
            page.locator('input[name="login"]').fill("admin")
            page.locator('input[name="password"]').fill(TEST_PASSWORD)
            page.locator('button[type="submit"]').click()
            page.wait_for_url("**/odoo", timeout=15_000)
            page.goto(f"{base}/odoo/action-erp_delivery.action_erp_project")
            page.wait_for_selector(".o_list_table", timeout=15_000)
            page.goto(f"{base}/odoo/action-erp_delivery.action_erp_project/new")
            page.wait_for_selector('[name="name"] textarea', timeout=15_000)

            customer = page.locator('[name="partner_id"]')
            customer_visible = any(customer.nth(i).is_visible() for i in range(customer.count()))
            assert customer_visible is expect_customer, (
                f"{key}: expected partner_id visible={expect_customer}, "
                f"count={customer.count()}, visible={customer_visible}"
            )
            page.screenshot(path=str(SCREENSHOT_DIR / f"remaining_combo_{key}_project_form.png"), full_page=True)
            browser.close()
            return {
                "status": "PASS",
                "customer_field_visible": customer_visible,
                "expected_customer_field_visible": expect_customer,
            }
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        server_output.close()


def main() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {
        "started_at": datetime.now().astimezone().isoformat(),
        "tests": {},
    }
    for index, (key, modules, expect_customer) in enumerate(COMBINATIONS):
        db = f"erp_ui_matrix_{key}"
        port = 8171 + index
        init_log = Path(f"/tmp/erp-delivery-ui-matrix-{key}-init.log")
        fixture_log = Path(f"/tmp/erp-delivery-ui-matrix-{key}-fixture.log")
        try:
            if not REUSE_EXISTING:
                run_checked([str(PG_BIN / "dropdb"), "-h", PG_HOST, "-p", PG_PORT, "--if-exists", db])
                run_checked([str(PG_BIN / "createdb"), "-h", PG_HOST, "-p", PG_PORT, db])
                run_checked(
                    odoo_args(db)
                    + [
                        "--without-demo=all",
                        "-i",
                        ",".join(modules),
                        "--stop-after-init",
                        "--log-level=info",
                    ],
                    log_path=init_log,
                )
            fixture_admin(db, fixture_log)
            results["tests"][key] = run_ui_smoke(db, port, expect_customer, key)
            results["tests"][key]["modules"] = list(modules)
            results["tests"][key]["database"] = db
        except Exception as exc:  # noqa: BLE001 - preserve all matrix evidence
            results["tests"][key] = {
                "status": "FAIL",
                "modules": list(modules),
                "database": db,
                "error": str(exc),
                "init_log": str(init_log),
            }

    results["finished_at"] = datetime.now().astimezone().isoformat()
    RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    if any(case["status"] != "PASS" for case in results["tests"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
