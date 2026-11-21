# Tech products sales dashboard

A Streamlit dashboard for the supplied sales workbook. It includes sales KPIs,
monthly trends, product/channel/payment/state charts, customer summaries, and
transaction details. Use the sidebar to filter results or upload another
compatible Excel workbook.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The app loads `data/Tech_Products_Sales_Data.xlsx` by default. Uploaded
workbooks must contain the same sales columns as the supplied workbook.
