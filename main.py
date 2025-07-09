import subprocess
import time
import curses
import sys
import re
import json
import threading


class VLCController:
    def __init__(self, output_name):
        self.output_name = output_name

        self.process = None

        self.components = {
            "Natural language": ["Prompt contains natural language", curses.COLOR_CYAN],
            "Source code": ["Prompt contains sourcs code", curses.COLOR_GREEN],
            "Tool output": [
                "Prompt contains output from the tool (e.g. counter-examples or compiler output)",
                curses.COLOR_YELLOW,
            ],
            "Category: Context specification": [
                "specify the context, explaining the meaning of one or more symbols, words, or statements to the LLM so it uses the provided information for output generation.",
                curses.COLOR_BLUE,
            ],
            "Category: Flipped Interaction": [
                "let the LLM to ask questions to obtain the information it needs to perform some tasks. Rather than the user driving the conversation, you want the LLM to drive the conversation to focus it on achieving a specific goal.",
                curses.COLOR_MAGENTA,
            ],
            "Category: Persona": [
                "give the LLM a persona or role to play when generating output. The intent of this pattern is to give the LLM a “persona” that helps it select what types of output to generate and what details to focus on.",
                curses.COLOR_RED,
            ],
            "Category: Template": [
                "ensure an LLM’s output follows a precise template in terms of structure. (for example, in Diff-style)",
                curses.COLOR_WHITE,
            ],
            "Category: Infinite generation": [
                "let LLM generate a series of outputs (which may appear infinite) without having to reenter the generator prompt each time.",
                curses.COLOR_CYAN,
            ],
            "Category: Reflection": [
                "ask the model to automatically explain the rationale behind given answers to the user. Users can gain a better understanding of how the model is processing the input, what assumptions it is making, and what data it is drawing on.",
                curses.COLOR_GREEN,
            ],
        }

    def getch(self):
        """Get a single character using curses"""

        def _getch(stdscr):
            stdscr.nodelay(True)  # Non-blocking mode
            curses.curs_set(0)  # Hide cursor
            key = stdscr.getch()
            if key == -1:  # No key pressed
                return None
            return chr(key) if 32 <= key <= 126 else chr(key).lower()

        return curses.wrapper(_getch)

    def start_vlc(self):
        # Start VLC process with RC interface and GUI
        self.process = subprocess.Popen(
            ["vlc", "--extraintf", "rc"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True,
        )

        time.sleep(1)

        # Skip two welcome lines
        for _ in range(2):
            self.process.stdout.readline()

    def readln(self):
        s = self.process.stdout.readline().strip()
        # VLC prints the prompt welcome sequence "> " before each command
        # and we need to remove it
        s = re.sub("^(> )*", "", s)
        return s

    def send_command(self, command):
        if self.process.stdin:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()

    def add(self, video_path):
        self.send_command(f"add {video_path}")

    def play(self):
        self.send_command("play")

    def pause(self):
        self.send_command("pause")

    def get_time(self):
        self.send_command("get_time")
        return self.readln()

    def write_category_help(self, line_cursor_nr: int, stdscr):
        # Initialize color pairs if not already done
        curses.start_color()

        # Dynamically iterate over self.components to display categories and descriptions
        for idx, (category, details) in enumerate(self.components.items()):
            description, color = details
            curses.init_pair(idx + 1, color, curses.COLOR_BLACK)
            stdscr.addstr(
                line_cursor_nr + idx,
                0,
                f"{category}: ",
                curses.A_BOLD | curses.color_pair(idx + 1),
            )
            stdscr.addstr(
                line_cursor_nr + idx,
                len(f"{category}: "),
                description,
            )

    def display_comments(self, stdscr):
        line_cursor = 0
        curses.curs_set(0)  # Hide the cursor
        stdscr.clear()
        stdscr.addstr(
            line_cursor, 0, "Select a comment (press the corresponding number):"
        )
        line_cursor += 1

        for idx, comment in enumerate(self.components):
            _, color = self.components[comment]
            curses.init_pair(idx + 1, color, curses.COLOR_BLACK)
            stdscr.addstr(
                line_cursor, 0, f"{line_cursor}. {comment}", curses.color_pair(idx + 1)
            )
            line_cursor += 1

        stdscr.addstr(line_cursor, 0, "Press Enter to confirm selection.")
        line_cursor += 2

        p_string = lambda x: json.dumps(
            sorted(list(x))
        )  # Pretty string of the selected comments

        self.write_category_help(line_cursor + 5, stdscr)
        result = None
        selected_comments = set()
        stdscr.refresh()
        while True:
            key = stdscr.getch()
            if key in range(ord("1"), ord("1") + len(self.components)):
                # Get the corresponding component key from the dictionary
                component_key = list(self.components.keys())[key - ord("1")]
                if component_key in selected_comments:
                    selected_comments.remove(component_key)
                else:
                    selected_comments.add(component_key)
                stdscr.move(line_cursor + 2, 0)
                stdscr.clrtoeol()
                stdscr.addstr(
                    line_cursor + 2,
                    0,
                    f"Current components: {p_string(selected_comments)}",
                )
            elif key in (curses.KEY_ENTER, 10, 13):
                result = sorted(list(selected_comments))
                break
            elif key == ord("q"):
                break
        stdscr.refresh()
        return result

    def listen_for_input(self, file_name):
        curses.wrapper(self.display_key_hint)

        running = True

        def input_thread():
            nonlocal running
            while running:
                try:
                    key = curses.wrapper(self.get_single_key)
                    if key is None:
                        continue  # Skip if no valid key was pressed
                    if key == "c":
                        self.pause()
                        current_time = self.get_time()
                        print(f"Paused at {current_time}")

                        # Use curses to display comments and get user selection
                        components = curses.wrapper(self.display_comments)
                        if components is None:
                            print("Exiting...")
                            running = False
                            break

                        # Record the timestamp and comment to a file
                        if len(components) > 0:
                            with open(self.output_name, "a", encoding="utf-8") as f:
                                f.write(
                                    f"{json.dumps({'timestamp': current_time, 'file_name': file_name, 'components': components})}\n"
                                )
                    elif key == "y":
                        self.pause()
                        current_time = self.get_time()
                        print(f"Paused at {current_time}")

                        confirm = (
                            curses.wrapper(
                                lambda stdscr: self.get_curses_input(
                                    stdscr, "Confirm prompt was copy pasted? (y/n): "
                                )
                            )
                            .strip()
                            .lower()
                        )
                        if confirm is None:
                            print("Exiting...")
                            running = False
                            break
                        if confirm != "y":
                            print("Cancelled writing timestamp.")
                            self.play()
                            curses.wrapper(self.display_key_hint)
                            continue

                        # Record the timestamp and comment to a file
                        with open(self.output_name, "a", encoding="utf-8") as f:
                            f.write(
                                f"{json.dumps({'timestamp': current_time, 'file_name': file_name, 'is_copy_pasted': True})}\n"
                            )
                    elif key == "u":
                        self.pause()
                        current_time = self.get_time()
                        print(f"Paused at {current_time}")

                        confirm = (
                            curses.wrapper(
                                lambda stdscr: self.get_curses_input(
                                    stdscr,
                                    "Confirm copy pasted prompt was not changed until submission? (y/n): ",
                                )
                            )
                            .strip()
                            .lower()
                        )
                        if confirm != "y":
                            print("Cancelled writing timestamp.")
                            self.play()
                            curses.wrapper(self.display_key_hint)
                            continue

                        # Record the timestamp and comment to a file
                        with open(self.output_name, "a", encoding="utf-8") as f:
                            f.write(
                                f"{json.dumps({'timestamp': current_time, 'file_name': file_name, 'is_copy_pasted_and_unchanged': True})}\n"
                            )
                    elif key == "o":
                        self.pause()
                        current_time = self.get_time()
                        print(f"Paused at {current_time}")

                        # Use curses to display comments and get user selection
                        comment = curses.wrapper(
                            lambda stdscr: self.get_curses_input(
                                stdscr, "Enter your comment: "
                            )
                        )
                        if comment is None:
                            print("Exiting...")
                            running = False
                            break

                        # Record the timestamp and comment to a file
                        with open(self.output_name, "a", encoding="utf-8") as f:
                            f.write(
                                f"{json.dumps({'timestamp': current_time, 'file_name': file_name, 'comment': comment})}\n"
                            )

                    elif key == "t":
                        self.pause()
                        current_time = self.get_time()
                        action, task = curses.wrapper(self.log_task)
                        if task is None:
                            print("Exiting...")
                            running = False
                            break

                        # Record the timestamp and comment to a file
                        with open(self.output_name, "a", encoding="utf-8") as f:
                            f.write(
                                f"{json.dumps({'timestamp': current_time, 'file_name': file_name, 'action': action, 'task': task})}\n"
                            )

                    elif key == "q":
                        print("Exiting...")
                        running = False
                        break
                    self.play()
                    curses.wrapper(self.display_key_hint)
                except (EOFError, KeyboardInterrupt):
                    running = False
                    break

        # Start input thread
        input_worker = threading.Thread(target=input_thread, daemon=True)
        input_worker.start()

        # Wait for the input thread to finish
        input_worker.join()

    def log_task(self, stdscr):
        line_cursor = 0
        curses.curs_set(0)  # Hide the cursor
        stdscr.clear()

        # Step 1: Ask for start or end
        stdscr.addstr(
            line_cursor,
            0,
            "Log Task: Start or End? (press '1' for Start, '2' for End):",
        )
        line_cursor += 2
        stdscr.refresh()

        while True:
            key = stdscr.getch()
            if key == ord("1"):
                action = "start"
                break
            elif key == ord("2"):
                action = "end"
                break

        # Step 2: Ask for task number
        stdscr.clear()
        stdscr.addstr(line_cursor, 0, "Select a task (press the corresponding number):")
        line_cursor += 1

        tasks = [
            "Task 1 (CALCULATOR_2)",
            "Task 2 (MAPLE_RECURSIVE_ABSOLUTE_2)",
            "Task 3 (LINKED_LIST_MAKE_AFTER_1)",
            "Task 4 (LINKED_STACK_MAKE_COMBINED)",
            "Task 5 (PRIME_CHECK_8)",
            "Task 6 (QS_QUEUE_49)",
            "Task 7 (ARRAY_FORCE_TO_EMPTY_1)",
            "Task 8 (TIME_1)",
            "Task 9 (FIND_FIRST_IN_SORTED_1)",
            "Task 10 (FIND_IN_SORTED_6) (Press 0 to select)",
        ]
        for idx, task in enumerate(tasks):
            curses.init_pair(idx + 1, curses.COLOR_GREEN, curses.COLOR_BLACK)
            stdscr.addstr(
                line_cursor, 0, f"{idx + 1}. {task}", curses.color_pair(idx + 1)
            )
            line_cursor += 1

        stdscr.addstr(line_cursor, 0, "Press Enter to confirm selection.")
        line_cursor += 2
        stdscr.refresh()

        selected_task = None
        while True:
            key = stdscr.getch()
            if key in range(ord("0"), ord("0") + len(tasks)):
                if key == ord("0"):
                    selected_task = tasks[-1]  # Task 10
                else:
                    selected_task = tasks[key - ord("1")]
                break

        # Log the action and task
        stdscr.clear()
        stdscr.addstr(0, 0, f"Logged {action} for {selected_task}")
        stdscr.refresh()
        return action, selected_task

    def quit_vlc(self):
        self.send_command("quit")  # Quit VLC when done

    def get_curses_input(self, stdscr, prompt):
        curses.curs_set(1)  # Show the cursor
        stdscr.clear()
        stdscr.addstr(0, 0, prompt)
        stdscr.refresh()

        input_str = ""
        while True:
            key = stdscr.getch()
            if key in (curses.KEY_ENTER, 10, 13):  # Enter key
                break
            elif key in (curses.KEY_BACKSPACE, 127):  # Backspace key
                input_str = input_str[:-1]
                stdscr.clear()
                stdscr.addstr(0, 0, prompt + input_str)
                stdscr.refresh()
            elif 32 <= key <= 126:  # Printable characters
                input_str += chr(key)
                stdscr.addstr(0, 0, prompt + input_str)
                stdscr.refresh()

        curses.curs_set(0)  # Hide the cursor
        return input_str

    def display_key_hint(self, stdscr):
        stdscr.clear()
        key_hint = [
            "'t' to log task start or end",
            "'c' to log prompt Components and Categories",
            "'y' to log prompt copY paste",
            "'u' to log copy past prompt unchanged Until submission",
            "'o' to add cOmment",
            "'q' to Quit",
        ]
        stdscr.addstr(0, 0, "Press:")
        for idx, hint in enumerate(key_hint, start=1):
            stdscr.addstr(idx, 2, f"- {hint}")
        stdscr.refresh()
        # stdscr.getch()  # Wait for user to press a key before continuing

    def get_single_key(self, stdscr):
        """Get a single key press using curses"""
        key = stdscr.getch()
        return chr(key).lower() if 32 <= key <= 126 else None


def main(output_name, video_paths):
    vlc_controller = VLCController(output_name)
    vlc_controller.start_vlc()

    for video_path in video_paths:
        print(f"Now playing: {video_path}")

        # Start the video playing
        vlc_controller.add(video_path)
        vlc_controller.play()

        # Start listening for user input
        vlc_controller.listen_for_input(video_path)

    vlc_controller.quit_vlc()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python main.py ouput-name <video1.mp4> <video2.mp4> ...")
        sys.exit(1)

    _, output, *videos = sys.argv
    # Clear the terminal at the start
    print("\033c", end="")
    main(output, videos)
