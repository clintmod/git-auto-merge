# git-auto-merge

A tool to automatically merge git branches.

# Features

- Automatically merge branches in a git repo
- 

# Installation

# Usage

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
