# The hub server's GitHub App

Every team runs its own instance of the hub server with an App of its own. One command
registers the App from the manifest the package ships, through GitHub's manifest flow.

## Registering the App

Name the directory the instance keeps its key and secrets in, then run the command with the
owner of the App and the address GitHub delivers events to:

```bash
export BASSTLER_HUB_SECRET_DIRECTORY=/path/to/secrets
python -m basstler.hub_server register-app <owner> --webhook-url https://<instance>/webhook
```

The command opens your browser on GitHub's registration page with the manifest filled in.
Confirm the App there; GitHub sends the browser back to the command, which writes one file
for each secret into the directory, readable by you alone: `app-id`, `client-id`,
`client-secret`, `webhook-secret` and `private-key.pem`.

- `<owner>` is an organization. Add `--personal-account` when it is your own account.
- The App is named `<owner>-basstlerhub` unless `--name` gives another; GitHub keeps App names
  unique across all owners.
- The App is private: it can be installed only on its owner's account.
- It asks for read-only access to metadata, contents, pull requests, checks and statuses, and
  receives the events `push`, `pull_request`, `pull_request_review`,
  `pull_request_review_thread`, `check_suite`, `status`, `issue_comment` and
  `installation_repositories`.
- A directory that already holds an App's secrets is never overwritten; the command stops
  before it opens the browser.

GitHub converts the code the browser returns only once, so a registration that fails after
the browser step leaves an App on GitHub whose key was never saved: delete that App in its
settings and run the command again.
