from typing import Type
import os
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class FileWriteInput(BaseModel):
    """Input schema for the file writer tool."""
    content: str = Field(..., description="The content to write to file")
    filepath: str = Field(..., description="The relative or absolute file path to write")
    directory: str = Field(default="output", description="The base directory (e.g., output/blogs)")


class FileWriterTool(BaseTool):
    name: str = "file_writer"
    description: str = (
        "Writes content to a file in the specified directory. Creates directories if they "
        "don't exist. Used to save blog posts and reports to disk."
    )
    args_schema: Type[BaseModel] = FileWriteInput

    def _run(self, content: str, filepath: str, directory: str = "output") -> str:
        try:
            full_path = os.path.join(directory, filepath)
            os.makedirs(os.path.dirname(full_path) if os.path.dirname(full_path) else directory, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {full_path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"
