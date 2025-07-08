import subprocess
import time
import curses
import sys
import re
import json
import threading
import termios
import tty


class VLCController:
    def __init__(self, output_name):
        self.output_name = output_name

        self.process = None

        self.components = {
            "natural language": ["Prompt contains natural language", curses.COLOR_CYAN],
            "source code": ["Prompt contains sourcs code", curses.COLOR_GREEN],
            "tool output": [
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
        """Get a single character from stdin without pressing Enter"""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

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
            description, color = self.components[comment]
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
        key_hint = "Press" + " --- ".join(
            [
                "'c' to log prompt Components and Categories",  # implemented
                "'y' to log prompt copY paste",  # implemented
                "'u' to log copy past prompt unchanged Until submission",  # implemented
                "'o' to add cOmment",  # implemented
                "'q' to Quit",  # implemented
            ]
        )
        print(key_hint)

        running = True

        def input_thread():
            nonlocal running
            while running:
                try:
                    key = self.getch().lower()
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

                        self.play()
                        print(key_hint)
                    elif key == "y":
                        self.pause()
                        current_time = self.get_time()
                        print(f"Paused at {current_time}")

                        confirm = (
                            input("Confirm prompt was copy pasted? (y/n): ")
                            .strip()
                            .lower()
                        )
                        if confirm != "y":
                            print("Cancelled writing timestamp.")
                            self.play()
                            print(key_hint)
                            continue

                        # Record the timestamp and comment to a file
                        with open(self.output_name, "a", encoding="utf-8") as f:
                            f.write(
                                f"{json.dumps({'timestamp': current_time, 'file_name': file_name, 'is_copy_pasted': True})}\n"
                            )

                        self.play()
                        print(key_hint)
                    elif key == "u":
                        self.pause()
                        current_time = self.get_time()
                        print(f"Paused at {current_time}")

                        confirm = (
                            input(
                                "Confirm copy pasted prompt was not changed until submission? (y/n): "
                            )
                            .strip()
                            .lower()
                        )
                        if confirm != "y":
                            print("Cancelled writing timestamp.")
                            self.play()
                            print(key_hint)
                            continue

                        # Record the timestamp and comment to a file
                        with open(self.output_name, "a", encoding="utf-8") as f:
                            f.write(
                                f"{json.dumps({'timestamp': current_time, 'file_name': file_name, 'is_copy_pasted_and_unchanged': True})}\n"
                            )

                        self.play()
                        print(key_hint)
                    elif key == "o":
                        self.pause()
                        current_time = self.get_time()
                        print(f"Paused at {current_time}")

                        # Use curses to display comments and get user selection
                        comment = input("Enter your comment: ")
                        if comment is None:
                            print("Exiting...")
                            running = False
                            break

                        # Record the timestamp and comment to a file
                        with open(self.output_name, "a", encoding="utf-8") as f:
                            f.write(
                                f"{json.dumps({'timestamp': current_time, 'file_name': file_name, 'comment': comment})}\n"
                            )

                        self.play()
                        print(key_hint)
                    elif key == "q":
                        print("Exiting...")
                        running = False
                        break
                except (EOFError, KeyboardInterrupt):
                    running = False
                    break

        # Start input thread
        input_worker = threading.Thread(target=input_thread, daemon=True)
        input_worker.start()

        # Wait for the input thread to finish
        input_worker.join()

    def quit_vlc(self):
        self.send_command("quit")  # Quit VLC when done


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
    main(output, videos)
