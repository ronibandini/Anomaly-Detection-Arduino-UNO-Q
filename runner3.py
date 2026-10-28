#!/usr/bin/env python3
# Anomaly Detection with Arduino UNO Q
# Roni Bandini @RoniBandini
# October 2026
# GPL-3.0 license

import json
import os
import subprocess
import sys
from datetime import datetime

import requests

CONFIDENCE_THRESHOLD = 8.0
WEBHOOK_URL = ""
LOG_FILE = "output.txt"
RUNNER_COMMAND = ["edge-impulse-linux-runner"]


class Console:

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"

    def __init__(self):
        self.use_color = sys.stdout.isatty()

    def paint(self, text, color):
        if not self.use_color:
            return text
        return f"{color}{text}{self.RESET}"

    def banner(self):
        width = 68
        print(self.paint("┌" + "─" * width + "┐", self.CYAN))
        print(self.paint(f"│ {'DETECCION DE ANOMALIAS CON UNO Q Y EDGE IMPULSE':<{width - 2}} │", self.BOLD + self.CYAN))
        print(self.paint(f"│ {'Roni Bandini, Nerdearla MX 2026':<{width - 2}} │", self.CYAN))
        print(self.paint("└" + "─" * width + "┘", self.CYAN))
        print()

    def event(self, tag, message, color=None):
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag_text = f"{tag:<8}"
        if color:
            tag_text = self.paint(tag_text, color)
        print(f"{self.paint(timestamp, self.DIM)}  {tag_text} {message}", flush=True)


console = Console()


