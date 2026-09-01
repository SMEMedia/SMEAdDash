# Advertiser Dashboard

This dashboard creates advertiser performance reports for SME. It combines campaign data from Google Ad Manager, HubSpot email activity, and SME's shared Google Sheets into one Streamlit app. The app can be used to review campaign performance on screen and download a client-ready PDF report.

## What The Dashboard Does

The dashboard lets a user:

- Choose an advertiser.
- Choose a report date range.
- Pull available campaign data from connected sources.
- Add manual notes or manual metrics when a source is not automated.
- Choose which sections should appear in the PDF.
- Download a PDF report.

The dashboard is designed for campaign reporting, not for editing source-system data. The only source list it edits directly is the advertiser source Google Sheet.

## Connected Data Sources

| Report section | Where the data comes from | Status |
| --- | --- | --- |
| Website Ads | Google Ad Manager | Live |
| eNewsletter Ads | HubSpot + Master Digital Metrics File | Live |
| Custom Email | HubSpot | Live |
| Webinars | Master Digital Metrics File | Live |
| Lead Gen | Master Digital Metrics File | Live |
| Retargeting | Manual entry for now | Planned |

The dashboard also contains older helper code for GA4 and historical Webinar.net workflows. Those are not the primary nontechnical workflow today.

## The Two Google Sheets

The dashboard expects access to two Google Sheets:

1. **Advertiser Source**
   - Tab: `advertisers`
   - Purpose: the advertiser dropdown list.
   - The dashboard can refresh this sheet by adding advertisers found in Google Ad Manager and the master metrics sheet.

2. **Master Digital Metrics File**
   - Tabs used by the dashboard:
     - `2026 eNewsletter Ads`
     - `2026 Web Ads`
     - `2026 Webinars`
     - `2026 Custom Emails`
     - `2026 Lead Gen`
   - Purpose: placement and manually maintained performance data.

Both sheets must be shared with the Google service account used by the app.

## How To Run A Report

1. Open the Streamlit app.
2. Select an advertiser from the sidebar.
3. Choose the start date and end date.
4. Leave the connected data pulls selected unless there is a reason to skip one.
5. Use **Run report**.
6. Review the dashboard sections.
7. Use the PDF checkboxes to include or remove report sections.
8. Download the PDF report.

If an advertiser is missing from the dropdown, use **Search advertiser not shown in list** and type the company name. This searches the selected date range across the connected data sources.

## Refreshing The Advertiser List

Use **Refresh advertiser sheet** in the sidebar when new advertisers should be added to the dropdown.

That button updates the `Advertiser Source` Google Sheet by combining:

- existing advertisers already in the advertiser sheet,
- advertisers from Google Ad Manager,
- advertisers found in all supported tabs of the Master Digital Metrics File.

This is the normal way to keep the dropdown current.

## Manual Entry

Manual entry is available in the sidebar for:

- Website Ads
- Webinars
- eNewsletter Ads
- Retargeting
- Custom Email
- Lead Gen

Manual entry is useful when a report section is not automated yet, a data source is unavailable, or a one-off correction needs to appear in the PDF.

## Accounts And Credentials Needed

These are the account connections that must be transferred to the new owner or replaced with team-owned credentials.

### Google Sheets

Used for:

- reading the advertiser source sheet,
- writing refreshed advertisers back to the advertiser source sheet,
- reading the master metrics sheet.

Credential options:

- Streamlit Cloud secret named `gcp_service_account` or `google_service_account`, or
- environment variable `GOOGLE_SERVICE_ACCOUNT_JSON`, or
- local service account JSON file in `config/`.

The service account needs access to both Google Sheets.

### HubSpot

Used for:

- finding eNewsletter marketing emails,
- finding custom emails,
- pulling delivered/opened/click metrics,
- pulling creative and web-version URLs.

Required setting:

```text
HUBSPOT_ACCESS_TOKEN
```

The HubSpot token should come from an SME-owned private app or service key, not from a departing employee's personal setup.

### Google Ad Manager

Used for:

- advertiser list refresh,
- website ad impressions,
- website ad clicks,
- CTR,
- campaign and creative details.

Credential options:

- `config/googleads.yaml` locally, or
- Streamlit Cloud secrets/environment values:
  - `GAM_NETWORK_CODE`
  - `GAM_APPLICATION_NAME`
  - `GAM_SERVICE_ACCOUNT_JSON`
  - or OAuth values: `GAM_CLIENT_ID`, `GAM_CLIENT_SECRET`, `GAM_REFRESH_TOKEN`

For handoff, an SME-owned service account is the cleanest option.

## Important Files

| File or folder | Purpose |
| --- | --- |
| `app.py` | Main Streamlit dashboard. |
| `src/config.py` | Loads environment settings, Google Sheets data, and report source labels. |
| `src/gam_client.py` | Connects to Google Ad Manager. |
| `src/hubspot_client.py` | Connects to HubSpot marketing email data. |
| `src/master_metrics.py` | Reads the Master Digital Metrics File tabs. |
| `src/pdf_report.py` | Builds the PDF report. |
| `src/reporting.py` | Pulls together GAM, HubSpot, and sheet data for a selected advertiser. |
| `assets/sme_logo.png` | Logo used in the dashboard and PDF. |
| `config/report_sources.yml` | Labels shown in the Connected Sources table. |
| `config/googleads.yaml.example` | Example Google Ad Manager configuration. |
| `.env.example` | Template for local environment settings. Do not put real secrets in it. |

## Files That Should Stay Private

Do not commit these files to GitHub:

- `.env`
- `.streamlit/secrets.toml`
- `config/googleads.yaml`
- `config/*.json` service account files
- downloaded exports or temporary report files

The repository's `.gitignore` is set up to keep these private.

## Local Setup For A Technical Helper

Most users should use the deployed Streamlit app. If a technical helper needs to run it locally:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Then fill in `.env` with team-owned credentials and run:

```powershell
streamlit run app.py
```

## Streamlit Cloud Setup

In Streamlit Cloud, add secrets for the same account connections:

- Google service account JSON for the Google Sheets.
- HubSpot access token.
- Google Ad Manager credentials.

Keep all real tokens and JSON keys in Streamlit secrets. Do not paste them into files committed to GitHub.

## Common Issues

### Advertiser is missing from the dropdown

Use **Refresh advertiser sheet**. If the advertiser still does not appear, use **Search advertiser not shown in list**.

### HubSpot email section is empty

Check:

- the HubSpot token is current,
- the token has marketing email access,
- the email name contains the expected advertiser/date text,
- the selected date range includes the email.

### Website ads are empty

Check:

- the advertiser has a Google Ad Manager advertiser ID,
- the selected date range includes campaign delivery,
- Google Ad Manager credentials are working.

### Webinars or lead gen are empty

Check:

- the advertiser name in the master sheet matches the name being searched,
- the selected date range overlaps the row's date range,
- the relevant master sheet tab has data.

## Handoff Checklist

Before the project owner changes:

- Transfer or recreate the HubSpot private app/service key.
- Transfer or recreate the Google service account used for Sheets.
- Share `Advertiser Source` with the new service account.
- Share `Master Digital Metrics File` with the new service account.
- Transfer or recreate Google Ad Manager credentials.
- Update Streamlit Cloud secrets with the new credentials.
- Confirm the GitHub repo owner/admin access is assigned to the right SME person.
- Run one test report in Streamlit after credentials are updated.

