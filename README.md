# git-auto-merge

A tool to automatically merge git branches.

# Features

- Automatically merge branches in a git repo
- Based a config file checked in to the target repo
- Captures emails when a conflict is detected
- Generates a json report of problems
- Prints a plan
- Can be executed in dry run mode (doesn't push changes)
- Supports monorepo

# Installation

```

git clone https://github.com/clintmod/git-auto-merge.git
make

```

Or you can pull the docker images: 

```
docker pull clintmod/git-auto-merge
```

# Usage

```
Usage: git-auto-merge [OPTIONS]

  A tool to automatically merge git branches.

Options:
  -r, --repo TEXT              The git repository to operate on  [required]
  -w, --work-dir TEXT          The directory to use for the git repo  [default: workdir]
  -l, --log-level TEXT         The log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  -cb, --config-brach TEXT     The branch in the git repository to use for the .git-auto-merge.json config file  [default: main]
  -c, --config-file-name TEXT  The name of the config file to use  [default: .git-auto-merge.json]
  -udp, --use-default-plan     Use the default plan from the .git-auto-merge.json config file in this git repository
  -d, --dry-run                This mode will do everything except git push
  --help                       Show this message and exit.

```

# Example

Based on this `.git-auto-merge.json` file in the default branch of a repo:

```
{
  "version": 1,
  "plan": {
    "root": {
      "selectors": [
        {"name": "main"}
      ],
      "downstream": {
        
        "release": {
          "sort": "version",
          "selectors": [
            {"regex": "^hotfix/.*(?:(\\d+\\.[.\\d]*\\d+)).*"},
            {"regex": "^release/.*(?:(\\d+\\.[.\\d]*\\d+)).*"}
          ],
          "downstream": {
            "develop": {
              "selectors": [
                {"name": "develop"}
              ],
              "downstream": {
                "feature": {
                  "selectors": [
                    {"regex": "^feature/.*"}
                  ]
                }
              }
            }
          }
        }
      }
    }
  }
}

```

This util would merge code like below: 


```
main -> hotfix/1.0.1 -> release/2.0.0 -> develop -> feature/*

```
