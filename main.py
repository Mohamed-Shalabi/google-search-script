import json
import re
import subprocess
import tempfile
from pathlib import Path
from time import sleep
from typing import Final

import pyautogui
import pyperclip
import pytesseract  # pyright: ignore[reportMissingTypeStubs]
from PIL import Image
from playwright.sync_api import FrameLocator, Page, sync_playwright

MAX_CAPTCHA_ATTEMPTS: Final[int] = 10
CLAUDE_RESPONSE_WAIT_SECONDS: Final[int] = 10


def copy_image_to_clipboard(image_bytes: bytes) -> None:
    """Save screenshot bytes to a temp file and copy the image to macOS clipboard."""
    tmp_path: str = str(Path(tempfile.gettempdir()) / "captcha_screenshot.png")
    with open(tmp_path, "wb") as f:
        f.write(image_bytes)

    applescript: str = (
        f'set the clipboard to (read (POSIX file "{tmp_path}") as «class PNGf»)'
    )
    subprocess.run(["osascript", "-e", applescript], check=True)
    print(f"  Copied captcha image to clipboard ({len(image_bytes)} bytes)")


def open_claude_app() -> None:
    """Open Claude Desktop via Spotlight and prepare a new maximized chat."""
    # Open Spotlight
    pyautogui.hotkey("command", "space")
    sleep(2)

    # Type "claude" and launch
    pyautogui.typewrite("claude", interval=0.05)
    pyautogui.press("enter")
    sleep(2)

    # New chat: Cmd+Shift+O
    pyautogui.hotkey("command", "shift", "o")
    sleep(2)

    # Maximize window: Option+Ctrl+Return
    pyautogui.hotkey("option", "ctrl", "return")
    sleep(0.5)

    print("  Claude app opened with new chat (maximized)")


def send_prompt_to_claude(instruction_text: str) -> None:
    """Paste the captcha image and type the solving prompt into Claude."""
    # Paste the image from clipboard
    pyautogui.hotkey("command", "v")
    sleep(1)

    prompt: str = (
        f"You are an expert at solving reCAPTCHA image challenges.\n\n"
        f'CHALLENGE INSTRUCTION: "{instruction_text.replace(chr(10), " ").strip()}"\n\n'
        f"GRID LAYOUT:\n"
        f"- The image shows a grid of tiles (either 3x3 = 9 tiles, or 4x4 = 16 tiles)\n"
        f"- Tiles are numbered left-to-right, top-to-bottom, starting from 0\n"
        f"- 3x3 grid: Row 1: [0,1,2], Row 2: [3,4,5], Row 3: [6,7,8]\n"
        f"- 4x4 grid: Row 1: [0,1,2,3], Row 2: [4,5,6,7], Row 3: [8,9,10,11], Row 4: [12,13,14,15]\n\n"
        f"CRITICAL INSTRUCTIONS:\n"
        f"1. Look at EVERY tile carefully - examine each one individually\n"
        f"2. Select ALL tiles that contain the target object, even if:\n"
        f"   - Only a small part of the object is visible\n"
        f"   - The object is partially cut off at the edge\n"
        f"   - The object is in the background or blurry\n"
        f"   - You can only see a corner, edge, or small portion\n"
        f"3. Common objects to recognize:\n"
        f"   - Vehicles: cars, buses, motorcycles, bicycles, boats, trucks\n"
        f"   - Infrastructure: traffic lights, crosswalks (zebra stripes), bridges, fire hydrants, parking meters\n"
        f"   - Nature: trees, mountains, water, sky\n"
        f"4. DO NOT select tiles if:\n"
        f"   - The object is only mentioned in text/signs\n"
        f"   - It's a drawing/painting of the object (unless that counts)\n"
        f"   - You're genuinely unsure (be conservative only when truly ambiguous)\n"
        f"5. If the instruction says 'If there are none, click skip' and you find NO matching tiles, return empty array\n\n"
        f"RESPONSE FORMAT:\n"
        f"Return ONLY this exact format: RES: [0, 3, 6]\n"
        f"If no tiles match: RES: []\n"
        f"Do not include any explanation, reasoning, or other text - ONLY the RES: [...] line."
    )

    # Paste the prompt from clipboard
    pyperclip.copy(prompt)
    sleep(1)
    pyautogui.hotkey("command", "v")
    sleep(1)

    # Submit
    pyautogui.press("enter")
    print(
        f"  Prompt sent to Claude, waiting {CLAUDE_RESPONSE_WAIT_SECONDS}s for response..."
    )
    sleep(CLAUDE_RESPONSE_WAIT_SECONDS)


def extract_response_from_claude() -> list[int]:
    """Take a screenshot of Claude's window, OCR it, and extract the tile indices."""
    screenshot: Image.Image = pyautogui.screenshot()  # type: ignore[reportUnknownMemberType]

    # OCR the screenshot
    ocr_text: str = pytesseract.image_to_string(screenshot)  # type: ignore[reportUnknownMemberType]
    print(f"  OCR extracted text (last 300 chars): ...{ocr_text[-300:]}")

    # Search for the RES: [indices] pattern
    # Handles: RES:[1,2], RES: [1, 2], RES:[ ], RES: []
    # If multiple matches, take the last one (most recent response)
    matches: list[str] = re.findall(
        r"RES:?\s*(\[[\d,\s]*\])", ocr_text, re.DOTALL | re.IGNORECASE
    )

    if matches:
        last_json: str = matches[-1]
        try:
            indices: list[object] = json.loads(last_json)
            result: list[int] = [int(i) for i in indices]  # pyright: ignore[reportArgumentType]
            print(f"  Extracted indices (from last match): {result}")
            pyautogui.hotkey("command", "w")
            sleep(1)
            return result
        except json.JSONDecodeError:
            print(f"  Failed to parse JSON from last match: {last_json}")

    print("  Could not extract RES pattern from OCR text")
    pyautogui.hotkey("command", "w")
    return []


