# MemeCat

Welcome to **MemeCat**—the purr-fect CLI tool that slaps automated, stylish, and completely unnecessary captions all over your videos. Why pay for fancy pants video editors when all you need are sweet, sweet subtitles you can do at the command line like the true keyboard warrior you are?

MemeCat extracts the audio from your video, uses [OpenAI’s Whisper](https://github.com/openai/whisper) to transcribe it, and then sprinkles those words right in the middle of your screen in **BIG, LOUD TEXT**. Give your videos that *"TikTok influencer meets basement meme lord"* energy with no fuss, no frills, and a blatant disregard for complex licensing fees.

## Features

- **Automatic Transcription:** Leverages Whisper to translate the weird mumbling from your video into actual words.
- **Customizable Fonts & Sizes:** Because your life’s calling is to find the perfect font size that says, “I’m screaming, and so is this caption.”
- **Automatic Effects based on Captions:** Base font style, emojis, etc. off of specific words or concepts you set. It uses AI just so you know it's 2025.

## To the Corporate ppl Reading This (yes you ByteDance)

This is only the expression of an idea or set of ideas that I had over a very short period of time. It would be stupid to try to just use my source code and incorporate it into a money making application. Consider hiring me or consulting because there are so many breakthrough ideas I have and know how to implement in this app... It would be in your best interest to invite me around rather than just cash grab steal my code. The resource is not the code, it is me, my experience, my programming art, and my professionalism which is the real value and return on investment. Consider contacting me.

## Requirements

1. **Python 3.x**: Because it's not 1995.
2. **FFmpeg**: Don’t worry, it’s basically on every Linux machine already. If not:
   ```bash
   sudo apt-get update && sudo apt-get install ffmpeg
   ```
3. **Whisper**: For text to speech (the correct one, not the bootleg knockoff):
   ```bash
   pip install --upgrade openai-whisper
   ```
4. **Lib ASS**: The Aegisub library. Yes, you read that right.

## Installation on Linux

```bash
sudo apt-get install libass-dev
git clone https://github.com/newsbubbles/MemeCat.git
cd MemeCat
pip install -r requirements.txt
```

## Installation on Windows

... just the part after `sudo`?

*yeah, I don't use windows.*

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

**Use a custom bucket YAML file:**
```bash
python memecat.py --input_video input.mp4 --output_video output.mp4 --config "path/to/bucket.yml"
```

**Use the sentiment bucket:**
```bash
python memecat.py --input_video input.mp4 --output_video output.mp4 --config "buckets/sentiment.yml"
```

**Pick a Different Model (Because ‘size’ matters):**
```bash
python memecat.py --input_video input.mp4 --output_video bigbrain.mp4 --model medium
```

## Why MemeCat?

- Because paying for a full-fledged NLE to add some freakin’ subtitles is like buying a private jet to visit your neighbor.
- Because we stand for the open-source spirit of doing something incredibly niche without any sane reason.
- Because cats are meme kings. Duh.

## More about the `.yml` Files....

There are two sample files in the buckets folder. These files allow you to change the way that the captions appear on a word or phrase basis. Take a look at [buckets/nate.yml](buckets/nate.yml) to see more instructions and examples of one where I got all wild with my editing.

## License

MIT—meaning do whatever you want and don’t blame us if your cringey subtitles scare off your viewers.

## Contributing

Sure, why not. Just open a pull request. If your code looks good and doesn’t break the fragile ecosystem we slapped together, we might just merge it.

Now go forth and create the memes of your dreams (and nightmares).
