import subprocess
import time
import curses
import sys
import re
import json

class VLCController:
    def __init__(self, output_name):
        self.output_name = output_name

        self.process = None

        self.components = [
            'natural language',
            'source code',
            'tool output'
        ]

        self.categories = [
            'question',
            'task'
        ]

    def start_vlc(self):
        # Start VLC process with RC interface and GUI
        self.process = subprocess.Popen(
            ['vlc', '--extraintf', 'rc'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True
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
            self.process.stdin.write(command + '\n')
            self.process.stdin.flush()

    def add(self, video_path):
        self.send_command(f'add {video_path}')

    def play(self):
        self.send_command('play')

    def pause(self):
        self.send_command('pause')

    def get_time(self):
        self.send_command('get_time')
        return self.readln()

    def display_comments(self, stdscr):
        curses.curs_set(0)  # Hide the cursor
        stdscr.clear()
        stdscr.addstr(0, 0, "Select a comment (press the corresponding number):")

        for idx, comment in enumerate(self.components):
            stdscr.addstr(idx + 1, 0, f"{idx + 1}. {comment}")

        stdscr.addstr(len(self.components) + 2, 0, "Press 'q' to quit.")
        stdscr.refresh()

        selected_comment = None
        while selected_comment is None:
            key = stdscr.getch()
            if key in range(ord('1'), ord('1') + len(self.components)):
                selected_comment = self.components[key - ord('1')]
            elif key == ord('q'):
                return None  # Exit if 'q' is pressed

        return selected_comment

    def listen_for_input(self):
        while True:
            input("Press Enter to pause and record timestamp...")
            self.pause()
            current_time = self.get_time()
            print(f"Paused at {current_time}")

            # Use curses to display comments and get user selection
            comment = curses.wrapper(self.display_comments)
            if comment is None:
                print("Exiting...")
                break

            # Record the timestamp and comment to a file
            with open(self.output_name, "a") as f:
                f.write(f"{json.dumps({'timestamp': current_time, 'comment': comment})}\n")

            self.play()

    def quit_vlc(self):
        self.send_command('quit')  # Quit VLC when done

def main(output_name, video_paths):
    vlc_controller = VLCController(output_name)
    vlc_controller.start_vlc()

    for video_path in video_paths:
        print(f"Now playing: {video_path}")

        # Start the video playing
        vlc_controller.add(video_path)
        vlc_controller.play()

        # Start listening for user input
        vlc_controller.listen_for_input()

    vlc_controller.quit_vlc()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python main.py ouput-name <video1.mp4> <video2.mp4> ...")
        sys.exit(1)

    _, output, *videos = sys.argv
    main(output, videos)
