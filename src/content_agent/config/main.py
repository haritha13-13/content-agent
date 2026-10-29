#!/usr/bin/env python
import sys
import warnings
import os

from pathlib import Path

# Ensure we can find the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content_agent.crew import ContentGenerationCrew
from content_agent.helpers import keyword_slug

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

DEFAULT_KEYWORD = "accounting automation"
DEFAULT_COUNTRY = "Malaysia"


def run(keyword: str = DEFAULT_KEYWORD, country: str = DEFAULT_COUNTRY):
    """
    Run the content generation crew.
    Generates a full blog post with title, meta description, and internal links
    based on the Speedbots content strategy.
    """
    inputs = {
        'keyword': keyword,
        'country': country,
        'keyword_slug': keyword_slug(keyword),
    }

    print("=" * 60)
    print(f"Speedbots Content Generation Agent")
    print(f"Keyword: {keyword}")
    print(f"Country: {country}")
    print("=" * 60)

    try:
        result = ContentGenerationCrew().crew().kickoff(inputs=inputs)
        print("\n" + "=" * 60)
        print("CONTENT GENERATION COMPLETE")
        print("=" * 60)
        print(result)
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        'keyword': DEFAULT_KEYWORD,
        'country': DEFAULT_COUNTRY,
        'keyword_slug': keyword_slug(DEFAULT_KEYWORD),
    }
    try:
        ContentGenerationCrew().crew().train(
            n_iterations=int(sys.argv[1]),
            filename=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        ContentGenerationCrew().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        'keyword': DEFAULT_KEYWORD,
        'country': DEFAULT_COUNTRY,
        'keyword_slug': keyword_slug(DEFAULT_KEYWORD),
    }
    try:
        ContentGenerationCrew().crew().test(
            n_iterations=int(sys.argv[1]),
            eval_llm=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


if __name__ == "__main__":
    run()
