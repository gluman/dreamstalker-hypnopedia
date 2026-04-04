"""Pytest fixtures for DreamStalker web tests."""

import time
import pytest
import requests
from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session", autouse=True)
def wait_for_server():
    for attempt in range(10):
        try:
            resp = requests.get(BASE_URL + "/api/sessions", timeout=5)
            if resp.status_code == 200:
                print("\nServer is ready!")
                return
        except Exception:
            pass
        print(f"\nWaiting for server... attempt {attempt + 1}/10")
        time.sleep(3)
    raise RuntimeError("Server not available after 10 attempts")


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture()
def page(browser):
    page = browser.new_page()
    yield page
    page.close()
