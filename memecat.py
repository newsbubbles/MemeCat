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
        - Uses a semantic effects system
        semantic clipping based on text concept buckets
        long silence removal
        long context search for sticky styles!!!!
        auto censoring: -mute or cut out certain words/concepts
        top_k words: top word analysis for showing which words
        TODO change for multiple effects
"""

# Utility

def rgb_mirror(color):
    # b g r <-|-> r g b
    return color[4:6] + color[2:4] + color[0:2]

def seconds_to_hms(seconds):
    """Convert float seconds to H,MM,SS.xx format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = (seconds % 60)
    return h, f"{m:02d}", s


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

class Image(Effect):
    """ Image does nothing to the text but acts as a trigger to grab from the bucket"""
    def tag(self):
        return ""
    
class Video(Effect):
    """ Video does nothing to the text but acts as a trigger to grab from the bucket"""
    def tag(self):
        return ""

class Audio(Effect):
    """ Video does nothing to the text but acts as a trigger to grab from the bucket"""
    def tag(self):
        return ""

class Color(Effect):
    """ Performs RGB->BRG conversion in the tag """
    def tag(self):
        return "{\\" + self.ass_switch + str(rgb_mirror(self.arg) or '') + self.suffix + "}"

class Alpha(Effect):
    """ Performs (0.0, 1.0) ranged alpha to Hex FF inverted (ass format)"""
    def tag(self):
        trans = int(255 * (1.0 - float(self.arg)))
        return "{\\" + self.ass_switch + str(hex(trans)).replace('0x', '') + self.suffix + "}"

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
        self.add(Alpha('alpha', 'alpha&H', arg_name='opacity', arg=0.75, suffix='&'))
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
        self.add(Image('image', None, arg_name='src'))
        self.add(Video('video', None, arg_name='src'))
        self.add(Audio('volume', None, arg_name='ratio', arg=0.5))

class EffectBucket:
    """ Holds high level bucket of effects and styles """
    def __init__(self, load_file=None):
        self.effects:SemanticDict = SemanticDict()
        self.index:EffectIndex = EffectIndex()
        self.overlays:dict[str, dict] = {}
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
            if text not in self.effects.data:
                self.effects.add(text, [e])
            else:
                self.effects.data[text].append(e)
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
        self.overlays = config.get('overlays', {})

# Main class

