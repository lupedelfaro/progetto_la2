import requests
import datetime

# Function to get Kraken data

def get_kraken_data(pair):
    url = f'https://api.kraken.com/0/public/Ticker?pair={pair}'
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f'Error fetching data: {response.status_code}')
    data = response.json()
    if 'error' in data and data['error']:  
        raise Exception(f'Error in API response: {data['error']}')
    return data['result']

# Main function

def main():
    # Define currency pairs
    pairs = {'XBTUSD': 'XXBTZUSD', 'ETHUSD': 'XETHZUSD'}
    for old_pair, new_pair in pairs.items():
        try:
            data = get_kraken_data(new_pair)
            print(f'Data for {new_pair}: {data}')
        except Exception as e:
            print(f'Failed to retrieve data for {new_pair}: {str(e)}')

if __name__ == '__main__':
    main()