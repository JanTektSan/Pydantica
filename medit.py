#!/usr/bin/env python3
from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from rich.console import Console
from rich.prompt import Prompt
import subprocess
import shlex
from dotenv import load_dotenv

load_dotenv()

console = Console()

@dataclass
class CommandDependencies:
    commands: List[str] = None
    current_instruction: str = ""

    def __post_init__(self):
        if self.commands is None:
            self.commands = []

class CommandResult(BaseModel):
    command: Optional[str] = Field(None, description="Generated command")
    tool: Optional[str] = Field(None, description="Tool to use (imagemagick/ffmpeg)")
    action: str = Field(description="Next action (route/combine/execute)")
    commands: Optional[List[str]] = Field(None, description="List of commands to execute")
    success: Optional[bool] = Field(None, description="Whether the command execution was successful")
    error: Optional[str] = Field(None, description="Error message if command failed")

# Routing Agent
routing_agent = Agent(
    "openai:gpt-4o-mini",
    deps_type=CommandDependencies,
    result_type=CommandResult,
    retries=3,
    system_prompt=r"""
    You are a routing agent that:
    1. Analyzes user instructions to determine if they need ImageMagick or FFmpeg
    2. Routes instructions to the appropriate agent
    3. Stores commands in sequence
    4. Routes to combining agent when user wants to execute commands
    5. Routes to executing agent after combining agent returns combined commands

    When receiving a user instruction, analyze it and return:
    - For image processing tasks:
      action: "route"
      tool: "imagemagick"
    
    - For video processing tasks:
      action: "route"
      tool: "ffmpeg"
    
    - When user mentions "execute", "run", or similar execution commands:
      action: "combine"
    
    - When user asks to see, show, or list commands:
      action: "list"
    
    - When handling combined commands for execution:
      action: "execute"
      commands: [list of commands to execute]
      
    Important: When receiving combined commands from the combining agent,
    ALWAYS return them in the 'commands' field with action='execute'.
    """
)

# ImageMagick Agent
imagemagick_agent = Agent(
    "openai:gpt-4o-mini",
    deps_type=CommandDependencies,
    result_type=CommandResult,
    system_prompt=r"""
    You are an ImageMagick expert that generates correct ImageMagick commands.
    Always return the complete command with all necessary parameters.
    Use the 'magick' command which is the newer ImageMagick 7 syntax.
    ImageMagick documentation can be found at 
    https://imagemagick.org/script/command-line-processing.php

    Important rules:
    1. For format conversion, use: magick input.jpg output.png
    2. For resize operations:
       - Fixed width: magick input.jpg -resize WIDTHx output.jpg
       - Fixed height: magick input.jpg -resize xHEIGHT output.jpg
       - Both: magick input.jpg -resize WIDTHxHEIGHT output.jpg
    3. For getting dimensions: magick identify -format '%wx%h' image.jpg
    4. Always verify input files exist before operating on them
    5. Use proper quoting for commands with special characters
    6. When using shell commands within ImageMagick, properly escape them
    7. Don't use 'convert' command, use 'magick' instead
    8. Always specify output filename with appropriate extension
    """
)

# FFmpeg Agent
ffmpeg_agent = Agent(
    "openai:gpt-4o-mini",
    deps_type=CommandDependencies,
    result_type=CommandResult,
    system_prompt=r"""
    You are an FFmpeg expert that generates correct FFmpeg commands.
    Always return the complete command with all necessary parameters.
    Include appropriate codec parameters and quality settings. FFmpeg
    documentation can be found at https://ffmpeg.org/ffmpeg.html

    Important rules:
    1. For frame extraction, use: ffmpeg -i input.mp4 -vf "select=between(n\\,start_frame,end_frame)" -vsync vfr frame_%03d.png
    2. For combining frames into video: ffmpeg -framerate 30 -pattern_type glob -i '*.png' -c:v libx264 -pix_fmt yuv420p output.mp4
    3. Always specify output filenames that don't conflict with inputs
    4. Use proper escaping for filter expressions
    """
)

# Combining Agent
combining_agent = Agent(
    "openai:gpt-4o",
    deps_type=CommandDependencies,
    result_type=CommandResult,
    retries=3,
    system_prompt=r"""
    You are an expert at combining ImageMagick and FFmpeg commands.
    Your job is to analyze the commands, optimize them, and return them in the correct execution order.

    Important rules:
    1. Analyze dependencies between commands:
       - If a command creates a file used by another command, order them correctly
       - If a command needs information from another command, combine them appropriately
    2. For ImageMagick commands:
       - Combine multiple operations on the same file into a single command
       - Use proper syntax: magick input.jpg [operations] output.jpg
    3. For FFmpeg commands:
       - Combine filter chains when possible
       - Maintain proper input/output file order
    4. Return the optimized commands in the 'commands' field as a list
    5. Never return an empty command list
    6. If commands can't be optimized further, return them in the original order
    7. Always verify each command is complete and properly formatted
    
    Example optimizations:
    1. Combining resize and format conversion:
       Input commands:
         magick input.jpg output.png
         magick output.png -resize 400x output_resized.png
       Optimized:
         magick input.jpg -resize 400x output_resized.png
    
    2. Handling dimension queries:
       Input commands:
         magick identify -format '%wx%h' input.jpg
         magick input.jpg -resize 400x output.jpg
       Optimized:
         magick input.jpg -resize 400x output.jpg
    
    Return the optimized commands in the 'commands' field.
    """
)

