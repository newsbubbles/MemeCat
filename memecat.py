import argparse
import copy
import os
import subprocess
import tempfile
import whisper

import yaml
from lib.semdict import SemanticDict

"""
    MemeCat: smart subtitles, less work. By @newsbubbles on github (@natecodesai on YouTube)
        Uses a semantic effects system
        semantic clipping based on text concept buckets
        long silence removal
        long context search for sticky styles!!!!
        auto censoring: mute or cut out certain words/concepts
        top_k words: top word analysis for showing which words
"""

# Utility

def rgb_mirror(color):
    # b g r <-|-> r g b
    return color[4:6] + color[2:4] + color[0:2]

# Styles and Effects

class Style: # a class to match the aegisub style format but with yaml, cause yeh
    def __init__(self, name:str, data=None):
        self.name = name
        self.data = data

# set up the full effects table from https://aegisub.org/docs/latest/ass_tags/

class Effect:
    """ A Modular model for a single Aegisub text effect"""
    def __init__(self, name:str=None, ass_switch:str=None, arg_name:str=None, arg=None, suffix=None, sticky=False, data:dict=None):
        self.name:str = name # for indexing
        
        # aegisub properties for rendering tag
        self.ass_switch:str = ass_switch
        self.arg_name = arg_name
        self.arg = arg
        self.suffix = suffix or ''
        self.sticky = sticky # this is only for if you want the effect to take place afterwards without a style reset
    
        self.data:dict = data # holds other data when 
        
    def tag(self):
        """ Returns the tag as it should be given inline in the ASS file """
        return "{\\" + self.ass_switch + str(self.arg or '') + self.suffix + "}"
    
    def off(self):
        # for use with things like bold in which 0 turns the effect back off
        # font_size and other globally configured vars will go back to the default here?
        return "{\\" + self.ass_switch + '0' + "}"
    
class Emoji(Effect):
    """ Emoji subclasses Effect but only returns emoji above the text """
    def tag(self):
        return self.arg + "\\N" 
    
class Color(Effect):
    """ Performs RGB->BRG conversion in the tag """
    def tag(self):
        return "{\\" + self.ass_switch + str(rgb_mirror(self.arg) or '') + self.suffix + "}"

# Effect Bucket
        
class EffectIndex:
    def __init__(self):
        self.effects:dict[str, Effect] = {}
        
    def add(self, effect:Effect):
        self.effects[effect.name] = effect
        
    def get(self, effect_name:str):
        return self.effects[effect_name] or None
        
    def exists(self, effect_name:str):
        return effect_name in self.effects
    
    def config(self):
        self.add(Effect('font_family', 'fn', arg_name='on', arg='Arial'))
        self.add(Effect('font_size', 'fs', arg_name='on', arg='Arial'))
        self.add(Color('color', 'c&H', arg_name='GBR hex color', arg='FFFFFF', suffix='&'))
        self.add(Color('border_color', '3c&H', arg_name='RGB hex color', arg='000000', suffix='&'))
        self.add(Color('shadow_color', '4c&H', arg_name='RGB hex color', arg='000000', suffix='&'))
        self.add(Effect('alpha', 'alpha&H', arg_name='alpha percent', arg=75, suffix='&'))
        self.add(Effect('bold', 'b', arg_name='weight', arg=1))
        self.add(Effect('italic', 'i', arg_name='on', arg=1))
        self.add(Effect('underline', 'u', arg_name='on', arg=1))
        self.add(Effect('strikeout', 's', arg_name='on', arg=1))
        self.add(Effect('border', 'bord', arg_name='thickness', arg=1))
        self.add(Effect('blur_edges', 'be', arg_name='amount', arg=1))
        self.add(Effect('rotate_x', 'frx', arg_name='degrees', arg=45))
        self.add(Effect('rotate_y', 'fry', arg_name='degrees', arg=45))
        self.add(Effect('rotate_z', 'frz', arg_name='degrees', arg=45))
        self.add(Effect('shear_x', 'fax', arg_name='factor', arg=1))
        self.add(Effect('shear_y', 'fay', arg_name='factor', arg=1))
        self.add(Effect('alignment', 'an', arg_name='position', arg=5)) # uses (numpad) alignment [ordered like the numpad]
        self.add(Effect('reset_style', 'r', arg_name="style", arg=""))
        self.add(Emoji('emoji', None, arg_name='emoji', arg='😂'))

