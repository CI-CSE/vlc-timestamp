# vlc-timestamp

## Installation

Install python and VLC player <https://www.videolan.org/vlc/>

This project uses python venv.

Create virtual environment

``` sh
python -m venv .venv
```

Activate environment

``` sh
source .venv/bin/activate
```

Install requirements

``` sh
pip install -r requirements.txt
```


## Usage
Run VLC with the HTTP interface

``` sh
vlc --extraintf http --http-port 3000 --http-password cit
```

Run the script

``` sh
python main.py video1.mp4 video2.mp4
```

