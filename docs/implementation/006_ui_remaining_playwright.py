"""Playwright coverage for the UI cases left after the initial E2E audit.

The script intentionally creates all business records through the browser.
The only fixture setup performed outside the browser is documented in
006_full_ui_e2e_testing.md (database, users, and companies).

Run against the temporary UI server used by the handoff:

    odoo-venv/bin/python docs/implementation/006_ui_remaining_playwright.py
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


BASE_URL = "http://127.0.0.1:8169"
DB = "erp_ui_test"
LOGIN = "admin"
PASSWORD = os.environ.get("ERP_DELIVERY_TEST_PASSWORD")
if not PASSWORD:
    raise RuntimeError("Set ERP_DELIVERY_TEST_PASSWORD before running the UI checks")
ACTION_URL = f"{BASE_URL}/odoo/action-erp_delivery.action_erp_project"
SCREENSHOT_DIR = Path(__file__).parent / "screenshots/006_ui_e2e"
RESULT_PATH = Path(__file__).parent / "results_ui_remaining.json"


def wait_for_list(page: Page) -> None:
    page.wait_for_selector(".o_list_table", timeout=15_000)
    page.wait_for_timeout(250)


def login(page: Page) -> None:
    page.goto(f"{BASE_URL}/web/login?db={DB}")
    page.locator('input[name="login"]').fill(LOGIN)
    page.locator('input[name="password"]').fill(PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_url(re.compile(r"/odoo(?:$|/?)"), timeout=15_000)
    page.wait_for_timeout(500)


def open_projects(page: Page) -> None:
    page.goto(ACTION_URL)
    wait_for_list(page)


def open_project_form(page: Page) -> None:
    page.goto(f"{ACTION_URL}/new")
    page.wait_for_selector('[name="name"] textarea', timeout=15_000)


def save_form(page: Page) -> None:
    page.locator('button[aria-label="Save manually"]').click()
    page.wait_for_timeout(700)
    if page.locator('[role="dialog"]').count():
        raise AssertionError(page.locator('[role="dialog"]').inner_text())


def create_project(page: Page, name: str) -> str:
    open_project_form(page)
    page.locator('[name="name"] textarea').fill(name)
    save_form(page)
    page.wait_for_url(re.compile(r"/odoo/action-\d+/\d+$"), timeout=15_000)
    page.wait_for_timeout(400)
    return page.url


def open_tab(page: Page, tab_name: str) -> None:
    page.locator(f'a[name="{tab_name}"]').click()
    page.wait_for_timeout(250)


def add_risk(page: Page, project_url: str, name: str, level: str, state: str = "Open") -> None:
    page.goto(project_url)
    page.wait_for_selector('[name="name"] textarea', timeout=15_000)
    open_tab(page, "erp_risks")
    page.get_by_text("Add a line", exact=True).click()
    row = page.locator(".o_list_table tbody tr.o_data_row").last
    row.locator('td[name="name"] input').fill(name)
    row.locator('td[name="level"] select').select_option(label=level)
    row.locator('td[name="state"] select').select_option(label=state)
    page.locator('[name="name"] textarea').click()
    save_form(page)


def risk_state(page: Page, project_url: str) -> str:
    page.goto(project_url)
    page.wait_for_selector('[name="name"] textarea', timeout=15_000)
    open_tab(page, "erp_risks")
    row = page.locator(".o_list_table tbody tr.o_data_row").last
    return row.locator('td[name="state"]').inner_text().strip()


def set_risk_state(page: Page, project_url: str, target: str) -> None:
    page.goto(project_url)
    page.wait_for_selector('[name="name"] textarea', timeout=15_000)
    open_tab(page, "erp_risks")
    row = page.locator(".o_list_table tbody tr.o_data_row").last
    row.locator('td[name="state"]').click()
    row.locator('td[name="state"] select').select_option(label=target)
    page.locator('[name="name"] textarea').click()
    save_form(page)


def add_milestone(page: Page, project_url: str, name: str) -> None:
    page.goto(project_url)
    page.wait_for_selector('[name="name"] textarea', timeout=15_000)
    open_tab(page, "erp_milestones")
    page.get_by_text("Add a line", exact=True).click()
    row = page.locator(".o_list_table tbody tr.o_data_row").last
    row.locator('td[name="name"] input').fill(name)
    row.locator('td[name="is_mandatory"] input').check()
    page.locator('[name="name"] textarea').click()
    save_form(page)


def set_milestone_done(page: Page, project_url: str) -> None:
    page.goto(project_url)
    page.wait_for_selector('[name="name"] textarea', timeout=15_000)
    open_tab(page, "erp_milestones")
    row = page.locator(".o_list_table tbody tr.o_data_row").last
    row.locator('td[name="state"]').click()
    row.locator('td[name="state"] select').select_option(label="Done")
    if not row.locator('td[name="is_reached"] input').is_checked():
        row.locator('td[name="is_reached"]').click()
        row.locator('td[name="is_reached"] input').check()
    page.locator('[name="name"] textarea').click()
    save_form(page)


def search_filter(page: Page, label: str) -> list[str]:
    page.locator('input[placeholder="Search..."]').click()
    page.get_by_text(label, exact=True).click()
    page.wait_for_timeout(500)
    return [
        row.inner_text().strip()
        for row in page.locator(".o_list_table tbody tr.o_data_row").all()
    ]


def test_filter_and_group_by(page: Page, expected_names: list[str]) -> None:
    open_projects(page)
    for label, health in (("Green Only", "Green"), ("Amber Only", "Amber"), ("Red Only", "Red")):
        rows = search_filter(page, label)
        assert rows, f"{label} returned no rows"
        assert any(name in "\n".join(rows) for name in expected_names), f"{label}: {rows}"
        assert all(health in row for row in rows), f"{label} returned non-{health}: {rows}"
        open_projects(page)

    page.locator('input[placeholder="Search..."]').click()
    page.get_by_text("Health", exact=True).click()
    page.wait_for_timeout(500)
    groups = [
        node.inner_text().strip()
        for node in page.locator(".o_group_name").all()
    ]
    assert {"Green", "Amber", "Red"}.issubset({group.split(" (")[0] for group in groups}), groups
    page.screenshot(path=str(SCREENSHOT_DIR / "remaining_filter_group_by_health.png"), full_page=True)


def test_kanban_health_badge(page: Page, expected_names: list[str]) -> None:
    open_projects(page)
    page.locator(".o_switch_view.o_kanban").click()
    page.wait_for_selector(".o_kanban_renderer", timeout=15_000)
    page.wait_for_timeout(500)
    cards = page.locator(".oe_kanban_card")
    assert cards.count() >= 3, f"Expected at least three kanban cards, got {cards.count()}"
    body = page.locator(".o_kanban_renderer").inner_text()
    for name in expected_names:
        assert name in body, f"Missing kanban project {name}"
    badges = page.locator(".oe_kanban_card .badge")
    assert badges.count() >= 3, f"Expected health badges, got {badges.count()}"
    badge_text = " ".join(badges.all_inner_texts())
    assert all(health in badge_text for health in ("Green", "Amber", "Red")), badge_text
    page.screenshot(path=str(SCREENSHOT_DIR / "remaining_kanban_health_badges.png"), full_page=True)


def test_risk_lifecycle(page: Page, project_url: str) -> None:
    assert risk_state(page, project_url) == "Open"
    set_risk_state(page, project_url, "Mitigated")
    assert risk_state(page, project_url) == "Mitigated"
    set_risk_state(page, project_url, "Closed")
    assert risk_state(page, project_url) == "Closed"
    page.screenshot(path=str(SCREENSHOT_DIR / "remaining_risk_open_mitigated_closed.png"), full_page=True)


def test_milestone_state_and_reached(page: Page, project_url: str) -> None:
    page.goto(project_url)
    page.wait_for_selector('[name="name"] textarea', timeout=15_000)
    open_tab(page, "erp_milestones")
    row = page.locator(".o_list_table tbody tr.o_data_row").last
    assert row.locator('td[name="state"]').inner_text().strip() == "Pending"
    set_milestone_done(page, project_url)
    page.goto(project_url)
    page.wait_for_selector('[name="name"] textarea', timeout=15_000)
    open_tab(page, "erp_milestones")
    row = page.locator(".o_list_table tbody tr.o_data_row").last
    assert row.locator('td[name="state"]').inner_text().strip() == "Done"
    assert row.locator('td[name="is_reached"] input').is_checked()
    page.screenshot(path=str(SCREENSHOT_DIR / "remaining_milestone_done_reached.png"), full_page=True)


def main() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {
        "started_at": datetime.now().astimezone().isoformat(),
        "base_url": BASE_URL,
        "database": DB,
        "tests": {},
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        login(page)

        green_url = create_project(page, "PW Remaining Green")
        amber_url = create_project(page, "PW Remaining Amber")
        add_risk(page, amber_url, "PW Amber High Risk", "High")
        red_url = create_project(page, "PW Remaining Red")
        add_risk(page, red_url, "PW Red Critical Risk", "Critical")
        lifecycle_url = create_project(page, "PW Risk Lifecycle")
        add_risk(page, lifecycle_url, "PW Lifecycle Critical Risk", "Critical")
        milestone_url = create_project(page, "PW Milestone Lifecycle")
        add_milestone(page, milestone_url, "PW UAT Milestone")

        expected_names = ["PW Remaining Green", "PW Remaining Amber", "PW Remaining Red"]
        cases = {
            "filter_and_group_by_health": lambda: test_filter_and_group_by(page, expected_names),
            "kanban_health_badge": lambda: test_kanban_health_badge(page, expected_names),
            "risk_open_mitigated_closed": lambda: test_risk_lifecycle(page, lifecycle_url),
            "milestone_state_and_is_reached": lambda: test_milestone_state_and_reached(page, milestone_url),
        }
        for name, case in cases.items():
            started = datetime.now().astimezone().isoformat()
            try:
                case()
            except (AssertionError, PlaywrightTimeoutError) as exc:
                results["tests"][name] = {
                    "status": "FAIL",
                    "error": str(exc),
                    "started_at": started,
                }
                page.screenshot(path=str(SCREENSHOT_DIR / f"remaining_FAIL_{name}.png"), full_page=True)
            else:
                results["tests"][name] = {"status": "PASS", "started_at": started}

        browser.close()

    results["finished_at"] = datetime.now().astimezone().isoformat()
    RESULT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    if any(case["status"] != "PASS" for case in results["tests"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
