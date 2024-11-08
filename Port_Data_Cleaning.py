import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# Streamlit app title
st.title("Port Receiving Supervision Data - Data Exceptions and CSV Download")

# File uploader widget
uploaded_file = st.file_uploader("Choose a file", type=['xlsx'])

# If a file is uploaded
if uploaded_file is not None:
    try:
        # Load the RawData sheet with the specified header row
        df = pd.read_excel(uploaded_file, sheet_name="RawData", header=1)
        df['Added Time'] = pd.to_datetime(df['Added Time'], errors='coerce')  # Ensure Added Time is in datetime format

        # Standardize "BAG OFFLOADING DATE" or "BAG OFFLOADED DATE" to a single column name
        if 'BAG OFFLOADING DATE' in df.columns:
            df.rename(columns={'BAG OFFLOADING DATE': 'BAG OFFLOADED DATE'}, inplace=True)
        elif 'BAG OFFLOADED DATE' in df.columns:
            df.rename(columns={'BAG OFFLOADED DATE': 'BAG OFFLOADED DATE'}, inplace=True)

        # Identify columns and process data as in previous code
        bag_id_column = next((col for col in df.columns if "bag id" in col.lower()), None)
        horse_registration_column = next((col for col in df.columns if "receiving horse registration" in col.lower()),
                                         None)
        kico_seal_column = next((col for col in df.columns if "kico seal no." in col.lower()), None)
        added_time_column = next((col for col in df.columns if "added time" in col.lower()), None)

        if bag_id_column and horse_registration_column and kico_seal_column and added_time_column:
            # Extract components and create combined_df as in previous code
            def extract_bag_info(bag_id):
                parts = dict(item.split('=') for item in bag_id.split(',') if '=' in item)
                parts.update({item.split(': ')[0]: item.split(': ')[1] for item in bag_id.split(',') if ': ' in item})
                return parts

            bag_info_df = df[bag_id_column].dropna().apply(extract_bag_info).apply(pd.Series)
            combined_df = pd.concat([df, bag_info_df], axis=1)
            combined_df["Bag Scanned & Manual"] = combined_df.apply(
                lambda row: row["Bag"] if len(str(row[bag_id_column])) > 20 else row[bag_id_column],
                axis=1
            )
            combined_df = combined_df.sort_values(by=added_time_column, ascending=False)

            # Display total and data for combined_df first
            st.write(f"Total Combined DataFrame Entries: {len(combined_df)}")
            st.write("Combined DataFrame with extracted components (Sorted by Added Time):")
            st.dataframe(combined_df)

            # Display total and data for duplicates exceptions
            duplicates = combined_df[combined_df.duplicated(subset=["Bag Scanned & Manual"], keep=False)]
            duplicates_exceptions = duplicates.groupby("Bag Scanned & Manual").apply(
                lambda group: pd.Series({
                    "Added Time": ', '.join(group[added_time_column].astype(str).unique()),
                    "Bag Scanned & Manual": group["Bag Scanned & Manual"].iloc[0],
                    "KICO SEAL NO.": ', '.join(group[kico_seal_column].astype(str).unique()),
                    "Horse Registration IDs": ', '.join(group[horse_registration_column].astype(str).unique()),
                    "Lot IDs": ', '.join(group["Lot"].dropna().unique())
                })
            ).reset_index(drop=True)
            duplicates_exceptions = duplicates_exceptions.sort_values(by="Added Time", ascending=False)

            st.write(f"Total Duplicates Exceptions: {len(duplicates_exceptions)}")
            st.write("Duplicates Exceptions DataFrame (Sorted by Added Time):")
            st.dataframe(duplicates_exceptions)

            # Display total and data for flagged entries
            flagged_bag_id_df = combined_df[combined_df[bag_id_column].str.len().between(16, 24)]
            flagged_bag_id_df = flagged_bag_id_df[[added_time_column, bag_id_column, kico_seal_column]]
            flagged_bag_id_df.columns = ["Added Time", "BAG ID", "KICO SEAL NO."]
            flagged_bag_id_df = flagged_bag_id_df.sort_values(by="Added Time", ascending=False)

            st.write(f"Total Flagged BAG ID Entries: {len(flagged_bag_id_df)}")
            st.write("Flagged BAG ID Entries (Length Between 16 and 24 Characters, Sorted by Added Time):")
            st.dataframe(flagged_bag_id_df)

            # Get the current time in South Africa timezone
            sa_timezone = pytz.timezone('Africa/Johannesburg')
            current_time_sa = datetime.now(sa_timezone)

            # Date-time picker for Combined_df_for_Download
            st.write("Select a date-time range to filter the Combined DataFrame:")
            start_date = st.date_input("Start Date", value=combined_df[added_time_column].min().date())
            start_time = st.time_input("Start Time", value=pd.to_datetime("00:00").time())
            end_date = st.date_input("End Date", value=current_time_sa.date())
            end_time = st.time_input("End Time", value=current_time_sa.time())

            start_datetime = pd.to_datetime(f"{start_date} {start_time}")
            end_datetime = pd.to_datetime(f"{end_date} {end_time}")
            combined_df_for_Download = combined_df[
                (combined_df[added_time_column] >= start_datetime) & (combined_df[added_time_column] <= end_datetime)]

            # Mapping for column names in the download CSV, excluding missing columns
            column_mappings = {
                "Bag Scanned & Manual": "name",
                "KICO SEAL NO.": "PRN_KICO_SEAL",
                "MMS SEAL NO": "MMS_SEAL_NO",
                "BAG OFFLOADED DATE": "PRN_RECEIVED_DATE",  # Updated to use standardized column
                "RECORD BAG CONDITION": "PORT_PRN_BAG_CONDITION_STATUS",
                "RECEIVING WAREHOUSE": "PRN_WAREHOUSE_NAME",
                "RECEIVING HORSE REGISTRATION": "PRN_TRUCK_REG",
                "Added Email ID": "WITNESS_PRN_USER",
                "Added Time": "PRN_FORM_COMPLETE"
            }

            # Check for column existence and create final mapping
            available_columns = {key: value for key, value in column_mappings.items() if
                                 key in combined_df_for_Download.columns}
            mapped_df_for_download = combined_df_for_Download.rename(columns=available_columns)

            # Add missing columns as empty if they don't exist in the data
            for col in column_mappings.values():
                if col not in mapped_df_for_download.columns:
                    mapped_df_for_download[col] = None

            # Add "+02:00" to all time columns in mapped_df_for_download
            for col in ["PRN_RECEIVED_DATE", "PRN_FORM_COMPLETE"]:  # Specify all columns with time information
                if col in mapped_df_for_download.columns:
                    mapped_df_for_download[col] = mapped_df_for_download[col].astype(str) + "+02:00"

            # Reorder columns according to column_mappings
            mapped_df_for_download = mapped_df_for_download[column_mappings.values()]

            # Define the filename based on start and end date-time selections
            file_name = f"From_{start_date.strftime('%Y%m%d')}_{start_time.strftime('%H%M')}_to_{end_date.strftime('%Y%m%d')}_{end_time.strftime('%H%M')}_Port_Receiving.csv"

            # Display total and mapped DataFrame for download
            st.write(f"Total Mapped DataFrame for Download: {len(mapped_df_for_download)}")
            st.write("Mapped DataFrame for Download:")
            st.dataframe(mapped_df_for_download)
            csv = mapped_df_for_download.to_csv(index=False)
            st.download_button(
                label="Download Mapped CSV",
                data=csv,
                file_name=file_name,
                mime="text/csv"
            )

    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    st.info("Awaiting file upload...")
