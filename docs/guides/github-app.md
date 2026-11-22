# GitHub App token helper

`ginflow gh token` mints short-lived GitHub App installation tokens, so a cloud-agents container needs only the App private key, never a personal access token (ADR `docs/adrs/0003-cloud-agents.md`).

One App serves every repository it is granted. A grant belongs to an installation (one per account or org); an installation token covers all repos in it. Ginflow maps repos to installations and caches tokens per installation.

## App setup

Permissions: Contents, Issues, Pull requests (read/write); Metadata (read).

Events: Issues, Issue comment, Pull request, Pull request review, Pull request review comment, Installation repositories.

Install the App on each account or org whose repos agents may touch, and mount the private key PEM read-only into the container.

## Environment

| Variable | Meaning | Default |
| --- | --- | --- |
| `GINFLOW_GH_APP_ID` | App id | required |
| `GINFLOW_GH_APP_KEY` | private key PEM path | `/run/secrets/gh-app.pem` |
| `GINFLOW_GH_INSTALLATION_ID` | installation used when no repo is given (single-installation setups) | optional |
| `GINFLOW_GH_API` | API base URL | `https://api.github.com` |
| `GINFLOW_GH_CACHE` | token cache dir | `$HERMES_HOME/cache/ginflow-gh` |

Requires the `openssl` binary. The cache dir is mode 0700, files 0600. A cached token is reused while more than 300 s remain.

## Usage

```sh
ginflow gh token --repo owner/repo     # resolves the installation, prints the token
ginflow gh token --installation 7      # explicit installation
```

Output is the token and a newline only. Errors go to stderr as `fail token: <reason>` with exit 1 (for example `App not installed on owner/repo`).

## git credential helper

```sh
git config --global credential.https://github.com.helper '!ginflow gh token credential'
git config --global credential.useHttpPath true
```

`useHttpPath` lets git pass `path=owner/repo.git`, so each repo gets its own installation's token. For `gh`:

```sh
GH_TOKEN="$(ginflow gh token --repo owner/repo)" gh issue comment ...
```

The container wrapper that sets this up belongs to CLOUD-1.8.
