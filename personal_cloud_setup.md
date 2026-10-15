# Your personal saved football app — one-time setup

Use **Streamlit Community Cloud + a private Standard Cloudflare R2 bucket**.
Keep using your existing app and model code. Streamlit stores the keys; R2 stores
history, models and settings. After setup, open the app and let it load upcoming
projections. You do not have to upload your checked seasons or fit every week.

## 1. Update the existing app

Before replacing an older build, download its **Complete workspace backup**.
Keep that copy on your computer. It includes both history and model state;
a model-input snapshot alone does not contain checked raw history.

Extract `football_dashboard_prototype16_1.zip`. In your GitHub repository, replace
all files in the folder containing the deployed `app.py` with the contents of the
extracted `football_dashboard` folder. Include all new `.py` modules and
`requirements.txt`. Keep the same Streamlit entrypoint and branch.

Wait for the updated dependencies to install, then reboot the app if needed.
The sidebar should say **Prototype 16.1**. Uploading only `app.py`,
only the ZIP or an extra nested folder does not complete the update.

## 2. Make it personal

In Streamlit **app Settings → Sharing**, set **Only specific people can view this
app**. Keep access limited to your own developer/account login. Check that you
have not granted viewers access. Community Cloud supports one private app.

You can keep a private GitHub repository, too. Keys go in Secrets, never in
GitHub. Do this privacy step before connecting your personal saved workspace.

Official instructions: [Streamlit sharing](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app).

## 3. Create the private saved-data bucket

1. Sign into or create a Cloudflare account and open **R2 Object Storage**.
2. Activate R2 if prompted. Cloudflare may request billing details even though
   usage within the free allowance costs $0.
3. Create a bucket named `football-model`. Select **Standard** storage and the
   default jurisdiction/location selection. Leave public access disabled. No
   public `r2.dev` URL or custom domain is needed.
4. On the R2 overview, under **Account Details → API Tokens**, click **Manage**.
5. Create an R2 API token with **Object Read & Write** permission, scoped to this
   bucket. Use a name such as `personal-football-app`.
6. Copy the **Access Key ID** and **Secret Access Key**. The secret is displayed
   only at creation. Also copy your 32-character **Cloudflare Account ID**.
   The API token value itself is not the app's `R2_SECRET_ACCESS_KEY` field.

Official instructions: [R2 authentication](https://developers.cloudflare.com/r2/api/tokens/).

## 4. Store the keys once

Open your Streamlit app's **Settings → Secrets**. Add this TOML, replacing the
placeholders with your own values. Preserve unrelated existing secrets.

```toml
CFBD_API_KEY = "your-college-football-data-key"
ODDS_API_KEY = "your-odds-api-key"
R2_ACCOUNT_ID = "your-32-character-cloudflare-account-id"
R2_ACCESS_KEY_ID = "your-r2-access-key-id"
R2_SECRET_ACCESS_KEY = "your-r2-secret-access-key"
R2_BUCKET = "football-model"
```

Click **Save**, then **Reboot app**. Open **Setup & Saved Data**. The storage row
should say **Connected**, followed by **Saved automatically** once the page
finishes. Correct any displayed bucket/permission error before considering the
workspace saved. No R2 keys need to be pasted into the model UI.

Official instructions: [Streamlit Secrets settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/app-settings).

## 5. Reuse your saved workspace

Your existing cloud workspace loads automatically. Prototype 16 upgrades its
main forecasting recipe while retaining your historical datasets, player
inputs, reviews, settings and immutable records. New workspaces also have the
historical datasets and trained main models preloaded. There is no routine
ten-season download, retraining button or manual Apply step.

If automatic restore is unavailable, use **Setup & Saved Data → Restore complete
workspace backup → Restore complete backup**. Only use the optional legacy
history/model upload sections if you have separate older exports instead.
Then click **Save everything now**, confirm success and download a new complete
backup. If needed, **Restore approved trained recipe** reinstates the packaged
forecasting algorithms without erasing your historical data.

For complete Prototype 10, 11 or 12 backups, **Restore complete workspace backup → Restore
complete backup** restores both history and models in one action.

Prototype 16 retains automatic frozen forecasts/results and observed market line
history to that same cloud save. No new keys, bucket or historical download is
needed. Current-year NFL and CFB game-level history is saved automatically in
the background; qualifying model updates require later-week checks. Automatic
learning is on by default and can be disabled. A previously played game without a saved pregame record cannot be
backfilled as a genuine past model pick. Public/ sharp-money coverage is not yet
connected and is never inferred from the eventual winner.

The main spread/total recipe is separate from the earlier core tree stage.
**Method & Validation** names the actual active algorithms, shows comparisons,
and distinguishes validated historical effects from live scenario assumptions.

## After that

Open the app and sign in. It restores saved data before loading the bundled
example. Automatic loading uses the next seven days in New York time, checks
whether a refresh is due and reuses the saved trained models. The default
full refresh interval is 60 minutes; injury checks have their own 60-minute
interval. Both switches are already on.

While the page is open, a five-minute timer checks whether those intervals have
elapsed. When Streamlit is asleep or no browser is open, this build does not run
a separate scheduled worker. The next visit resumes checks. Community Cloud can
sleep after 12 hours without traffic; use its wake button if shown. A cold start
or a new NFL play-by-play download may take longer than loading an existing save.

The readiness table states what is loaded, absent or optional. No current
bookmaker quotes means no current price-based value. Official DVOA/red-zone
DVOA/adjusted line yards, returning starters, manual injury overrides, CLV closes
and calibration archives remain optional. Check these rows only if you want
those extra terms. A loaded fit can still be inactive after core controls change
or required live statistics are missing; each projection explains why.

Public injury listings are free, but incomplete. NFL uses ESPN with Covers as
fallback; CFB uses Covers. They need no additional key. Older/mismatched reports
are withheld. Missing reports mean unknown coverage. Estimated injury player
values and uncertain-status probabilities are assumptions, not trained effects.

## Cost and limits

- [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud): free hosting, with resource/sleep limits.
- [R2 Standard free allowance](https://developers.cloudflare.com/r2/pricing/):
  10 GB-month storage, 1 million Class A and 10 million Class B operations monthly.
  Charges apply above the allowance; it is not a hard $0 spending cap. Keep an
  eye on Cloudflare usage. Infrequent Access does not have this free allowance.
- [CFBD free plan](https://collegefootballdata.com/api-tiers): 1,000 monthly
  calls for core/historical endpoints. Existing access/quota still applies.
- [The Odds API free plan](https://the-odds-api.com/): 500 monthly credits. NFL
  ATTD requests add event-level usage. Leaving the app open for many hours with
  frequent refreshes can exhaust the free allowance. Choose a longer full
  refresh interval in Setup if you need to conserve credits; injury checking
  can retain its shorter interval.

The app does not automatically buy a plan. Quota/access failures are displayed.
Past-season requests are cached for 90 days, including across host restarts;
weekly refreshes do not repeat the multi-season training process. Stored raw
history and fitted models stay available independently of that request cache.

## If a save fails

Your current browser state remains available. Download a complete backup before
closing it. Fix host Secrets/permissions and reboot. If another browser saved
newer data, the app pauses replacement; download this session first and then
**Reload saved workspace**. A corrupt cloud workspace is also protected from
being overwritten by the example automatically.

R2 keeps the latest manifest, one previous manifest and shared history objects.
The app's complete backup is the convenient recovery file. This release was
checked with a compatible S3 test double and a durable local save/restore;
your actual authenticated R2 connection still needs the check in step 4.
