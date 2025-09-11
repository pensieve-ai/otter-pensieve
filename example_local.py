#!/usr/bin/env python3
"""
Example usage of the otter_pensieve_local script.
"""

import json
from pathlib import Path

import otter_pensieve_local as opl


def example_basic():
    """Basic example processing a single notebook."""
    print("Example 1: Basic processing")
    print("-" * 50)

    # Replace with your actual notebook path
    notebook_path = "/Users/qria/Downloads/test-labs/columbia Yi/Sample Submissions/Exercise 2 Solution/Exercise 2.ipynb"

    # Process the notebook
    result = opl.process_notebook(notebook_path=notebook_path, verbose=True)

    print(f"\nProcessing complete!")
    print(f"- PDF: {result['pdf_path']}")
    print(f"- Metadata: {result['metadata_path']}")

    # Read and display metadata summary
    with open(result["metadata_path"]) as f:
        metadata = json.load(f)

    print(f"\nMetadata summary:")
    print(f"- Questions found: {metadata['num_questions']}")
    for q in metadata["questions"]:
        print(
            f"  - Question {q['index'] + 1}: cells {q['begin']['cell_index']} to {q['end']['cell_index']}"
        )
    print(f"- Page indices: {metadata['page_indices']}")

    return result


def example_custom_paths():
    """Example with custom output paths."""
    print("\nExample 2: Custom output paths")
    print("-" * 50)

    notebook_path = "/Users/qria/Downloads/test-labs/columbia Yi/Sample Submissions/Exercise 2 Solution/Exercise 2.ipynb"

    # Process with custom paths
    result = opl.process_notebook(
        notebook_path=notebook_path,
        output_pdf_path="custom_output.pdf",
        output_metadata_path="custom_metadata.json",
        verbose=True,
    )

    return result


def example_batch_processing():
    """Example processing multiple notebooks."""
    print("\nExample 3: Batch processing")
    print("-" * 50)

    # List of notebooks to process
    notebooks = [
        # Add your notebook paths here
        "/path/to/notebook1.ipynb",
        "/path/to/notebook2.ipynb",
    ]

    results = []
    for notebook_path in notebooks:
        if Path(notebook_path).exists():
            try:
                print(f"\nProcessing: {notebook_path}")
                result = opl.process_notebook(notebook_path, verbose=False)
                results.append(result)
                print(f"✓ Success: {result['pdf_path']}")
            except Exception as e:
                print(f"✗ Error: {e}")
        else:
            print(f"✗ Skipping (not found): {notebook_path}")

    return results


def example_api_usage():
    """Example using individual functions directly."""
    print("\nExample 4: Direct API usage")
    print("-" * 50)

    import nbformat

    notebook_path = "/Users/qria/Downloads/test-labs/columbia Yi/Sample Submissions/Exercise 2 Solution/Exercise 2.ipynb"

    # Load notebook
    with open(notebook_path) as f:
        notebook = nbformat.read(f, as_version=4)

    # Parse questions
    parsed = opl.parse_notebook(notebook)
    print(f"Found {len(parsed.questions)} questions")

    # Process each question individually
    for i, question in enumerate(parsed.questions):
        print(f"\nQuestion {i + 1}:")
        print(
            f"- Begin: cell {question.begin.cell_index}, line {question.begin.line_index}"
        )
        print(f"- End: cell {question.end.cell_index}, line {question.end.line_index}")

        # Slice notebook
        slice_nb = opl.slice_notebook(notebook, question)

        # Extract answer
        answer = opl.extract_answer(slice_nb)
        print(f"- Answer parts: {len(answer.parts)}")
        for j, part in enumerate(answer.parts):
            if part.content_type == "text":
                preview = part.content[:50].replace("\n", " ")
                print(f"  - Part {j}: {part.content_type} - {preview}...")
            else:
                print(f"  - Part {j}: {part.content_type}")


def main():
    """Run examples."""
    import os

    # Check if example notebook exists
    example_notebook = "/Users/qria/Downloads/test-labs/columbia Yi/Sample Submissions/Exercise 2 Solution/Exercise 2.ipynb"

    if os.path.exists(example_notebook):
        # Run basic example
        example_basic()

        # Uncomment to run other examples
        # example_custom_paths()
        # example_api_usage()
    else:
        print(f"Example notebook not found at: {example_notebook}")
        print("Please update the notebook_path with your actual notebook path")
        print("\nCommand line usage:")
        print("  python otter_pensieve_local.py notebook.ipynb")
        print(
            "  python otter_pensieve_local.py notebook.ipynb -o output.pdf -m metadata.json -v"
        )


if __name__ == "__main__":
    main()