# Executing Agent
executing_agent = Agent(
    "gemini-2.0-flash",
    deps_type=CommandDependencies,
    result_type=CommandResult,
    retries=3,
    system_prompt=r"""
    You are an expert at executing ImageMagick and FFmpeg commands.
    You receive a list of commands and execute them in sequence using the execute_command tool.
    
    Important rules:
    1. Execute each command in sequence
    2. Stop if any command fails
    3. Return execution status and any errors
    4. Do not add any verification commands
    
    Return execution results in the response:
    - success: true/false indicating if all commands succeeded
    - error: error message if any command failed
    - command: summary of execution
    """
)

@executing_agent.tool_plain
async def execute_command(command: str) -> str:
    """Execute a shell command and return the result."""
    console.print(f"[dim]Executing: {command}[/dim]")
    success, output = execute_shell_command(command)
    if success:
        console.print("[green]✓[/green]")
    else:
        console.print(f"[red]✗ {output}[/red]")
    return output

def execute_shell_command(command: str) -> tuple[bool, str]:
    """Execute a shell command and return success status and output/error."""
    try:
        process = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            check=True
        )
        return True, "Command executed successfully"
    except subprocess.CalledProcessError as e:
        return False, f"Error: {e.stderr}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def display_commands(commands: List[str], title: str = "Current commands:") -> None:
    """Display the list of commands with numbers."""
    if commands:
        console.print(f"[yellow]{title}[/yellow]")
        for i, cmd in enumerate(commands, 1):
            console.print(f"  {i}. [dim]{cmd}[/dim]")
    else:
        console.print("[yellow]No commands in queue[/yellow]")

class MPrompt(Prompt):
    prompt_suffix = "> "

async def main():
    console.print("[bold blue]Welcome to medit![/bold blue]")
    console.print("Enter your instructions in natural language. Type 'exit' to quit.")
    console.print("Commands: 'list' to show commands, 'run' to execute them, 'exit' to quit.\n")
    
    deps = CommandDependencies()
    
    while True:
        instruction = MPrompt.ask("")
        if instruction.lower() == 'exit':
            break
            
        deps.current_instruction = instruction
        
        try:
            # First, use routing agent to determine next action
            result = await routing_agent.run(instruction, deps=deps)
            
            if result.data.action == "route":
                if result.data.tool == "imagemagick":
                    # Route to ImageMagick agent
                    img_result = await imagemagick_agent.run(instruction, deps=deps)
                    if img_result.data.command:
                        deps.commands.append(img_result.data.command)
                        console.print(f"[green]Added ImageMagick command:[/green] [dim]{img_result.data.command}[/dim]")
                        
                elif result.data.tool == "ffmpeg":
                    # Route to FFmpeg agent
                    ff_result = await ffmpeg_agent.run(instruction, deps=deps)
                    if ff_result.data.command:
                        deps.commands.append(ff_result.data.command)
                        console.print(f"[green]Added FFmpeg command:[/green] [dim]{ff_result.data.command}[/dim]")
            
            elif result.data.action == "list":
                display_commands(deps.commands)
                        
            elif result.data.action == "combine":
                if deps.commands:
                    console.print("[yellow]Combining commands...[/yellow]")
                    display_commands(deps.commands)
                    
                    # Route to combining agent to combine commands
                    combine_result = await combining_agent.run(
                        "Optimize and sequence these commands:\n" + "\n".join(
                            f"{i}. {cmd}" for i, cmd in enumerate(deps.commands, 1)
                        ), 
                        deps=deps
                    )

                    if combine_result.data.commands:
                        display_commands(combine_result.data.commands, "Combined commands:")
                            
                        # Route combined commands directly to executing agent
                        console.print("[yellow]Executing commands...[/yellow]")
                        exec_result = await executing_agent.run(
                            "Execute these commands:\n" + "\n".join(
                                f"{i}. {cmd}" for i, cmd in enumerate(combine_result.data.commands, 1)
                            ),
                            deps=deps
                        )
                        
                        if exec_result.data.success:
                            console.print("[green]All commands executed successfully[/green]")
                        else:
                            console.print(f"[red]Execution error: {exec_result.data.error}[/red]")
                        
                        deps.commands.clear()
                    else:
                        console.print("[red]Error: Failed to combine commands[/red]")
                        console.print(f"Combining agent response: {combine_result.data}")
                else:
                    console.print("[yellow]No commands to execute[/yellow]")
                    
        except Exception as e:
            console.print(f"[red]Error processing instruction:[/red] {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
