from typing import Type
import os
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class FileReadInput(BaseModel):
    """Input schema for the file reader tool."""
    filepath: str = Field(..., description="The relative or absolute file path to read")
    directory: str = Field(default="output", description="The base directory (e.g., output/blogs)")


class FileReaderTool(BaseTool):
    name: str = "file_reader"
    description: str = (
        "Reads the contents of a file in the specified directory. Used to load an "
        "existing blog post or report from disk so it can be reviewed or optimized."
    )
    args_schema: Type[BaseModel] = FileReadInput

    def _run(self, filepath: str, directory: str = "output") -> str:
        try:
            full_path = os.path.join(directory, filepath)
            if not os.path.exists(full_path):
                return f"Error: file not found at {full_path}"
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content
        except Exception as e:
            return f"Error reading file: {str(e)}"