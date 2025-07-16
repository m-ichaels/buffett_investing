import pandas as pd
import os

# Loading and cleaning the data
def load_and_clean_data(file_path):
    df = pd.read_excel(file_path, sheet_name="All_Stocks_EPS")
    
    # Define EPS columns for the years 2013–2022
    eps_columns = [f'EPS_{year}' for year in range(2013, 2023)]
    
    # Remove rows with missing or non-numeric data in any EPS column
    df = df.dropna(subset=eps_columns, how='any')
    for col in eps_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=eps_columns, how='any')
    
    return df

# Screening stocks based on criteria
def screen_stocks(df):
    qualifying_stocks = []
    
    for _, row in df.iterrows():
        ticker = row['Ticker']
        company = row['Company_Name']
        eps_values = [row[f'EPS_{year}'] for year in range(2013, 2023)]
        
        # Check for no negative EPS
        if all(eps > 0 for eps in eps_values):
            # Count years with EPS increase
            increase_count = sum(1 for i in range(1, len(eps_values)) if eps_values[i] > eps_values[i-1])
            
            # Check for at least 8 years of increase
            if increase_count >= 8:
                # Calculate total EPS growth
                total_growth = eps_values[-1] - eps_values[0]
                
                # Check for positive total growth
                if total_growth > 0:
                    qualifying_stocks.append({
                        'Ticker': ticker,
                        'Company_Name': company,
                        'EPS_2013': eps_values[0],
                        'EPS_2022': eps_values[-1],
                        'Years_Increased': increase_count,
                        'Total_Growth': total_growth
                    })
    
    return pd.DataFrame(qualifying_stocks)

def main():
    # Specify the path to the Excel file in Results folder
    file_path = os.path.join('Results', '2022.xlsx')
    
    # Load and clean data
    df = load_and_clean_data(file_path)
    
    # Screen stocks
    result_df = screen_stocks(df)
    
    # Output results
    if not result_df.empty:
        print("Stocks meeting all criteria (EPS increase in 8+ years, no negative EPS, positive total growth):")
        print(result_df[['Ticker', 'Company_Name', 'EPS_2013', 'EPS_2022', 'Years_Increased', 'Total_Growth']])
    else:
        print("No stocks meet all the specified criteria.")
    
    # Append results to the existing Excel file
    with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        result_df.to_excel(writer, sheet_name='Qualifying_Stocks', index=False)
    
    print(f"\nResults saved to '{file_path}' in 'Qualifying_Stocks' worksheet")

if __name__ == "__main__":
    main()