class MemeCat:
            
    @staticmethod
    def generate_subtitles(word_list, bucket:EffectBucket, font="Arial Black", font_size=180, primary_color="&H00FFFFFF&", words_per_line=1, threshold=0.2, search_n=1):
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
        overlays:list[dict] = []
        audio_effects:list[dict] = []
        top_k_words:dict[str, int] = {}
        full_text = ""
        
        for i in range(0, len(word_list), words_per_line):
            # get chunk and text
            chunk = word_list[i:i+words_per_line]
            start_time = chunk[0][0]
            end_time = chunk[-1][1]
            text = " ".join(w[2] for w in chunk)
            full_text += " " + text
            
            # get top_k for text frequency
            wk = text.strip(r'.-!? ').lower()
            if wk not in top_k_words:
                top_k_words[wk] = 0
            top_k_words[wk] += 1
            
            # find any n effects that should be applied given the text
            effect = bucket.search(text, threshold=threshold, n=search_n)

            start_h, start_m, start_s = seconds_to_hms(start_time)
            end_h, end_m, end_s = seconds_to_hms(end_time)

            # This is where the effects bucket comes into play
            effect_str, effect_str_end = "", ""
                
            if effect is not None:
                for eff in effect:
                    if isinstance(eff, list):
                        for e in eff:
                            # If Effect is an Image or video, add to the overlay_effects list
                            # Idea is to output the timings so that the ffmpeg overlay process can insert correctly given the other settings
                            print(e)
                            if isinstance(e, (Image, Video)):
                                print('IMAGE', e.arg)
                                # get the image from self.overlays
                                ol = copy.deepcopy(bucket.overlays.get(e.arg))
                                # add times to overlay_effects
                                ol['start_time'] = float(start_time)
                                duration = ol.get('duration')
                                if duration is None:
                                    ol['end_time'] = float(end_time)
                                else:
                                    ol['end_time'] = float(start_time) + duration
                                overlays.append(ol)
                            elif isinstance(e, Audio):
                                el = {'volume': e.arg, 'start': float(start_time), 'end': float(end_time)}
                                audio_effects.append(el)
                            effect_str += e.tag()
                    else:
                        effect_str = eff.tag()

            line = f"Dialogue: 0,{start_h}:{start_m}:{start_s:.2f},{end_h}:{end_m}:{end_s:.2f},Default,,0,0,0,,{effect_str}{text}{effect_str_end}"
            dialogue_lines.append(line)
            
        top_k = dict(sorted(top_k_words.items(), key=lambda item: item[1], reverse=True))
        print(top_k)
            
        return ass_header + "\n".join(dialogue_lines), overlays, audio_effects, top_k, full_text
    
    @staticmethod
    def burn(
        input_video:str,
        output_video:str,
        bucket_path=None,
        model='small',
        words=1,
        threshold=0.2,
        n=1,
        font=None,
        font_size=None,
        primary_color=None,
        ass_path="subtitles.ass",
    ):
        # Load up a bucket
        bucket = EffectBucket(bucket_path)

        model = whisper.load_model(model)
        result = model.transcribe(input_video, word_timestamps=True)

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

        ass_content, overlays, audio_effects, top_k, full_text = MemeCat.generate_subtitles(
            word_list,
            bucket,
            font=font,
            font_size=font_size,
            primary_color=primary_color,
            words_per_line=int(words),
            threshold=float(threshold),
            search_n=int(n),
        )

        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        MemeCat.write(input_video, output_video, ass_path, overlays=overlays, audio_effects=audio_effects)

        print(f"Done! Created {output_video} with burned-in subtitles.")
    
    @staticmethod
    def write(video_path: str, output_path: str, ass_path: str, overlays: list[dict] = None, audio_copy=True, audio_effects=None):
        """
        Write the captions and overlays onto a video with specific configurations.

        Parameters:
        - video_path (str): Path to the input video.
        - overlays (list[dict]): List of overlay configurations.
            Each configuration is a dictionary with keys:
                - 'src': Path to the image.
                - 'x': X position of the image.
                - 'y': Y position of the image.
                - 'width': Width of the image (optional).
                - 'height': Height of the image (optional).
                - 'start_time': Start time (in seconds).
                - 'end_time': End time (in seconds).
        - output_path (str): Path to save the output video.
        - ass_path (str): Path to the ASS subtitle file to burn in (required).
        - audio_copy (bool): Whether to copy audio without re-encoding.

        Returns:
        - None
        """
        if not ass_path:
            raise ValueError("A subtitle file (ass_path) must be provided.")

        def get_overlay_position(alignment, margin_x, margin_y):
            alignments = {
                "top-left": (margin_x, margin_y),
                "top-center": (f"(main_w-overlay_w)/2+{margin_x}", margin_y),
                "top": (f"(main_w-overlay_w)/2+{margin_x}", margin_y),
                "top-right": (f"main_w-overlay_w-{margin_x}", margin_y),
                "middle-left": (margin_x, f"(main_h-overlay_h)/2+{margin_y}"),
                "middle-center": (f"(main_w-overlay_w)/2+{margin_x}", f"(main_h-overlay_h)/2+{margin_y}"),
                "middle": (f"(main_w-overlay_w)/2+{margin_x}", f"(main_h-overlay_h)/2+{margin_y}"),
                "middle-right": (f"main_w-overlay_w-{margin_x}", f"(main_h-overlay_h)/2+{margin_y}"),
                "bottom-left": (margin_x, f"main_h-overlay_h-{margin_y}"),
                "bottom-center": (f"(main_w-overlay_w)/2+{margin_x}", f"main_h-overlay_h-{margin_y}"),
                "bottom": (f"(main_w-overlay_w)/2+{margin_x}", f"main_h-overlay_h-{margin_y}"),
                "bottom-right": (f"main_w-overlay_w-{margin_x}", f"main_h-overlay_h-{margin_y}")
            }
            return alignments.get(alignment, alignments["top-center"])

        filter_complex = []
        input_count = 1  # Start after the main video input
        overlay_streams = []
        final_label = '0:v'
        label = ''

        if overlays:
            for i, config in enumerate(overlays):
                # Handle optional width and height
                width = config.get('width', 'iw')  # Default to input width
                height = config.get('height', 'ih')  # Default to input height
                alignment = config.get('alignment', 'top-center')
                margin_x = config.get('margin_x', 28)
                margin_y = config.get('margin_y', 28)
                
                if config.get('x') is None or config.get('y') is None:
                    x, y = get_overlay_position(alignment, margin_x, margin_y)
                else:
                    x = config.get('x')
                    y = config.get('y')
                
                # Timing
                start_time = config['start_time']
                end_time = config['end_time']

                # Format, scale, and prepare overlay filter
                filter_complex.append(f"[{input_count}:v]format=rgba,scale=w={width}:h={height}[img{i}]")
                next_stream = f"[v{i+1}]"
                label = final_label if i == 0 else f"v{i}"
                overlay_streams.append(f"[{label}][img{i}]overlay=x={x}:y={y}:enable='between(t,{start_time},{end_time})'{next_stream}")
                input_count += 1

        # Add subtitles filter
        subtitle_filter = f"ass={ass_path}"
        if overlays:
            filter_complex.extend(overlay_streams)
            filter_complex.append(f"{next_stream}{subtitle_filter}")
            combined_filters = ";".join(filter_complex)
        else:
            combined_filters = subtitle_filter

        # Build ffmpeg command
        command = [
            "ffmpeg", "-y", "-i", video_path
        ]

        # Add image inputs
        if overlays:
            for config in overlays:
                command.extend(["-i", config['src']])

        # Add filter complex
        command.extend(["-filter_complex", f'{combined_filters}'])

        # Handle audio filtering
        if len(audio_effects) == 0: # just copy audio
            command.extend(["-c:a", "copy"])
        else: # apply audio effects
            combined_audio_filters = []
            # TODO Audio can have effects beyond volume
            #   using an audio library like torchaudio
            #   NOTE would need to first extract audio, then formatting
            for af in audio_effects:
                combined_audio_filters.append(f"volume=enable='between(t,{af['start']},{af['end']})':volume={af['volume']}")
            command.extend(["-af", ",".join(combined_audio_filters)])

        # Add output file
        command.append(output_path)

        print(" ".join(command))

        # Run the command
        subprocess.run(command, check=True)
        
