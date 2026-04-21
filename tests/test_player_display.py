"""
Full-game frontend test for the player display (/player/).

Alice joins and acts through the browser (Playwright).
Bob joins and acts through the REST API.
Alice always joins first so she is the category picker for turn 1.

All assertions are unconditional: the suite stays red until every scene
template is implemented in templates/player/index.html.

Run with:
    PYTHONPATH=. pytest tests/test_player_display.py -v
"""
from __future__ import annotations

import re
import time

import pytest
import requests
from playwright.sync_api import Page, expect

BASE = "http://localhost:6767"

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def api(method: str, path: str, **kwargs) -> requests.Response:
    return requests.request(method, f"{BASE}{path}", **kwargs)


def add_player(name: str) -> str:
    r = api("POST", "/api/players", json={
        "name": name,
        "avatar_emoji": "🤖",
        "avatar_bg_color": "#3498db",
    })
    assert r.status_code == 200, r.json()
    return r.json()["player_id"]


def get_state() -> dict:
    return api("GET", "/api/game/state").json()


def wait_for_phase_api(*phases: str, timeout: float = 8.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = get_state()
        if s["phase"] in phases:
            return s
        time.sleep(0.05)
    raise AssertionError(
        f"API timed out waiting for {phases!r}; current phase: {get_state()['phase']!r}"
    )


def wait_for_phase_ui(page: Page, phase: str, timeout: int = 6_000) -> None:
    """Block until #scene-<phase> carries the 'active' class.

    Times out and fails the test if the scene element never appears — this is
    the primary mechanism that catches missing scene templates.
    """
    page.wait_for_function(
        f"document.getElementById('scene-{phase}')?.classList.contains('active')",
        timeout=timeout,
    )


def cast_vote_api(player_id: str) -> None:
    """Vote for the first answer available to this player (API-only)."""
    answers = get_state()["current_turn"]["answers"]
    for a in answers:
        r = api("POST", "/api/game/vote", json={"player_id": player_id, "answer_id": a["answer_id"]})
        if r.status_code == 200:
            return
    raise AssertionError(f"No valid answer to vote on for player {player_id!r}")


def cast_like_api(player_id: str) -> None:
    answers = get_state()["current_turn"]["answers"]
    for a in answers:
        r = api("POST", "/api/game/like", json={"player_id": player_id, "answer_id": a["answer_id"]})
        if r.status_code == 200:
            return


def join_via_browser(page: Page, name: str = "Alice") -> str:
    """Drive the onboarding form and return the player_id stored in localStorage."""
    page.locator("#name-input").fill(name)
    page.locator("#join-btn").click()
    expect(page.locator("#scene-lobby")).to_have_class(re.compile(r"\bactive\b"))
    player_id = page.evaluate(
        "JSON.parse(localStorage.getItem('lieability_player')).player_id"
    )
    return player_id


# ------------------------------------------------------------------
# Fixture
# ------------------------------------------------------------------

@pytest.fixture()
def player_page(live_server, browser):
    """Fresh browser context pointed at /player/ with clean localStorage."""
    context = browser.new_context()
    p = context.new_page()
    p.goto(f"{live_server}/player/")
    yield p
    context.close()


# ------------------------------------------------------------------
# Tests — Onboarding (currently implemented)
# ------------------------------------------------------------------

def test_onboarding_initial_render(player_page: Page) -> None:
    """Join form is shown on fresh load; join button is disabled."""
    expect(player_page.locator("#scene-onboarding")).to_have_class(re.compile(r"\bactive\b"))
    expect(player_page.locator("#scene-lobby")).not_to_have_class(re.compile(r"\bactive\b"))
    expect(player_page.locator("#join-btn")).to_be_disabled()
    expect(player_page.locator("#emoji-grid .emoji-btn")).to_have_count(12)
    expect(player_page.locator("#color-grid .color-swatch")).to_have_count(8)
    expect(player_page.locator("#emoji-grid .emoji-btn.selected")).to_have_count(1)
    expect(player_page.locator("#color-grid .color-swatch.selected")).to_have_count(1)


def test_onboarding_join_button_enables_on_name(player_page: Page) -> None:
    """Join button enables when name has content and disables when cleared."""
    page = player_page
    expect(page.locator("#join-btn")).to_be_disabled()
    page.locator("#name-input").fill("Alice")
    expect(page.locator("#join-btn")).to_be_enabled()
    page.locator("#name-input").fill("")
    expect(page.locator("#join-btn")).to_be_disabled()


def test_onboarding_join_flow(player_page: Page) -> None:
    """Submitting the form transitions to lobby and stores player_id."""
    page = player_page
    page.locator("#name-input").fill("Alice")
    page.locator("#join-btn").click()

    expect(page.locator("#scene-lobby")).to_have_class(re.compile(r"\bactive\b"))
    expect(page.locator("#scene-onboarding")).not_to_have_class(re.compile(r"\bactive\b"))

    stored = page.evaluate("localStorage.getItem('lieability_player')")
    assert stored, "player data should be saved to localStorage"
    import json
    data = json.loads(stored)
    assert data.get("player_id"), "player_id should be in localStorage"
    assert data.get("name") == "Alice"


def test_onboarding_error_on_game_in_progress(player_page: Page) -> None:
    """Joining while a game is active shows an error in #join-error."""
    bob = add_player("Bob")
    carol = add_player("Carol")
    api("POST", "/api/game/start", json={})

    page = player_page
    page.locator("#name-input").fill("Dave")
    page.locator("#join-btn").click()

    expect(page.locator("#join-error")).to_be_visible()
    expect(page.locator("#scene-onboarding")).to_have_class(re.compile(r"\bactive\b"))


# ------------------------------------------------------------------
# Tests — Lobby (currently implemented)
# ------------------------------------------------------------------

def test_lobby_shows_player_card(player_page: Page) -> None:
    """After joining, player card shows the correct name and avatar."""
    page = player_page
    page.locator("#name-input").fill("Alice")
    # Pick the second emoji (index 1 = 🎭) and second color
    page.locator("#emoji-grid .emoji-btn").nth(1).click()
    page.locator("#color-grid .color-swatch").nth(1).click()
    page.locator("#join-btn").click()

    expect(page.locator("#scene-lobby")).to_have_class(re.compile(r"\bactive\b"))
    expect(page.locator("#player-info")).to_contain_text("Alice")
    # Avatar should carry the chosen background color (second color = #e67e22)
    avatar = page.locator("#player-info .avatar")
    expect(avatar).to_have_attribute("style", re.compile(r"background.*#e67e22", re.IGNORECASE))


def test_lobby_waiting_message(player_page: Page) -> None:
    """Lobby shows a 'waiting for host' message."""
    join_via_browser(player_page)
    expect(player_page.locator(".wait-text")).to_be_visible()
    expect(player_page.locator(".wait-text")).to_contain_text(
        re.compile(r"wait|host|start", re.IGNORECASE)
    )


def test_lobby_edit_toggle(player_page: Page) -> None:
    """Edit form is hidden by default; toggle button shows/hides it."""
    page = player_page
    join_via_browser(page)

    expect(page.locator("#edit-form")).to_have_attribute("hidden", "")
    page.locator("#edit-toggle-btn").click()
    expect(page.locator("#edit-form")).not_to_have_attribute("hidden", "")
    expect(page.locator("#edit-toggle-btn")).to_have_text("Cancel")

    page.locator("#edit-toggle-btn").click()
    expect(page.locator("#edit-form")).to_have_attribute("hidden", "")
    expect(page.locator("#edit-toggle-btn")).to_have_text("Edit")


def test_lobby_edit_save(player_page: Page) -> None:
    """Saving a new name in the edit form updates the player card."""
    page = player_page
    join_via_browser(page, name="Alice")

    page.locator("#edit-toggle-btn").click()
    page.locator("#edit-name").fill("Alice Updated")
    page.locator("#edit-save-btn").click()

    # Edit form should close and card should reflect new name
    expect(page.locator("#player-info")).to_contain_text("Alice Updated")
    # Form should be closed after a successful save
    expect(page.locator("#edit-form")).to_have_attribute("hidden", "")


# ------------------------------------------------------------------
# Tests — In-game phases (unconditional; fail until scenes are built)
# ------------------------------------------------------------------

def test_phase_category_pick_as_picker(player_page: Page) -> None:
    """Alice (first joiner = picker) sees category buttons in the pick scene."""
    page = player_page
    alice_id = join_via_browser(page)
    add_player("Bob")
    api("POST", "/api/game/start", json={})

    wait_for_phase_ui(page, "category_pick")
    expect(page.locator("#scene-category_pick")).to_have_class(re.compile(r"\bactive\b"))

    # Category buttons must be present for the picker
    cats = page.locator("[data-category-id]")
    expect(cats).not_to_have_count(0)

    # Clicking the first category advances to lie_submission
    cats.first.click()
    wait_for_phase_ui(page, "lie_submission")


def test_phase_category_pick_as_waiter(player_page: Page) -> None:
    """Alice (second joiner = waiter) sees a waiting message while Bob picks."""
    bob_id = add_player("Bob")
    page = player_page
    join_via_browser(page)
    api("POST", "/api/game/start", json={})

    wait_for_phase_ui(page, "category_pick")
    expect(page.locator("#scene-category_pick")).to_have_class(re.compile(r"\bactive\b"))

    # Alice is NOT the picker — no category buttons, only a waiting indicator
    expect(page.locator("[data-category-id]")).to_have_count(0)
    expect(page.locator("#scene-category_pick")).to_contain_text(
        re.compile(r"wait|bob|picking", re.IGNORECASE)
    )

    # Bob picks via API → Alice advances to lie_submission
    cats = api("GET", "/api/categories").json()
    api("POST", "/api/game/category", json={"player_id": bob_id, "category_id": cats[0]["id"]})
    wait_for_phase_ui(page, "lie_submission")


def _setup_to_lie_submission(page: Page) -> tuple[str, str]:
    """Join Alice (browser, picker) + Bob (API), start, pick category. Returns IDs."""
    alice_id = join_via_browser(page)
    bob_id = add_player("Bob")
    api("POST", "/api/game/start", json={})

    wait_for_phase_ui(page, "category_pick")
    # Alice is the picker — click first category button
    page.locator("[data-category-id]").first.click()
    wait_for_phase_ui(page, "lie_submission")
    return alice_id, bob_id


def test_phase_lie_submission(player_page: Page) -> None:
    """Lie submission scene has a text input; submitting disables re-submission."""
    page = player_page
    alice_id, bob_id = _setup_to_lie_submission(page)

    expect(page.locator("#scene-lie_submission")).to_have_class(re.compile(r"\bactive\b"))

    s = get_state()
    prompt = s["current_turn"]["question_prompt"]
    expect(page.locator("#scene-lie_submission")).to_contain_text(prompt)

    lie_input = page.locator("#lie-input")
    expect(lie_input).to_be_visible()
    expect(lie_input).to_be_empty()

    submit_btn = page.locator("#submit-lie-btn")
    lie_input.fill("My very plausible lie")
    submit_btn.click()

    # After submit the input/button should reflect a submitted state
    expect(submit_btn).to_be_disabled()


def test_phase_voting(player_page: Page) -> None:
    """Voting scene lists answers; after voting, like buttons appear immediately."""
    page = player_page
    alice_id, bob_id = _setup_to_lie_submission(page)

    page.locator("#lie-input").fill("Alice lie")
    page.locator("#submit-lie-btn").click()
    api("POST", "/api/game/lie", json={"player_id": bob_id, "text": "Bob lie"})

    wait_for_phase_ui(page, "voting")
    expect(page.locator("#scene-voting")).to_have_class(re.compile(r"\bactive\b"))

    answer_btns = page.locator("[data-answer-id]")
    expect(answer_btns).to_have_count(3)  # 2 lies + 1 truth

    answer_btns.first.click()
    expect(page.locator("#scene-voting")).to_contain_text(
        re.compile(r"like another submission|you voted", re.IGNORECASE)
    )
    expect(page.locator("#scene-voting [data-like-id], #scene-voting .like-btn")).not_to_have_count(0)


def test_phase_likes(player_page: Page) -> None:
    """Likes scene shows answers with vote counts; clicking a like registers it."""
    page = player_page
    alice_id, bob_id = _setup_to_lie_submission(page)

    page.locator("#lie-input").fill("Alice lie")
    page.locator("#submit-lie-btn").click()
    api("POST", "/api/game/lie", json={"player_id": bob_id, "text": "Bob lie"})

    wait_for_phase_ui(page, "voting")
    # Alice votes via browser
    page.locator("[data-answer-id]").first.click()
    cast_vote_api(bob_id)

    wait_for_phase_ui(page, "likes")
    expect(page.locator("#scene-likes")).to_have_class(re.compile(r"\bactive\b"))

    # Answers with vote counts visible
    expect(page.locator("[data-vote-count]")).not_to_have_count(0)

    # Click a like button (first available)
    like_btn = page.locator("[data-like-id], .like-btn").first
    like_btn.click()
    # Button should reflect liked state
    expect(like_btn).to_have_class(re.compile(r"liked|selected|active"))


def test_phase_round_results(player_page: Page) -> None:
    """Round-results scene reveals the real answer and shows Alice's score change."""
    page = player_page
    alice_id, bob_id = _setup_to_lie_submission(page)

    page.locator("#lie-input").fill("Alice lie")
    page.locator("#submit-lie-btn").click()
    api("POST", "/api/game/lie", json={"player_id": bob_id, "text": "Bob lie"})

    wait_for_phase_ui(page, "voting")
    page.locator("[data-answer-id]").first.click()
    cast_vote_api(bob_id)

    wait_for_phase_ui(page, "likes")
    cast_like_api(alice_id)
    cast_like_api(bob_id)

    wait_for_phase_ui(page, "round_results")
    expect(page.locator("#scene-round_results")).to_have_class(re.compile(r"\bactive\b"))

    s = get_state()
    real_answer = s["current_turn"]["real_answer_text"]
    expect(page.locator("#scene-round_results")).to_contain_text(real_answer)

    # Score change for Alice must be shown (even if 0 pts)
    expect(page.locator("[data-score-change]")).to_be_visible()


def test_phase_game_over(player_page: Page) -> None:
    """Game-over scene shows both players' final scores."""
    page = player_page
    alice_id, bob_id = _setup_to_lie_submission(page)

    page.locator("#lie-input").fill("Alice lie")
    page.locator("#submit-lie-btn").click()
    api("POST", "/api/game/lie", json={"player_id": bob_id, "text": "Bob lie"})

    wait_for_phase_ui(page, "voting")
    page.locator("[data-answer-id]").first.click()
    cast_vote_api(bob_id)

    wait_for_phase_ui(page, "likes")
    cast_like_api(alice_id)
    cast_like_api(bob_id)

    # round_results auto-advances to game_over after UI_TIMEOUTS["round_results"] (2 s)
    wait_for_phase_api("game_over", timeout=10.0)
    wait_for_phase_ui(page, "game_over", timeout=8_000)

    expect(page.locator("#scene-game_over")).to_have_class(re.compile(r"\bactive\b"))
    expect(page.locator("#scene-lobby")).not_to_have_class(re.compile(r"\bactive\b"))

    scene = page.locator("#scene-game_over")
    expect(scene).to_contain_text("Alice")
    expect(scene).to_contain_text("Bob")

    s = get_state()
    assert all(p["score"] >= 0 for p in s["final_scores"])
