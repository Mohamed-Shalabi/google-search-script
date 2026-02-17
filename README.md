# Google Search Automation & CAPTCHA Solver

Automate Google searches and solve reCAPTCHA challenges using Playwright and Claude Desktop.

## Demo

[Demo Video](https://youtu.be/ywk6dsA1G8M)

## Tools

- **Playwright**: Browser automation and CAPTCHA rendering.
- **PyAutoGUI**: macOS "Hands" for interacting with the Claude app.
- **Tesseract OCR**: Extracting Claude's text-based solutions.
- **Pillow**: Image processing for screenshots.
- **Pyperclip**: Clipboard management for prompt injection.

## Prerequisites

- **macOS**: Required for AppleScript and Claude Desktop automation.
- **Claude Desktop**: Installed and logged in.
- **Tesseract OCR**: Installed via Homebrew:
  ```bash
  brew install tesseract
  ```
- **Python 3.13+**: The project is built with modern Python features.

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd google-search-automation
   ```

2. **Set up the environment**:
   Using `uv` (recommended):
   ```bash
   uv venv
   source .venv/bin/activate
   uv sync
   ```
   Or using `pip`:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Install Playwright Browsers**:
   ```bash
   playwright install chromium
   ```

## Usage

Run the automation script:
```bash
python main.py
```

## How it Works

The script follows a "Brain & Hands" architecture:
1. **Hands (Playwright)**: Navigates Google, detects CAPTCHAs, and takes screenshots of challenges.
2. **Bridge (macOS Automation)**: Copies screenshots to the clipboard and opens Claude Desktop.
3. **Brain (Claude Desktop)**: Receives the screenshot and instructions, identifies the correct tiles, and provides a response.
4. **OCR (Tesseract)**: Reads Claude's response from the screen to determine which tiles to click in the browser.
