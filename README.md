# `otter-pensieve`

`otter-pensieve` is a plugin for [`otter-grader`](
https://github.com/ucbds-infra/otter-grader) allowing the otter autograder to
upload submission PDFs to Pensieve on students' behalfs.

## Installation

```bash
pip install otter-pensieve
```

## Testing

```bash
python -m unittest
```

## Configuration

1. Remove any existing Gradescope configuration from your otter notebook. This
   includes the `course_id`, `assignment_id`, and `token` keys under
   `generate`:

   ```yaml
   # ASSIGNMENT CONFIG
   generate:
     token: YOUR_TOKEN # remove this
     course_id: 1234 # remove this
     assignment_id: 5678 # remove this
   ```

2. Add `otter-pensieve` as a requirement for your otter notebook:

   ```yaml
   # ASSIGNMENT CONFIG
   requirements:
     - otter-pensieve
   ```

3. Add `otter_pensieve.PensieveOtterPlugin` as a plugin in your otter notebook:

   ```yaml
   # ASSIGNMENT CONFIG
   generate:
     plugins:
       - otter_pensieve.PensieveOtterPlugin
   ```

4. On the Pensieve webapp, navigate to your otter-based programming assignment,
   navigate to the "Configure" page, and select an "Associated Paper
   Assignment". This is the assignment to which `otter-pensieve` will make
   submissions.

   Note: `otter-pensieve` will only be able to make submissions when running on
   Pensieve infrastructure.

## Otter Assign

When running `otter assign`, you **must not** provide `--username` or
`--password` options.

## Links

* [PyPI Project](https://pypi.org/project/otter-pensieve)
* [GitHub Repo](https://github.com/pensieve-ai/otter-pensieve)