def main():
    parser = argparse.ArgumentParser(description="Create a video with overlaid subtitles from audio using Whisper and FFmpeg, similar to CapCut style.")
    # The videos
    parser.add_argument('--input_video', required=True, help="Path to the input video.")
    parser.add_argument('--output_video', required=True, help="Path to the output video.")
    # Semantic Search vars
    parser.add_argument('--bucket', default='buckets/nate.yml', help="The default Effects and Style Bucket to use for captions")
    parser.add_argument('--model', default='small', help="Whisper model size (e.g., tiny, base, small, medium, large).")
    parser.add_argument('--words', default=1, help="How many words can be on screen at the same time.")
    parser.add_argument('--threshold', default=0.2, help="Semantic search threshold (how close to the same meaning as your bucket tags)")
    parser.add_argument('--n', default=2, help="Semantic search effect result max (how many relevant effects can be stacked)")
    # Default Style overrides
    parser.add_argument('--font', default='Impact', help="Default font to use for subtitles.")
    parser.add_argument('--font_size', type=int, default=180, help="Font size for subtitles.")
    parser.add_argument('--primary_color', default='&H00FFFFFF&', help="Primary color for subtitles in ASS format. Default is white.")
    args = parser.parse_args()
    
    MemeCat.burn(
        args.input_video,
        args.output_video,
        bucket_path=args.bucket,
        model=args.model,
        words=args.words,
        threshold=args.threshold,
        n=args.n,
        font=args.font,
        font_size=args.font_size,
        primary_color=args.primary_color,
    )
    

if __name__ == "__main__":
    main()