def extract_json_array(line):
    decoder = json.JSONDecoder()
    for index, character in enumerate(line):
        if character != "[":
            continue
        try:
            value, _ = decoder.raw_decode(line[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            return value
    return None


def format_number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def display_anomaly_matrix(anomalies):
    cells = []
    for item in anomalies:
        if not isinstance(item, dict):
            continue
        try:
            x_source = item["x"]
            y_source = item["y"]
            width_source = item["width"]
            height_source = item["height"]
            value_source = item["value"]
            x_number = float(x_source)
            y_number = float(y_source)
            width_number = float(width_source)
            height_number = float(height_source)
            value_number = float(value_source)
        except (KeyError, TypeError, ValueError):
            continue

        if width_number <= 0 or height_number <= 0:
            continue

        cells.append({
            "x": x_source,
            "y": y_source,
            "x_number": x_number,
            "y_number": y_number,
            "width": width_source,
            "height": height_source,
            "value": value_source,
            "value_number": value_number,
            "label": str(item.get("label", "anomaly")),
        })

    if not cells:
        return


    x_positions = sorted({cell["x_number"] for cell in cells})
    y_positions = sorted({cell["y_number"] for cell in cells})
    occupied = {(cell["y_number"], cell["x_number"]) for cell in cells}
    peak_cell = max(cells, key=lambda cell: cell["value_number"])

    cell_width = 3
    border = "+" + "+".join("-" * cell_width for _ in x_positions) + "+"
    console.event(
        "MATRIX",
        f"Reported anomaly cells: {len(cells)}; grid: {len(y_positions)} × {len(x_positions)}",
        Console.CYAN,
    )
    print("        X = reported anomaly; blank = no record at that matrix position.")
    print("        " + border)

    for y in y_positions:
        row = "|" + "|".join(
            f"{' X ' if (y, x) in occupied else '   '}" for x in x_positions
        ) + "|"
        print("        " + row)

    print("        " + border)
    print(
        "        Highest value: {} at x={}, y={} (size={}×{}, label={})".format(
            peak_cell["value"], peak_cell["x"], peak_cell["y"],
            peak_cell["width"], peak_cell["height"], peak_cell["label"]
        )
    )


def display_anomaly(anomaly, state, compact=False):
    try:
        confidence_value = anomaly["value"]
        confidence = float(confidence_value)
    except (KeyError, TypeError, ValueError) as exc:
        console.event("WARNING", f"Skipping result with invalid confidence value: {exc}", Console.YELLOW)
        return

    state["detection_count"] += 1
    state["idle_reported"] = False

    label = str(anomaly.get("label", "anomaly"))
    x = anomaly.get("x", "?")
    y = anomaly.get("y", "?")
    width = anomaly.get("width", "?")
    height = anomaly.get("height", "?")

    if not compact:
        console.event("DETECT", f"#{state['detection_count']:04d}  {label}", Console.CYAN)
        print(f"           Confidence : {confidence:.2f}  (threshold {CONFIDENCE_THRESHOLD:.2f})")
        print(f"           Position   : x={x}, y={y}")
        print(f"           Size       : {width} × {height}")

    if confidence < CONFIDENCE_THRESHOLD:
        if not compact:
            console.event("STATUS", "Below trigger threshold.", Console.DIM)
        return

    if not WEBHOOK_URL.strip():
        if not state.get("webhook_disabled_warned"):
            console.event(
                "STATUS",
                f"Threshold reached at x={x}, y={y}; webhook URL is not configured.",
                Console.YELLOW,
            )
            state["webhook_disabled_warned"] = True
        return

    console.event("WEBHOOK", f"Sending event at x={x}, y={y}…", Console.YELLOW)
    try:
        payload = {
            "label": label,
            "confidence": confidence_value,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }
        response = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        body = " ".join(response.text.split())
        if len(body) > 180:
            body = body[:177] + "..."
        color = Console.GREEN if response.ok else Console.RED
        console.event(
            "WEBHOOK",
            f"HTTP {response.status_code} at x={x}, y={y}" + (f" — {body}" if body else ""),
            color,
        )
    except requests.RequestException as exc:
        console.event("ERROR", f"Webhook request failed: {exc}", Console.RED)
    except KeyError as exc:
        console.event("ERROR", f"Cannot build webhook payload; missing field {exc}.", Console.RED)


def process_runner_line(line, state):
    if "[]" in line:
        if not state["idle_reported"]:
            console.event("IDLE", "No detection.", Console.DIM)
            state["idle_reported"] = True
        return

    lowered = line.lower()
    if "height" not in lowered or "anomaly" not in lowered:
        return

    anomalies = extract_json_array(line)
    if anomalies is None:
        console.event("WARNING", "Could not parse the anomaly result as a JSON array.", Console.YELLOW)
        return

    if not anomalies:
        if not state["idle_reported"]:
            console.event("IDLE", "No detection.", Console.DIM)
            state["idle_reported"] = True
        return

    display_anomaly_matrix(anomalies)
    compact = len(anomalies) > 1
    for anomaly in anomalies:
        if isinstance(anomaly, dict):
            display_anomaly(anomaly, state, compact=compact)


def clear_screen():
    """Clear an interactive terminal without emitting escapes into redirected output."""
    if not sys.stdout.isatty():
        return
    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[2J\033[H", end="", flush=True)


def main():
    clear_screen()
    console.banner()
    console.event("CONFIG", f"Confidence threshold : {CONFIDENCE_THRESHOLD:.2f}")
    webhook_status = "configured" if WEBHOOK_URL.strip() else "disabled (URL not set)"
    console.event("CONFIG", f"Webhook              : {webhook_status}")
    console.event("LOG", f"Runner output        : {LOG_FILE}")
    console.event("INFO", "Press Ctrl+C to stop.")

    process = None
    state = {"detection_count": 0, "idle_reported": False}

    try:
        process = subprocess.Popen(
            RUNNER_COMMAND,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        console.event("RUNNER", "Edge Impulse runner started.", Console.GREEN)

        with open(LOG_FILE, "w", encoding="utf-8", buffering=1) as log_file:
            assert process.stdout is not None
            for line in process.stdout:
                log_file.write(line)
                process_runner_line(line, state)

        return_code = process.wait()
        if return_code != 0:
            console.event("ERROR", f"Runner exited with code {return_code}. See {LOG_FILE}.", Console.RED)
            return return_code

        console.event("INFO", "Runner finished.")
        return 0

    except FileNotFoundError:
        console.event("ERROR", "edge-impulse-linux-runner was not found. Check that it is installed and on PATH.", Console.RED)
        return 127
    except KeyboardInterrupt:
        print()
        console.event("STOP", "Shutdown requested.", Console.YELLOW)
        return 130
    except OSError as exc:
        console.event("ERROR", f"Could not start or read the runner: {exc}", Console.RED)
        return 1
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if process.stdout is not None:
                process.stdout.close()


if __name__ == "__main__":
    raise SystemExit(main())
