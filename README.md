# Advertiser Dashboard Automation

This project is a starter framework for client-facing advertiser dashboards.
It supports two reporting paths:

1. Streamlit app: choose one advertiser and generate a report view.
2. Power BI data layer: export advertiser-level tables to CSV or Excel for use in a filtered Power BI template.

The first implemented connector is GA4. Other source systems are represented in the shared schema so they can be added without changing the dashboard/reporting flow.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

The default GA4 setup reuses the OAuth files from the sibling `webscraping` project:

```text
GA4_PROPERTY_ID=123456789
GA4_CLIENT_SECRET_FILE=..\webscraping\config\client_secret.json
GA4_TOKEN_FILE=..\webscraping\config\token.json
```

If those values are blank, the app defaults to property `432233519` and the same sibling paths above. You can still use a service account by setting `GOOGLE_APPLICATION_CREDENTIALS`.

## Advertiser Config

Advertisers can come from either:

- Google Ad Manager, using the `sync-gam-advertisers` command.
- `config/advertisers.csv`, for manual overrides or GA4 matching rules.

To pull advertiser names from Google Ad Manager:

```powershell
Copy-Item config/googleads.yaml.example config/googleads.yaml
```

Fill in the GAM `network_code` and service-account key path, then run:

```powershell
python -m src.cli sync-gam-advertisers --output config/advertisers.csv
```

`config/googleads.yaml` can use either of these authentication styles:

```yaml
ad_manager:
  application_name: Advertiser Dashboard Automation
  network_code: YOUR_GAM_NETWORK_CODE
  path_to_private_key_file: C:\real\path\to\gam-service-account.json
```

or:

```yaml
ad_manager:
  application_name: Advertiser Dashboard Automation
  network_code: YOUR_GAM_NETWORK_CODE
  client_id: YOUR_CLIENT_ID
  client_secret: YOUR_CLIENT_SECRET
  refresh_token: YOUR_REFRESH_TOKEN
```

### Regenerate a Google Ad Manager refresh token

If the Google Ad Manager OAuth refresh token expires or is revoked, generate a
new one from the OAuth client file. Use the `admanager` scope, not the older
`dfp` scope:

```powershell
.\.venv\Scripts\Activate.ps1
python -c "from google_auth_oauthlib.flow import InstalledAppFlow; flow = InstalledAppFlow.from_client_secrets_file('config/gam_oauth_client.json', scopes=['https://www.googleapis.com/auth/admanager']); creds = flow.run_local_server(port=0, access_type='offline', prompt='consent'); print(creds.refresh_token)"
```

Sign in with a Google account that has access to the configured Google Ad
Manager network. Copy the printed token and replace only the `refresh_token`
value in `config/googleads.yaml`. Do not replace the `client_id` or
`client_secret` unless the OAuth client itself changed.

If the command prints `None` or Google keeps reusing the old grant, remove the
app from the Google account's third-party connections page, then run the command
again.

For service accounts, the service-account email also needs user/API access in the Google Ad Manager network.

For Streamlit Cloud, do not use a local Windows path in `config/googleads.yaml`.
Add these secrets in the Streamlit app settings instead:

```toml
GAM_NETWORK_CODE = "YOUR_GAM_NETWORK_CODE"
GAM_APPLICATION_NAME = "Advertiser Dashboard Automation"
GAM_SERVICE_ACCOUNT_JSON = """
PASTE_THE_FULL_SERVICE_ACCOUNT_JSON_FILE_CONTENTS_HERE
"""
```

When `config/googleads.yaml` is not present, the app builds the Google Ad
Manager config from these environment values. Locally, `config/googleads.yaml`
takes precedence, so you can keep using `path_to_private_key_file` on your
machine.

This writes GAM advertisers into the local advertiser config with:

- `advertiser_id`
- `advertiser_name`
- `gam_advertiser_id`
- `gam_advertiser_name`
- `gam_company_type`
- `gam_credit_status`

The Streamlit app can also read advertisers live from GAM from the sidebar.

Each row can include:

- `advertiser_id`: stable internal ID.
- `advertiser_name`: display name.
- `utm_source`, `utm_medium`, `utm_campaign`: optional filters used to isolate advertiser traffic in GA4.
- `landing_page_contains`: optional landing page filter.
- `notes`: free-form context.

Use whichever identifiers match how advertiser campaigns are tagged today. The GA4 connector builds a combined filter from the populated fields.

## HubSpot Email Performance

Set your private app token in `.env`:

```text
HUBSPOT_ACCESS_TOKEN=pat-na1-...
```

The Streamlit app can pull Marketing Emails API performance for:

- eNewsletter ads: matches placement dates for the selected advertiser to marketing email names like `MW m/dd/yy`. The default file is `data/newsletter_placements.csv`, falling back to `eNewsletter Ad Metrics.csv` in the project root. Users can also upload a newer CSV/XLSX file from the sidebar for a report run.
- Custom emails: matches email titles containing `[Advertiser Name] Custom Email`, optionally enriched with rows in `data/custom_email_placements.csv`.

Optional placement files can include `advertiser_id` or `advertiser_name`, plus a date column named `placement_date`, `date`, `newsletter_date`, or `send_date`. The eNewsletter export format with `Date`, `Delivered`, `Opened`, `Advertiser`, `Ad Type`, and `Clicks` is also supported; blank date/delivered/opened cells inherit the previous newsletter row.

To add advertiser names from the eNewsletter placement export into `config/advertisers.csv`:

```powershell
python -m src.cli sync-enewsletter-advertisers --placements "eNewsletter Ad Metrics.csv"
```

Or include them when syncing webinar sponsors:

```powershell
python -m src.cli sync-webinar-sponsors --include-enewsletter
```

To enrich `config/advertisers.csv` from all configured advertiser sources at once:

```powershell
python -m src.cli enrich-advertisers --placements "eNewsletter Ad Metrics.csv"
```

This adds or updates `gam`, `webinar`, and `email` columns with `true`/`false` source flags.

## Streamlit App

```powershell
streamlit run app.py
```

The app lets you select an advertiser, date range, and output mode. It currently shows GA4 website performance and placeholder sections for the remaining systems.

## Power BI Export

Export all advertisers to CSV files:

```powershell
python -m src.cli export --format csv --output-dir data/exports
```

Export all advertisers to one Excel workbook:

```powershell
python -m src.cli export --format xlsx --output-dir data/exports
```

The exported tables are shaped for Power BI filtering by `advertiser_id` and `advertiser_name`.

Current exported tables:

- `report_metadata`
- `ga4_website_performance`
- `gam_ad_performance`

`gam_ad_performance` includes ad impressions, ad clicks, and ad CTR by GAM advertiser and date.

## Source Roadmap

| Category | System | Status |
| --- | --- | --- |
| Webinars | Webinar.net | Planned |
| eNewsletter Ads | HubSpot | Planned |
| Website Ads | GAM and GA4 | GA4 starter implemented |
| Retargeting | StackAdapt | Planned |
| Custom Email | HubSpot | Planned |
| Lead Gen | Anteriad | Planned |
