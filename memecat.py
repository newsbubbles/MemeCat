import argparse
import os
import subprocess
import tempfile
import whisper

from lib.semdict import SemanticDict

# set up the full effects table from https://aegisub.org/docs/latest/ass_tags/

class Effect:
    def __init__(self, name:str=None):
        self.name = name

class EffectBucket:
    def __init__(self, load_file=None):
        self.effects:SemanticDict
        self.time_index:list[str] = [] # index by effect name
        
    def config(self):
        
        pass

def generate_ass_subtitles_from_words(word_list, font="Arial Black", font_size=180, primary_color="&H00FFFFFF&", fade=True):
    """
    Generate an ASS subtitle file (as a string) from a list of (start, end, text) tuples.
    We show one word per line. The text is center-middle. Fade effects are optional.

    Parameters:
    - word_list: A list of tuples: (start_time, end_time, text)
    - font: Default Font family for the subtitles.
    - font_size: Font size in points.
    - primary_color: ASS color code. Default: white.
    - fade: Boolean, if True adds a fade-in/out effect.
    """
    words_per_line = 1

    ass_header = f"""[Script Info]
; Script generated by Python
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Collisions: Normal
ScaledBorderAndShadow: yes

[V4+ Styles]
; Alignment 5 = middle-center
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{font},{font_size},{primary_color},&H000000FF&,&H00000000&,&H80000000&,1,0,0,0,100,100,0,0,1,5,0,5,50,50,50,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines = []
    
    for i in range(0, len(word_list), words_per_line):
        chunk = word_list[i:i+words_per_line]
        start_time = chunk[0][0]
        end_time = chunk[-1][1]
        text = " ".join(w[2] for w in chunk)

        start_h, start_m, start_s = seconds_to_hms(start_time)
        end_h, end_m, end_s = seconds_to_hms(end_time)

        # Add fade if requested
        # This is where the effects bucket comes into play
        effect_str = ""
        if fade:
            effect_str = r"{\fad(200,200)}"

        line = f"Dialogue: 0,{start_h}:{start_m}:{start_s:.2f},{end_h}:{end_m}:{end_s:.2f},Default,,0,0,0,,{effect_str}{text}"
        dialogue_lines.append(line)

    return ass_header + "\n".join(dialogue_lines)

def seconds_to_hms(seconds):
    """Convert float seconds to H,MM,SS.xx format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = (seconds % 60)
    return h, f"{m:02d}", s

def main():
    parser = argparse.ArgumentParser(description="Create a video with overlaid subtitles from audio using Whisper and FFmpeg, similar to CapCut style.")
    parser.add_argument('--input_video', required=True, help="Path to the input video.")
    parser.add_argument('--output_video', required=True, help="Path to the output video.")
    parser.add_argument('--model', default='small', help="Whisper model size (e.g., tiny, base, small, medium, large).")
    parser.add_argument('--font', default='Arial Black', help="Font to use for subtitles.")
    parser.add_argument('--font_size', type=int, default=180, help="Font size for subtitles.")
    parser.add_argument('--primary_color', default='&H00FFFFFF&', help="Primary color for subtitles in ASS format. Default is white.")
    parser.add_argument('--no_fade', action='store_true', help="If set, do not apply fade-in/out effect to the subtitles.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmpdir:
        model = whisper.load_model(args.model)
        result = model.transcribe(args.input_video, word_timestamps=True)

        # Extract words and their timestamps
        word_list = []
        for seg in result['segments']:
            for w in seg.get('words', []):
                w_text = w['word'].strip()
                if w_text:
                    start = w['start']
                    end = w['end']
                    word_list.append((start, end, w_text))

        # Fallback if no word-level timestamps
        if not word_list:
            for seg in result['segments']:
                word_list.append((seg['start'], seg['end'], seg['text'].strip()))

        ass_content = generate_ass_subtitles_from_words(
            word_list,
            font=args.font,
            font_size=args.font_size,
            primary_color=args.primary_color,
            fade=not args.no_fade
        )

        ass_path = os.path.join(tmpdir, "subtitles.ass")
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        # Burn in subtitles onto the output video
        subprocess.run([
            "ffmpeg", "-y", "-i", args.input_video, 
            "-vf", f"ass={ass_path}", 
            "-c:a", "copy", 
            args.output_video
        ], check=True)

    print(f"Done! Created {args.output_video} with burned-in subtitles.")

if __name__ == "__main__":
    main()

