# MemeCat

Welcome to **MemeCat**—the purr-fect CLI tool that slaps automated, stylish, and completely unnecessary captions all over your videos. Why pay for fancy pants video editors when all you need are sweet, sweet subtitles you can do at the command line like the true keyboard warrior you are?

MemeCat extracts the audio from your video, uses [OpenAI’s Whisper](https://github.com/openai/whisper) to transcribe it, and then sprinkles those words right in the middle of your screen in **BIG, LOUD TEXT**. Give your videos that *"TikTok influencer meets basement meme lord"* energy with no fuss, no frills, and a blatant disregard for complex licensing fees.

## Features

- **Automatic Transcription:** Leverages Whisper to translate the weird mumbling from your video into actual words.
- **Customizable Fonts & Sizes:** Because your life’s calling is to find the perfect font size that says, “I’m screaming, and so is this caption.”
- **Optional Fade Effects:** Add subtle fades or skip the drama entirely. It’s your show.

## Requirements

1. **Python 3.x**: Because it's not 1995.
2. **FFmpeg**: Don’t worry, it’s basically on every Linux machine already. If not:
   ```bash
   sudo apt-get update && sudo apt-get install ffmpeg
   ```
3. **Whisper**: Install the OpenAI whisper (the correct one, not the bootleg knockoff):
   ```bash
   pip install --upgrade openai-whisper
   ```

## Installation

```bash
git clone https://github.com/newsbubbles/MemeCat.git
cd MemeCat
pip install -r requirements.txt
```

*(If we forgot to include a requirements.txt, just pretend we did. Or just run `pip install openai-whisper` and hope for the best.)*

## Usage

**Basic Command:**
```bash
python memecat.py --input_video input.mp4 --output_video output.mp4
```

This will:
1. Listen to your video intently.
2. Scribble down everything you said (or didn’t say but the mic picked up anyway).
3. Burn captions onto your video’s soul.

**Customize the Font & Size:**
```bash
python memecat.py --input_video input.mp4 --output_video memefied.mp4 --font "Arial Black" --font_size 180
```

**No Fade, All Business:**
```bash
python memecat.py --input_video input.mp4 --output_video no_fade.mp4 --no_fade
```

**Pick a Different Model (Because ‘size’ matters):**
```bash
python memecat.py --input_video input.mp4 --output_video bigbrain.mp4 --model medium
```

## Why MemeCat?

- Because paying for a full-fledged NLE to add some freakin’ subtitles is like buying a private jet to visit your neighbor.
- Because we stand for the open-source spirit of doing something incredibly niche without any sane reason.
- Because cats are meme kings. Duh.

## License

MIT—meaning do whatever you want and don’t blame us if your cringey subtitles scare off your viewers.

## Contributing

Sure, why not. Just open a pull request. If your code looks good and doesn’t break the fragile ecosystem we slapped together, we might just merge it.

Now go forth and create the memes of your dreams (and nightmares).