def ask_claude_to_solve(screenshot_bytes: bytes, instruction_text: str) -> list[int]:
    """Orchestrate the full Claude Desktop solving workflow."""
    copy_image_to_clipboard(screenshot_bytes)
    open_claude_app()
    send_prompt_to_claude(instruction_text)
    return extract_response_from_claude()


def extract_instruction_text(challenge_frame: FrameLocator) -> str:
    """Extract the captcha instruction text from the challenge iframe."""
    try:
        instruction_el = challenge_frame.locator(".rc-imageselect-instructions")
        instruction_text: str = instruction_el.inner_text(timeout=3000)
        return instruction_text.strip()
    except Exception:
        return "Select all matching images"


def solve_captcha_with_claude(page: Page) -> bool:
    """Main loop: solve captcha challenges until search results appear."""
    for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
        print(f"\n--- Captcha attempt {attempt}/{MAX_CAPTCHA_ATTEMPTS} ---")

        # Wait for the challenge to render
        sleep(1)

        # Find the challenge iframe
        try:
            # Wait for any iframe that looks like the challenge (bframe)
            challenge_iframe_el = page.wait_for_selector(
                'iframe[src*="bframe"]', timeout=5000
            )
        except Exception:
            print(
                "  No captcha challenge iframe found (bframe). Might be solved already."
            )
            return True

        if not challenge_iframe_el:
            print("  No captcha challenge iframe found.")
            return True

        challenge_frame: FrameLocator = page.frame_locator('iframe[src*="bframe"]')

        # Extract the instruction text
        instruction_text: str = extract_instruction_text(challenge_frame)
        print(f"  Instruction: {instruction_text}")

        # Take a screenshot of the captcha challenge iframe
        screenshot_bytes: bytes = challenge_iframe_el.screenshot(type="png")
        print(f"  Screenshot taken ({len(screenshot_bytes)} bytes)")

        # Ask Claude to solve it
        indices: list[int] = ask_claude_to_solve(screenshot_bytes, instruction_text)
        print(f"  Tiles to click: {indices}")

        if not indices:
            print("  Claude returned no matching tiles. Clicking verify anyway...")
        else:
            # Click the matching tiles
            # Debug: dump HTML to see the structure if we fail
            tiles = challenge_frame.locator("table.rc-imageselect-table td")

            # If standard selector fails, try others
            if tiles.count() == 0:
                print(
                    "  Selector 'table.rc-imageselect-table td' found 0 tiles. Trying '.rc-imageselect-tile'..."
                )
                tiles = challenge_frame.locator(".rc-imageselect-tile")

            if tiles.count() == 0:
                print(
                    "  Still found 0 tiles. Dumping HTML to debug_captcha_frame.html..."
                )
                try:
                    with open("debug_captcha_frame.html", "w", encoding="utf-8") as f:
                        f.write(challenge_frame.locator("body").inner_html())
                except Exception as e:
                    print(f"  Failed to dump HTML: {e}")

                print("  No tiles found with known selectors.")
                return False

            print(f"  Found {tiles.count()} tiles")

            for idx in indices:
                try:
                    tiles.nth(idx).click()
                    print(f"  Clicked tile {idx}")
                    sleep(0.3)  # Small delay between clicks
                except Exception as e:
                    print(f"  Failed to click tile {idx}: {e}")

        # Wait for any tile replacement animations
        sleep(1)

        # Click the verify button
        try:
            verify_btn = challenge_frame.locator("#recaptcha-verify-button")
            verify_btn.click()
            print("  Clicked Verify button")
        except Exception as e:
            print(f"  Failed to click Verify: {e}")

        # Wait a moment for the result
        sleep(2)

        # Check if captcha is gone (search results loaded)
        try:
            page.wait_for_selector('iframe[src*="bframe"]', timeout=3000)
            # If we reach here, the challenge iframe is still present → loop again
            print("  Captcha still present, retrying...")
        except Exception:
            print("  Captcha challenge gone! Checking for search results...")
            return True

    print(f"\nMax attempts ({MAX_CAPTCHA_ATTEMPTS}) reached.")
    return False


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        _ = page.goto("https://www.google.com")
        page.fill('textarea[name="q"]', "flutter automation")
        page.press('textarea[name="q"]', "Enter")

        # Check for reCAPTCHA
        try:
            captcha_iframe = page.wait_for_selector(
                'iframe[title="reCAPTCHA"]', timeout=5000
            )
            if captcha_iframe:
                print("CAPTCHA detected, clicking 'I'm not a robot'...")
                page.frame_locator('iframe[title="reCAPTCHA"]').locator(
                    "#recaptcha-anchor"
                ).click()

                # Wait for the challenge to appear after clicking checkbox
                page.wait_for_load_state("networkidle")

                # Solve the captcha challenge
                solved: bool = solve_captcha_with_claude(page)
                if solved:
                    print("\nCaptcha solved successfully!")
                else:
                    print("\nFailed to solve captcha after max attempts.")

        except Exception as e:
            print(f"No CAPTCHA detected or timed out waiting for it: {e}")

            page.wait_for_load_state("networkidle")
            print(f"\nPage title: {page.title()}")
            sleep(1000)
            browser.close()


if __name__ == "__main__":
    main()
