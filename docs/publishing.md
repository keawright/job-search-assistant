# Publishing code without personal data

Only source code, tests, documentation, synthetic examples, and GitHub Actions
configuration belong in this repository. Spreadsheets are local application data,
including the seed workbook, generated queues, and archive copies. They must not
be committed. Resume documents (PDF/Word) and the local TASK.md handoff are
also blocked. Personal URL lists, private snapshots, candidate data, credentials,
environment files, database files, and local environments are excluded too.

Before each commit:

```powershell
git add .gitignore .gitattributes README.md pyproject.toml docs examples src tests tools .github
python tools/check_repository.py
git diff --cached --stat
git diff --cached
```

The guard checks the actual staged blobs, including files force-added against
ignore rules. It blocks spreadsheet/private-data filenames, binary files,
private-key blocks, common provider-token patterns, credential assignments, and
credentials embedded in URLs. Reports identify a filename and issue type without
printing the matching value. It cannot detect every secret or every kind of
personal information; review the staged content as well.

GitHub Actions runs the same privacy guard and pytest with synthetic data, read-only
repository permissions, and no application credentials. CI runs after code is
pushed, so local checks and review remain the protection before first publication.

Authenticate to GitHub through a browser/device flow or an OS credential manager.
Never paste access tokens into tracked configuration, command-line remote URLs,
test fixtures, issues, or chat. Use a repository URL without embedded credentials.
Git identity is stored in the local `.git/config`, outside tracked content.

If a real secret was ever committed, removing it in a later commit is insufficient:
revoke/rotate it and remove it from history before publication. Ignore patterns
do not remove tracked files or rewrite previous commits.
