# Deploying the remote server

The container image serves MCP over Streamable HTTP on port 8080. It refuses to start without
an authentication mode, so an exposed instance is never open.

## Choose how people authenticate

| Mode | Set | Who it is for |
|---|---|---|
| **Sign in with Google** | `QUANTUM_ADS_AUTH=google` | A team: each person signs in with their own Google account and acts with their own access |
| Your identity provider | `QUANTUM_ADS_OAUTH_JWKS_URI` + `QUANTUM_ADS_OAUTH_ISSUER` | An organisation with Okta/Entra/Auth0 tokens and a tenants map |
| Local issuer | `QUANTUM_ADS_OAUTH_PUBLIC_KEY_FILE` (`quantum-ads-mcp keygen` / `token`) | A few machine clients you mint tokens for |

### Sign in with Google

The server acts as an OAuth proxy in front of Google. MCP clients register themselves (Dynamic
Client Registration or a Client ID Metadata Document); the user logs in at Google and consents.
The server never sees a password. It keeps the user's Google token encrypted and uses it only to
act as that user, and the user can revoke it at any time from their Google account.

1. In Google Cloud Console, create an OAuth client of type **Web application** with the
   authorised redirect URI `https://<your host>/auth/callback`.
2. Set:

   ```bash
   QUANTUM_ADS_AUTH=google
   QUANTUM_ADS_PUBLIC_URL=https://<your host>
   QUANTUM_ADS_GOOGLE_CLIENT_ID=....apps.googleusercontent.com
   QUANTUM_ADS_GOOGLE_CLIENT_SECRET=...
   QUANTUM_ADS_GOOGLE_ALLOWED=@youragency.com,partner@example.com   # required: who may sign in
   QUANTUM_ADS_GOOGLE_WRITERS=lead@youragency.com                   # may write; others read only
   QUANTUM_ADS_JWT_SIGNING_KEY=<random 32+ bytes>                   # stable across restarts/replicas
   GOOGLE_ADS_DEVELOPER_TOKEN=...                                   # the operator's, shared
   QUANTUM_ADS_READ_ONLY=false                                      # writers can then write
   ```

   `QUANTUM_ADS_GOOGLE_SCOPES` (comma-separated) overrides the requested scopes; the default is
   Google Ads, GA4 edit, Tag Manager edit, Merchant, Search Console and YouTube read.
3. A user's requests then run on their own Google token: they reach exactly the accounts their
   Google identity can reach. The operator's refresh tokens and client secrets are never handed
   to a signed-in user.

Google requires verifying the OAuth app before more than 100 external users can consent to the
sensitive marketing scopes; inside one Google Workspace organisation, mark the app *Internal*.

## Cloud Run

Cloud Run pulls from Artifact Registry. Mirror the public image through a remote repository
once, then deploy:

```bash
gcloud artifacts repositories create ghcr --repository-format=docker --location=europe-west1 \
  --mode=remote-repository --remote-docker-repo=https://ghcr.io
gcloud run deploy quantum-ads-mcp \
  --image=europe-west1-docker.pkg.dev/<project>/ghcr/casius999/quantum-ads-mcp:<version> \
  --region=europe-west1 --port=8080 --allow-unauthenticated \
  --set-env-vars=QUANTUM_ADS_AUTH=google,QUANTUM_ADS_PUBLIC_URL=https://<service url>,QUANTUM_ADS_GOOGLE_ALLOWED=@youragency.com \
  --set-secrets=QUANTUM_ADS_GOOGLE_CLIENT_SECRET=qa-google-client-secret:latest,QUANTUM_ADS_JWT_SIGNING_KEY=qa-jwt-key:latest,GOOGLE_ADS_DEVELOPER_TOKEN=qa-dev-token:latest \
  --update-env-vars=QUANTUM_ADS_GOOGLE_CLIENT_ID=<client id>
```

`--allow-unauthenticated` only opens the HTTP endpoint; every MCP request still needs a valid
token from the configured mode. `deploy/cloudrun/service.yaml` is the same service as a
declarative file (`gcloud run services replace`). The signed audit is written under
`/data/audit` inside the instance; mount a volume there (Cloud Storage FUSE or Filestore) to keep
it across revisions.

Rate limits are per user (or tenant) and per instance (`QUANTUM_ADS_RATE_LIMIT_RPS`, default 10);
with several instances, cap them together with `--max-instances`.
