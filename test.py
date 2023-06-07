import re

string = "release/prefix-1000.1000.1000-codename"
pattern = r"(\d+\.\d+\.\d+)"

match = re.search(pattern, string)
if match:
    version = match.group(1)
    print(version)
else:
    print("No version found.")
