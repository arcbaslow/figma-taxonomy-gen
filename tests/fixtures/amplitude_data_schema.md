# Amplitude Data CSV contract fixture

`amplitude_data_headers.csv` is a synthetic header-only template transcribed from
the **Events and event properties file schema** in the public
[Amplitude CSV documentation](https://amplitude.com/docs/data/csv-import-export),
checked 2026-09-30. It contains all 33 documented import columns and no
export-only timestamps. Column order is not significant to Amplitude.

This is not an account export or a template downloaded from the authenticated
UI. Tests pin the published contract; a real-project import has not been run.
Test events, descriptions, properties and Figma IDs are synthetic.
