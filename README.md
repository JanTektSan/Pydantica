# medit

A command-line tool that uses AI to help you generate and execute ImageMagick and FFmpeg 
commands using natural language instructions. This is an example CLI application with agentic workflow.

## Features

- Natural language interface for image and video processing
- Supports both ImageMagick and FFmpeg commands
- Command queue management (add, list, execute)
- Smart command combination and optimization
- Clear, user-friendly output with execution status

## Installation

1. Ensure you have Python 3.8+ installed
2. Install required dependencies:
```bash
pip install -r requirements.txt
```
3. Make sure ImageMagick and FFmpeg are installed on your system:
   - For macOS: `brew install imagemagick ffmpeg`
   - For Linux: `apt-get install imagemagick ffmpeg`
   - For Windows: Download from respective websites

## Usage

Run the tool:
```bash
python medit.py
```

Available commands:
- Type your instructions in natural language
- Use `list` to show current command queue
- Use `run` to execute commands
- Type `exit` to quit

### Examples

```bash
Welcome to medit!
Enter your instructions in natural language. Type 'exit' to quit.
Commands: 'list' to show commands, 'run' to execute them, 'exit' to quit.

> take snow.jpeg and make it into a pencil sketch named sketch.jpg
Added ImageMagick command: magick snow.jpeg -colorspace Gray -sketch 0x20+1.0+0.0 sketch.jpg
> convert sketch.jpg to sketch.png
Added ImageMagick command: magick sketch.jpg sketch.png
> change the width of sketch.png to 800px
Added ImageMagick command: magick sketch.png -resize 800x sketch_resized.png
> run it
Combining commands...
Current commands:
  1. magick snow.jpeg -colorspace Gray -sketch 0x20+1.0+0.0 sketch.jpg
  2. magick sketch.jpg sketch.png
  3. magick sketch.png -resize 800x sketch_resized.png
Combined commands:
  1. magick snow.jpeg -colorspace Gray -sketch 0x20+1.0+0.0 -resize 800x sketch_resized.png
Executing commands...
Executing: magick snow.jpeg -colorspace Gray -sketch 0x20+1.0+0.0 -resize 800x sketch_resized.png
✓
All commands executed successfully
>
```

### Supported Operations

#### ImageMagick
- Format conversion
- Resize images
- Adjust brightness/contrast
- Apply filters and effects
- Crop and rotate
- And more...

#### FFmpeg
- Video format conversion
- Extract frames from video
- Combine frames into video
- Adjust video properties
- And more...

## Architecture

The application uses multiple AI agents to process and execute commands:

1. **Routing Agent**: Analyzes instructions and routes to appropriate agents
2. **ImageMagick Agent**: Generates ImageMagick commands
3. **FFmpeg Agent**: Generates FFmpeg commands
4. **Combining Agent**: Optimizes and sequences commands
5. **Executing Agent**: Safely executes commands with status feedback

