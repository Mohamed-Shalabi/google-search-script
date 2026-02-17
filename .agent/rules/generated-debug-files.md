---
trigger: always_on
---

If you need to create any file just for debugging purposes, put them at `/debug` directory, and delete them when you finish debugging and they are no longer needed

Example: You need to debug an issue in `main.py` without modifying `main.py`. So, you decided to create a new file (for example, debug_main.py). Then, you must create it at `debug/debug_main.py`. And then, after resolving the issue, delete the file.