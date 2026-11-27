# basstler-hub-server

The plan service: one container that receives a GitHub App's webhooks. It runs on any
container host. Every team runs its own instance, with its own App, and no instance
holds another team's key or data.

Each release publishes the image to the GitHub Container Registry of the repository it
was released from:

```
ghcr.io/<owner>/<repository>/basstler-hub-server:<version>
```

`latest` names the newest release.

## Settings

An instance reads three settings when it starts. Each one is given either in its
variable, or as a file whose path is in the same variable with `_FILE` appended. The
file form is how container hosts mount secrets. A file's final newline is not part of
the value.

| Variable | Holds |
| --- | --- |
| `BASSTLER_HUB_APP_ID` | the numeric ID of the GitHub App the instance acts as |
| `BASSTLER_HUB_PRIVATE_KEY` | the App's private key, in PEM |
| `BASSTLER_HUB_WEBHOOK_SECRET` | the secret GitHub signs the App's deliveries with |

An instance missing one of them stops at once and names the setting it lacks. The
instance listens on `PORT` (8080 when unset) and answers two routes:

- `GET /health` answers `200` once the instance has started.
- `POST /webhooks` receives the App's deliveries. A delivery whose
  `X-Hub-Signature-256` does not match the webhook secret is refused with `401`.

Point the App's webhook URL at `https://<your instance>/webhooks`.

## Running it with Docker

```bash
docker run -d -p 8080:8080 \
  -e BASSTLER_HUB_APP_ID=<app id> \
  -e BASSTLER_HUB_PRIVATE_KEY_FILE=/run/secrets/private-key.pem \
  -e BASSTLER_HUB_WEBHOOK_SECRET_FILE=/run/secrets/webhook-secret \
  -v /path/to/secrets:/run/secrets:ro \
  ghcr.io/<owner>/<repository>/basstler-hub-server:<version>
```

The instance runs as `nobody`, so the mounted files must be readable by every user.

To build the image from a checkout instead, run this from the repository's root:

```bash
docker build -f packages/hub-server/Dockerfile --build-arg VERSION=<version> -t basstler-hub-server .
```

## Deploying to Cloud Run

You need the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install), signed in to
an account that can administer the project. Install the server with
`pip install basstler-hub-server`, then run:

```bash
python -m basstler.hub_server deploy-cloud-run \
  --project <project> --region <region> --service <service> \
  --image ghcr.io/<owner>/<repository>/basstler-hub-server:<version> \
  --app-id <app id> \
  --private-key-file <app>.private-key.pem --webhook-secret-file <webhook secret file>
```

The command does everything a deployment needs, and each step is safe to repeat:

1. It enables the Cloud Run, Secret Manager and Artifact Registry APIs.
2. It uploads each file given as the newest version of its secret
   (`basstler-hub-private-key`, `basstler-hub-webhook-secret`), creating the secret on
   the first deployment. Leave a file out to keep the version the secret already holds.
3. It lets the service's account read both secrets. That account is
   `--service-account`, or else the project's default compute account.
4. It creates an Artifact Registry repository, `ghcr`, that proxies ghcr.io. Cloud Run
   cannot pull from ghcr.io directly, so it pulls the same image through that
   repository. The image's package must be public on GitHub.
5. It deploys the service as a single instance, open to unauthenticated requests:
   GitHub's deliveries carry no Google credential, and their signature is what
   authenticates them.

The command prints the image it deployed. Cloud Run prints the service's URL.

## Receiving webhooks on your own machine

[`gh webhook forward`](https://docs.github.com/en/webhooks/testing-and-troubleshooting-webhooks/using-the-github-cli-to-forward-webhooks-for-testing)
relays a repository's or an organization's deliveries to a local instance, signed with
the secret you give it:

```bash
gh extension install cli/gh-webhook
BASSTLER_HUB_APP_ID=<app id> BASSTLER_HUB_PRIVATE_KEY_FILE=<app>.private-key.pem \
  BASSTLER_HUB_WEBHOOK_SECRET=<secret> python -m basstler.hub_server serve
gh webhook forward --repo=<owner>/<repository> --events=push,pull_request \
  --url=http://localhost:8080/webhooks --secret=<secret>
```

Run the two commands in separate terminals. The relay is a webhook of the repository
itself, not of the App, so it sees only the events you name.
