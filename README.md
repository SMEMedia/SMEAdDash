# SME Advertiser Dashboard

This dashboard combines advertiser campaign information from Google Ad Manager, HubSpot, and SME’s shared Google Sheets. It can be used to review results on screen and download a client-ready PDF.

## Important links

- [Open the Advertiser Dashboard](https://smeaddash.streamlit.app/)
- [Advertiser Source](https://docs.google.com/spreadsheets/d/1wg3z5PmvSyyyNctwJuJzE6BMCUtVCin1GXdc20EFz_U/edit)
- [Master Digital Metrics File](https://docs.google.com/spreadsheets/d/1JAUNHKaIEW3mxEo-K_ENHsRXBNzLUV5v7XCQXvl4KTI/edit)
- [SMEMedia repository](https://github.com/SMEMedia/SMEAdDash)

## Run an advertiser report

1. Select the advertiser and reporting date range.
2. Leave the connected sources selected unless a source should intentionally be skipped.
3. Select **Run report**.
4. Review every report section.
5. Use the PDF checkboxes to include or remove sections.
6. Add manual notes or metrics only when an automated source is unavailable or a documented correction is required.
7. Download the PDF and verify it before sending it to a client.

## Where information comes from

| Report section | Source |
| --- | --- |
| Website Ads | Google Ad Manager |
| eNewsletter Ads | HubSpot and the Master Digital Metrics File |
| Custom Email | HubSpot |
| Webinars | Master Digital Metrics File |
| Lead Gen | Master Digital Metrics File |
| Retargeting | Manual entry |

The dashboard reads the Master Digital Metrics File and can update the advertiser list in the Advertiser Source Sheet. It does not edit campaigns in HubSpot or Google Ad Manager.

## Keep the advertiser list current

Select **Refresh advertiser sheet** when a new advertiser should appear. The dashboard combines existing names with advertisers found in Google Ad Manager and the supported tabs of the Master Digital Metrics File.

If a name still does not appear, use **Search advertiser not shown in list** and enter the company’s expected name.

## Troubleshooting

### An advertiser is missing

- Select **Refresh advertiser sheet** and wait for completion.
- Search for the advertiser using a shorter or alternate spelling.
- Check the Advertiser Source and the Master Digital Metrics File for spelling differences.
- Confirm the selected date range contains activity for the advertiser.

### Website Ads is empty

- Confirm the date range includes campaign delivery.
- Confirm the selected advertiser matches the Google Ad Manager advertiser name.
- Check whether Google Ad Manager itself shows impressions for the same period.
- If the dashboard reports an access error, contact the Google Ad Manager or Streamlit owner.

### eNewsletter or Custom Email is empty

- Confirm the email was sent during the selected period.
- Check that the HubSpot email name contains the expected advertiser name.
- Compare the spelling with the dashboard advertiser selection.
- If an authorization message appears, contact the HubSpot and Streamlit owners.

### Webinars or Lead Gen is empty

- Check the relevant tab in the Master Digital Metrics File.
- Confirm advertiser spelling and date fields match the requested report.
- Confirm the row contains the expected performance values.

### The PDF is missing a section

- Confirm the section appears on screen.
- Confirm its PDF checkbox is selected.
- Add a clearly labeled manual value only when the approved source is unavailable.
- Generate a new PDF and review every page before sending.

### A report contains duplicate or unexpected results

- Check for multiple spellings of the advertiser in the shared Sheets.
- Narrow the date range and rerun the report.
- Record the unexpected rows, source, advertiser, and date range before escalating.

### A credential or permission error appears

- Do not place tokens or keys in GitHub, email, chat, tickets, or screenshots.
- Contact the owner of the affected source and the Streamlit owner.
- After access is restored, rerun the report and verify the results against the source system.

## Ongoing maintenance

- Refresh the advertiser list when new campaigns begin.
- Keep advertiser names consistent across Google Ad Manager, HubSpot, and the shared Sheets.
- Verify downloaded PDFs before external use.
- Keep source-system, Streamlit, and Google Sheet access assigned to current SME staff.
- Escalate credential, source-mapping, deployment, and code changes to the assigned technical owner.

*** Delete File: SMEAppDash/README.md