class EffectBucket:
    """ Holds high level bucket of effects and styles """
    def __init__(self, load_file=None):
        self.effects:SemanticDict = SemanticDict()
        self.index:EffectIndex = EffectIndex()
        self.styles:dict = {
            'Default': {
                'font': 'Francois One',
                'font_size': 150,
                'color': 'FFFFFF',
                'border_color': '000000',
                'shadow_color': '000000'
            }
        }
        self.index.config()
        if load_file is not None:
            self.load_from_yaml(load_file)
        
    def init_effect(self, effect_name:str, arg=1):
        """ Finds the effect in the index and then copies it, overwriting the arg value """
        e = self.index.get(effect_name)
        ie = None
        if e:
            ie = copy.deepcopy(self.index.get(effect_name))
            ie.arg = arg
        return ie

    def add_one(self, text:str, effect_name:str|dict, arg=1):
        e = self.init_effect(effect_name, arg=arg)
        if e is not None:
            self.effects.add(text, e)
        else:
            raise ValueError(f"Effect {effect_name} not found.")

    def add(self, text:str, effect_name:str|dict, arg=1):
        """ Adds the effect to the bucket by name """
        if isinstance(effect_name, dict): # if a dict, add multiple effects
            # use effect data for storing the arg pairs
            for name, argument in effect_name.items():
                self.add_one(text, name, arg=argument)
        else:
            self.add_one(text, effect_name, arg=arg)
            
    def search(self, query:str, threshold=0.2, n=1) -> Effect:
        """ Semantically find the effect in the bucket by query """
        r = self.effects.get(query, threshold=threshold, n=n) # threshold based on paraphrase MiniLM-L6-v2
        if len(r) == 0:
            return None
        print(r, query)
        return [v[1] for v in r] # value of the first effect returned

    def load_from_yaml(self, filepath):
        with open(filepath, 'r') as f:
            config = yaml.safe_load(f)
        for entry in config.get('effects', []):
            self.add(*entry)
        self.styles = config.get('styles', {})
            
# Main function uses bucket
def generate_ass_subtitles_from_words(word_list, bucket:EffectBucket, font="Arial Black", font_size=180, primary_color="&H00FFFFFF&", words_per_line=1, threshold=0.2, search_n=1):
    """
    Generate an ASS subtitle file (as a string) from a list of (start, end, text) tuples.
    We show by default one word per line. The text is center-middle. Fade effects are optional.
    Aegisub is already part of ffmpeg so it will read a properly formatted ass script

    Parameters:
    - word_list: A list of tuples: (start_time, end_time, text)
    - font: Default Font family for the subtitles.
    - font_size: Font size in points.
    - primary_color: ASS color code. Default: white.
    """    
    threshold = float(threshold)
    

    # TODO Add more styles here
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
        # get chunk and text
        chunk = word_list[i:i+words_per_line]
        start_time = chunk[0][0]
        end_time = chunk[-1][1]
        text = " ".join(w[2] for w in chunk)
        
        # find any n effects that should be applied given the text
        effect = bucket.search(text, threshold=threshold, n=search_n)

        start_h, start_m, start_s = seconds_to_hms(start_time)
        end_h, end_m, end_s = seconds_to_hms(end_time)

        # This is where the effects bucket comes into play
        effect_str, effect_str_end = "", ""
            
        if effect is not None:
            if isinstance(effect, list):
                for e in effect:
                    effect_str += e.tag()
            else:
                effect_str = effect.tag()
            # if not effect.sticky: ... sticky effects done by long context
            #     effect_str_end = r"{\r}"

        line = f"Dialogue: 0,{start_h}:{start_m}:{start_s:.2f},{end_h}:{end_m}:{end_s:.2f},Default,,0,0,0,,{effect_str}{text}{effect_str_end}"
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
    parser.add_argument('--words', default=1, help="How many words can be on screen at the same time.")
    parser.add_argument('--font_size', type=int, default=180, help="Font size for subtitles.")
    parser.add_argument('--primary_color', default='&H00FFFFFF&', help="Primary color for subtitles in ASS format. Default is white.")
    parser.add_argument('--threshold', default=0.2, help="Semantic search threshold (how close to the same meaning as your bucket tags)")
    parser.add_argument('--n', default=2, help="Semantic search effect result max (how many relevant effects can be stacked)")
    parser.add_argument('--bucket', default='buckets/nate.yml', help="The default Effects and Style Bucket to use for captions")
    args = parser.parse_args()
    
    # Load up a bucket
    bucket = EffectBucket(args.bucket)

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
            bucket,
            font=args.font,
            font_size=args.font_size,
            primary_color=args.primary_color,
            words_per_line=int(args.words),
            threshold=float(args.threshold),
            search_n=int(args.n),
        )

        ass_path = "subtitles.ass"
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

